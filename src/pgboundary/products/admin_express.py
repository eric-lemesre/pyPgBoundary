"""Rétrocompatibilité: définitions Admin Express.

Les produits sont désormais définis dans les fichiers YAML sous sources/.
Ce module fournit les mêmes exports pour la rétrocompatibilité.
"""

from __future__ import annotations

from pgboundary.products.catalog import (
    IGNProduct,
    ProductCategory,
    get_admin_express_product,
    get_default_catalog,
)


def _get_admin_express_products() -> list[IGNProduct]:
    """Retourne tous les produits Admin Express depuis le catalogue YAML."""
    catalog = get_default_catalog()
    return catalog.list_by_category(ProductCategory.ADMIN)


ADMIN_EXPRESS_PRODUCTS: list[IGNProduct] = _get_admin_express_products()

__all__ = [
    "ADMIN_EXPRESS_PRODUCTS",
    "get_admin_express_product",
]
