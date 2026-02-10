"""Rétrocompatibilité: définitions des produits codes postaux.

Les produits sont désormais définis dans les fichiers YAML sous sources/.
Ce module fournit les mêmes exports pour la rétrocompatibilité.
"""

from __future__ import annotations

from pgboundary.products.catalog import (
    IGNProduct,
    ProductCategory,
    get_codes_postaux_product,
    get_default_catalog,
)


def _get_codes_postaux_products() -> list[IGNProduct]:
    """Retourne tous les produits de la catégorie ADDRESS."""
    catalog = get_default_catalog()
    return catalog.list_by_category(ProductCategory.ADDRESS)


CODES_POSTAUX_PRODUCTS: list[IGNProduct] = _get_codes_postaux_products()

__all__ = [
    "CODES_POSTAUX_PRODUCTS",
    "get_codes_postaux_product",
]
