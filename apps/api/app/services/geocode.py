"""Geocoding service: address → (lat, lng).

Providers behind one protocol, chosen by env: ``GoogleGeocodeProvider``,
``MapboxGeocodeProvider``, and ``NullGeocodeProvider`` (returns nothing; used in
tests / when unconfigured). Every call gets a timeout, retries, and a circuit
breaker. Geocoding never blocks saving a store — ``GeocodeService.locate``
returns ``None`` on failure and the caller keeps ``lat/lng`` null for manual entry.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.translation import CircuitBreaker  # reuse the shared breaker

logger = get_logger("geocode")

GEOCODE_TIMEOUT_S = 3.0
GEOCODE_RETRIES = 2


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lng: float


class GeocodeProvider(Protocol):
    name: str

    async def geocode(self, address: str) -> GeocodeResult | None: ...


class NullGeocodeProvider:
    name = "null"

    async def geocode(self, address: str) -> GeocodeResult | None:
        return None


class GoogleGeocodeProvider:
    name = "google"
    _URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def geocode(self, address: str) -> GeocodeResult | None:
        async with httpx.AsyncClient(timeout=GEOCODE_TIMEOUT_S) as client:
            resp = await client.get(self._URL, params={"address": address, "key": self._api_key})
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        loc = results[0]["geometry"]["location"]
        return GeocodeResult(lat=float(loc["lat"]), lng=float(loc["lng"]))


class MapboxGeocodeProvider:
    name = "mapbox"
    _URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def geocode(self, address: str) -> GeocodeResult | None:
        url = f"{self._URL}/{httpx.URL(address)}.json"
        async with httpx.AsyncClient(timeout=GEOCODE_TIMEOUT_S) as client:
            resp = await client.get(url, params={"access_token": self._api_key, "limit": 1})
            resp.raise_for_status()
            data = resp.json()
        features = data.get("features") or []
        if not features:
            return None
        lng, lat = features[0]["center"]
        return GeocodeResult(lat=float(lat), lng=float(lng))


class GeocodeService:
    def __init__(self, provider: GeocodeProvider, *, breaker: CircuitBreaker | None = None) -> None:
        self.provider = provider
        self._breaker = breaker or CircuitBreaker()

    async def locate(self, address: str) -> GeocodeResult | None:
        """Best-effort geocode. Returns None on empty result or provider failure."""
        if not address.strip() or self._breaker.is_open:
            return None
        last_exc: Exception | None = None
        for attempt in range(GEOCODE_RETRIES + 1):
            try:
                result = await asyncio.wait_for(
                    self.provider.geocode(address), timeout=GEOCODE_TIMEOUT_S
                )
                self._breaker.record_success()
                return result
            except Exception as exc:  # noqa: BLE001 — uniform failure handling
                last_exc = exc
                self._breaker.record_failure()
                logger.warning("geocode_failed", attempt=attempt, error=str(exc))
        logger.warning("geocode_degraded", address=address, error=str(last_exc))
        return None


def get_geocode_provider() -> GeocodeProvider:
    provider = settings.geocode_provider.lower()
    if provider == "google" and settings.geocode_api_key:
        return GoogleGeocodeProvider(settings.geocode_api_key)
    if provider == "mapbox" and settings.geocode_api_key:
        return MapboxGeocodeProvider(settings.geocode_api_key)
    return NullGeocodeProvider()


@lru_cache
def get_geocode_service() -> GeocodeService:
    return GeocodeService(get_geocode_provider())
