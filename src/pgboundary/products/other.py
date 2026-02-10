"""Rétrocompatibilité: définitions des autres produits IGN.

Les produits sont désormais définis dans les fichiers YAML sous sources/.
Ce module fournit les mêmes exports pour la rétrocompatibilité.
"""

from __future__ import annotations

from pgboundary.products.catalog import (
    IGNProduct,
    ProductCategory,
    get_default_catalog,
)


def _get_other_products() -> list[IGNProduct]:
    """Retourne tous les produits non-Admin Express et non-codes postaux."""
    catalog = get_default_catalog()
    excluded_categories = {ProductCategory.ADMIN, ProductCategory.ADDRESS}
    return [p for p in catalog.list_all() if p.category not in excluded_categories]


OTHER_PRODUCTS: list[IGNProduct] = _get_other_products()

__all__ = [
    "OTHER_PRODUCTS",
]
