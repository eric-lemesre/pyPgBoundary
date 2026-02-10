"""Backward compatibility: definitions of other IGN products.

Products are now defined in YAML files under sources/.
This module provides the same exports for backward compatibility.
"""

from __future__ import annotations

from pgboundary.products.catalog import (
    IGNProduct,
    ProductCategory,
    get_default_catalog,
)


def _get_other_products() -> list[IGNProduct]:
    """Return all products that are not Admin Express or postal codes."""
    catalog = get_default_catalog()
    excluded_categories = {ProductCategory.ADMIN, ProductCategory.ADDRESS}
    return [p for p in catalog.list_all() if p.category not in excluded_categories]


OTHER_PRODUCTS: list[IGNProduct] = _get_other_products()

__all__ = [
    "OTHER_PRODUCTS",
]
