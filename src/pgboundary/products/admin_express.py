"""Backward compatibility: Admin Express definitions.

Products are now defined in YAML files under sources/.
This module provides the same exports for backward compatibility.
"""

from __future__ import annotations

from pgboundary.products.catalog import (
    IGNProduct,
    ProductCategory,
    get_admin_express_product,
    get_default_catalog,
)


def _get_admin_express_products() -> list[IGNProduct]:
    """Return all Admin Express products from the YAML catalog."""
    catalog = get_default_catalog()
    return catalog.list_by_category(ProductCategory.ADMIN)


ADMIN_EXPRESS_PRODUCTS: list[IGNProduct] = _get_admin_express_products()

__all__ = [
    "ADMIN_EXPRESS_PRODUCTS",
    "get_admin_express_product",
]
