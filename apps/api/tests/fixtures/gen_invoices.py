"""Synthetic invoice fixtures (committed generator, not binaries).

Each builder returns ``(image_bytes, golden_json)``:
  * ``image_bytes`` — a valid JPEG that passes upload hardening. The pixels are
    placeholder; the NullInvoiceExtractor is driven by the golden JSON keyed by
    the image's sha256, so the (multilingual) line content lives in the golden.
  * ``golden_json`` — the exact JSON the extractor would return, in the
    ``invoice_extraction`` schema.

Three vendors exercise the moat: (a) SWAD mixed Devanagari/English with "6/#10"
and "बोरी 25kg"; (b) a Spanish produce house with a "CAJA 60" and a catch-weight
chicken line; (c) a thermal cash-and-carry receipt with a FEE line and a credit.
"""

from __future__ import annotations

import hashlib
import io

from PIL import Image, ImageDraw


def _image(lines: list[str], *, size: tuple[int, int] = (820, 1040)) -> bytes:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    y = 30
    for text in lines:
        draw.text((30, y), text, fill="black")
        y += 26
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def swad_invoice() -> tuple[bytes, dict]:
    image = _image(
        [
            "SWAD / RAJA FOODS - WHOLESALE INVOICE",
            "Invoice #SW-4471   Date 07/03/2026",
            "1 Basmati Rice / basmati chawal - bori 25kg",
            "2 Tomatoes / tamatar - 6/#10",
            "3 Jeera / cumin - 5 LB",
            "TOTAL 200.00",
        ]
    )
    golden = {
        "vendor_name": "SWAD / Raja Foods",
        "invoice_number": "SW-4471",
        "invoice_date": "2026-07-03",
        "currency": "USD",
        "stated_total_cents": 20000,
        "lines": [
            {
                "line_no": 1,
                "raw_text": "बासमती चावल / Basmati Rice — बोरी 25kg",
                "raw_lang": "mixed",
                "description_en": "basmati rice",
                "brand": "SWAD",
                "pack_desc": "बोरी 25kg",
                "case_count": 1,
                "pack_qty": 25,
                "pack_unit": "kg",
                "quantity_ordered": 4,
                "unit_price_cents": 3200,
                "extended_cents": 12800,
                "is_credit": False,
                "confidence": 0.97,
            },
            {
                "line_no": 2,
                "raw_text": "टमाटर / Tomatoes 6/#10",
                "raw_lang": "mixed",
                "description_en": "canned tomatoes",
                "brand": "SWAD",
                "pack_desc": "6/#10",
                "case_count": 6,
                "pack_qty": 2.84,
                "pack_unit": "kg",
                "quantity_ordered": 2,
                "unit_price_cents": 2700,
                "extended_cents": 5400,
                "is_credit": False,
                "confidence": 0.95,
            },
            {
                "line_no": 3,
                "raw_text": "जीरा / Jeera 5 LB",
                "raw_lang": "hi",
                "description_en": "cumin seeds",
                "brand": "Laxmi",
                "pack_desc": "5 LB",
                "case_count": 1,
                "pack_qty": 5,
                "pack_unit": "lb",
                "quantity_ordered": 1,
                "unit_price_cents": 1800,
                "extended_cents": 1800,
                "is_credit": False,
                "confidence": 0.98,
            },
        ],
    }
    return image, golden


def produce_invoice() -> tuple[bytes, dict]:
    image = _image(
        [
            "DISTRIBUIDORA DE VERDURAS EL SOL",
            "Factura 8890  Fecha 02/07/2026",
            "CILANTRO CAJA 60",
            "POLLO 40.2 LB @ $1.89",
            "TOTAL 105.98",
        ]
    )
    golden = {
        "vendor_name": "Distribuidora El Sol",
        "invoice_number": "8890",
        "invoice_date": "2026-07-02",
        "currency": "USD",
        "stated_total_cents": 10598,
        "lines": [
            {
                "line_no": 1,
                "raw_text": "CILANTRO CAJA 60",
                "raw_lang": "es",
                "description_en": "cilantro",
                "brand": None,
                "pack_desc": "CAJA 60",
                "case_count": 60,
                "pack_qty": 1,
                "pack_unit": "each",
                "quantity_ordered": 1,
                "unit_price_cents": 3000,
                "extended_cents": 3000,
                "is_credit": False,
                "confidence": 0.9,
            },
            {
                "line_no": 2,
                "raw_text": "POLLO 40.2 LB @ $1.89",
                "raw_lang": "es",
                "description_en": "chicken",
                "brand": None,
                "pack_desc": "40.2 LB @ $1.89/lb",
                "case_count": None,
                "pack_qty": 40.2,
                "pack_unit": "lb",
                "quantity_ordered": 1,
                "unit_price_cents": 189,
                "extended_cents": 7598,
                "is_credit": False,
                "confidence": 0.92,
            },
        ],
    }
    return image, golden


def thermal_invoice() -> tuple[bytes, dict]:
    image = _image(
        [
            "CASH & CARRY #12",
            "RICE 20LB",
            "DELIVERY FEE",
            "RETURN OIL",
            "TOTAL 8.00",
        ],
        size=(420, 900),
    )
    golden = {
        "vendor_name": "Cash & Carry #12",
        "invoice_number": None,
        "invoice_date": "2026-07-05",
        "currency": "USD",
        "stated_total_cents": 800,
        "lines": [
            {
                "line_no": 1,
                "raw_text": "RICE 20 LB BAG",
                "raw_lang": "en",
                "description_en": "rice",
                "brand": None,
                "pack_desc": "20 LB BAG",
                "case_count": 1,
                "pack_qty": 20,
                "pack_unit": "lb",
                "quantity_ordered": 1,
                "unit_price_cents": 1500,
                "extended_cents": 1500,
                "is_credit": False,
                "confidence": 0.8,
            },
            {
                "line_no": 2,
                "raw_text": "DELIVERY FEE",
                "raw_lang": "en",
                "description_en": "FEE: delivery",
                "brand": None,
                "pack_desc": "",
                "case_count": None,
                "pack_qty": None,
                "pack_unit": None,
                "quantity_ordered": 1,
                "unit_price_cents": 500,
                "extended_cents": 500,
                "is_credit": False,
                "confidence": 0.99,
            },
            {
                "line_no": 3,
                "raw_text": "RETURN - DAMAGED OIL 1 GAL",
                "raw_lang": "en",
                "description_en": "cooking oil (return)",
                "brand": None,
                "pack_desc": "1 GAL",
                "case_count": 1,
                "pack_qty": 1,
                "pack_unit": "gal",
                "quantity_ordered": 1,
                "unit_price_cents": 1200,
                "extended_cents": 1200,
                "is_credit": True,
                "confidence": 0.85,
            },
        ],
    }
    return image, golden


ALL_FIXTURES = {
    "swad": swad_invoice,
    "produce": produce_invoice,
    "thermal": thermal_invoice,
}
