"""Repository layer.

This is the ONLY layer permitted to build raw ``select(...)`` statements. Every
query is org-scoped through :meth:`OrgScopedRepository.scoped` so tenant isolation
can never be skipped by accident (enforced by ``tests/test_org_scoping.py``).
"""

from app.repositories.base import OrgScopedRepository
from app.repositories.ingredients import IngredientRepository
from app.repositories.prices import PriceRepository
from app.repositories.stores import StoreRepository
from app.repositories.tenancy import OrgRepository, UserRepository

__all__ = [
    "IngredientRepository",
    "OrgRepository",
    "OrgScopedRepository",
    "PriceRepository",
    "StoreRepository",
    "UserRepository",
]
