"""Shared slowapi limiter.

Kept in its own module so both the app factory and the feature routers import the
same instance without a circular import.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
