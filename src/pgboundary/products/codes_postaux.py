"""Backward compatibility: postal code product definitions.

Products are now defined in YAML files under sources/.
This module provides the same exports for backward compatibility.
"""

from __future__ import annotations

from pgboundary.products.catalog import (
    IGNProduct,
    ProductCategory,
    get_codes_postaux_product,
    get_default_catalog,
)


def _get_codes_postaux_products() -> list[IGNProduct]:
    """Return all products in the ADDRESS category."""
    catalog = get_default_catalog()
    return catalog.list_by_category(ProductCategory.ADDRESS)


CODES_POSTAUX_PRODUCTS: list[IGNProduct] = _get_codes_postaux_products()

__all__ = [
    "CODES_POSTAUX_PRODUCTS",
    "get_codes_postaux_product",
]
