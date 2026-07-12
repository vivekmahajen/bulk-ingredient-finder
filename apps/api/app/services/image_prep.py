"""Upload hardening for invoice images.

Validates + normalizes an uploaded file before it ever reaches storage or the
model: magic-byte sniffing (don't trust the client content-type), size/page
caps, EXIF stripping (re-encode), downscale to a max edge, and PDF → per-page
PNG rasterization. Raises typed errors the endpoint maps to RFC-7807 problems.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image

MAX_EDGE_PX = 2200
_JPEG_QUALITY = 85

# Best-effort HEIC support; absent plugin just means HEIC decode fails to 422.
try:  # pragma: no cover - depends on optional wheel
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # noqa: BLE001
    pass


class UploadError(Exception):
    """Base for upload-hardening failures. ``status`` maps to the HTTP problem."""

    status = 400

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class UnsupportedMedia(UploadError):
    status = 415


class ImageTooLarge(UploadError):
    status = 413


class TooManyPages(UploadError):
    status = 413


class CorruptImage(UploadError):
    status = 422


@dataclass(frozen=True)
class PreparedUpload:
    sha256: str
    ext: str
    stored_bytes: bytes
    stored_content_type: str
    images: list[bytes]  # per-page bytes handed to the extractor
    page_count: int


def sniff_content_type(data: bytes) -> str | None:
    """Detect media type from magic bytes. Returns None if unrecognized."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"mif1", b"heim"):
        return "image/heic"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    return None


_ACCEPTED = {"image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"}


def _normalize_raster(img: Image.Image) -> bytes:
    """Downscale + strip EXIF by re-encoding to JPEG (RGB)."""
    img = img.convert("RGB")
    longest = max(img.size)
    if longest > MAX_EDGE_PX:
        scale = MAX_EDGE_PX / longest
        img = img.resize((round(img.width * scale), round(img.height * scale)))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=_JPEG_QUALITY)  # no exif passed -> stripped
    return out.getvalue()


def _rasterize_pdf(data: bytes, max_pages: int) -> list[bytes]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        n = len(pdf)
        if n > max_pages:
            raise TooManyPages(f"PDF has {n} pages; the limit is {max_pages}.")
        pages: list[bytes] = []
        for i in range(n):
            page = pdf[i]
            # scale so the longest edge lands near MAX_EDGE_PX (72dpi base).
            bitmap = page.render(scale=min(4.0, MAX_EDGE_PX / max(page.get_size())))
            pil = bitmap.to_pil().convert("RGB")
            buf = io.BytesIO()
            pil.save(buf, format="JPEG", quality=_JPEG_QUALITY)
            pages.append(buf.getvalue())
        return pages
    finally:
        pdf.close()


def prepare_upload(data: bytes, *, max_mb: int, max_pages: int) -> PreparedUpload:
    if not data:
        raise CorruptImage("Empty upload.")
    if len(data) > max_mb * 1024 * 1024:
        raise ImageTooLarge(f"File exceeds the {max_mb} MB limit.")

    sniffed = sniff_content_type(data)
    if sniffed is None or sniffed not in _ACCEPTED:
        raise UnsupportedMedia("Unsupported file type. Use JPEG, PNG, WebP, HEIC, or PDF.")

    sha256 = hashlib.sha256(data).hexdigest()

    if sniffed == "application/pdf":
        pages = _rasterize_pdf(data, max_pages)
        if not pages:
            raise CorruptImage("PDF had no renderable pages.")
        return PreparedUpload(
            sha256=sha256,
            ext="jpg",
            stored_bytes=pages[0],
            stored_content_type="image/jpeg",
            images=pages,
            page_count=len(pages),
        )

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            normalized = _normalize_raster(img)
    except UploadError:
        raise
    except Exception as exc:  # noqa: BLE001 - decoding failures -> 422
        raise CorruptImage("Could not decode the image.") from exc

    return PreparedUpload(
        sha256=sha256,
        ext="jpg",
        stored_bytes=normalized,
        stored_content_type="image/jpeg",
        images=[normalized],
        page_count=1,
    )
