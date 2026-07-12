"""Static seed data for the Hari Om dogfood org.

Frequencies follow the ingredient-forecast rule from the spec:
staples = monthly, dairy/protein = twice_weekly, produce = weekly
(spices default to monthly, a couple of long-life ones quarterly).
"""

from __future__ import annotations

from app.models.enums import Category, DefaultUnit, PurchaseFrequency, StoreKind

ORG_NAME = "Hari Om"
SEED_USER_EMAIL = "owner@hariom.example"
SEED_USER_NAME = "Hari Om Owner"

# (canonical_name_en, display_name, category, default_unit, purchase_frequency)
INGREDIENTS: list[tuple[str, str, Category, DefaultUnit, PurchaseFrequency]] = [
    # Staples — monthly
    ("Basmati Rice", "Basmati Rice", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("Whole Wheat Flour", "Atta", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("All-Purpose Flour", "Maida", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("Gram Flour", "Besan", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("Toor Dal", "Toor Dal", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("Chana Dal", "Chana Dal", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("Moong Dal", "Moong Dal", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("Urad Dal", "Urad Dal", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("Kidney Beans", "Rajma", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("Chickpeas", "Kabuli Chana", Category.STAPLE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    # Spices — monthly / quarterly
    (
        "Turmeric Powder",
        "Turmeric Powder",
        Category.SPICE,
        DefaultUnit.KG,
        PurchaseFrequency.MONTHLY,
    ),
    ("Cumin Seeds", "Cumin Seeds", Category.SPICE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    (
        "Coriander Powder",
        "Coriander Powder",
        Category.SPICE,
        DefaultUnit.KG,
        PurchaseFrequency.MONTHLY,
    ),
    (
        "Red Chili Powder",
        "Red Chili Powder",
        Category.SPICE,
        DefaultUnit.KG,
        PurchaseFrequency.MONTHLY,
    ),
    ("Mustard Seeds", "Mustard Seeds", Category.SPICE, DefaultUnit.KG, PurchaseFrequency.MONTHLY),
    ("Garam Masala", "Garam Masala", Category.SPICE, DefaultUnit.KG, PurchaseFrequency.QUARTERLY),
    ("Green Cardamom", "Elaichi", Category.SPICE, DefaultUnit.KG, PurchaseFrequency.QUARTERLY),
    ("Curry Leaves", "Kadi Patta", Category.SPICE, DefaultUnit.BAG, PurchaseFrequency.MONTHLY),
    # Dairy — twice weekly
    ("Paneer", "Paneer", Category.DAIRY, DefaultUnit.KG, PurchaseFrequency.TWICE_WEEKLY),
    ("Clarified Butter", "Ghee", Category.DAIRY, DefaultUnit.KG, PurchaseFrequency.TWICE_WEEKLY),
    ("Yogurt", "Dahi", Category.DAIRY, DefaultUnit.KG, PurchaseFrequency.TWICE_WEEKLY),
    ("Milk", "Milk", Category.DAIRY, DefaultUnit.L, PurchaseFrequency.TWICE_WEEKLY),
    # Protein — twice weekly
    ("Chicken", "Chicken", Category.PROTEIN, DefaultUnit.KG, PurchaseFrequency.TWICE_WEEKLY),
    ("Goat Meat", "Mutton", Category.PROTEIN, DefaultUnit.KG, PurchaseFrequency.TWICE_WEEKLY),
    ("Eggs", "Eggs", Category.PROTEIN, DefaultUnit.EACH, PurchaseFrequency.TWICE_WEEKLY),
    # Produce — weekly
    ("Onions", "Pyaz", Category.PRODUCE, DefaultUnit.KG, PurchaseFrequency.WEEKLY),
    ("Tomatoes", "Tamatar", Category.PRODUCE, DefaultUnit.KG, PurchaseFrequency.WEEKLY),
    ("Potatoes", "Aloo", Category.PRODUCE, DefaultUnit.KG, PurchaseFrequency.WEEKLY),
    ("Ginger", "Adrak", Category.PRODUCE, DefaultUnit.KG, PurchaseFrequency.WEEKLY),
]

# (name, kind, website, address_line, city, state, postal)
STORES: list[tuple[str, StoreKind, str, str | None, str | None, str | None, str | None]] = [
    (
        "Sysco Sacramento",
        StoreKind.BROADLINE,
        "https://www.sysco.com",
        None,
        "Sacramento",
        "CA",
        None,
    ),
    ("US Foods", StoreKind.BROADLINE, "https://www.usfoods.com", None, "Sacramento", "CA", None),
    (
        "CHEF'STORE Redding",
        StoreKind.CASH_AND_CARRY,
        "https://www.chefstore.com",
        "1152 Hartnell Ave",
        "Redding",
        "CA",
        "96002",
    ),
    (
        "Raja Foods",
        StoreKind.ETHNIC_WHOLESALE,
        "https://www.rajafoods.com",
        None,
        "Skokie",
        "IL",
        None,
    ),
    (
        "House of Spices",
        StoreKind.ETHNIC_WHOLESALE,
        "https://www.hosindia.com",
        None,
        "Flushing",
        "NY",
        None,
    ),
    (
        "India Cash & Carry",
        StoreKind.ETHNIC_WHOLESALE,
        "https://www.indiacashandcarry.com",
        None,
        "Sunnyvale",
        "CA",
        None,
    ),
]
