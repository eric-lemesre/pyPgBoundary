"""Catalogue des produits IGN et sources géographiques.

Ce package contient les définitions des produits géographiques
disponibles pour le téléchargement et l'importation.

Les définitions de produits sont chargées depuis les fichiers YAML
dans le répertoire sources/.
"""

from pgboundary.products.admin_express import ADMIN_EXPRESS_PRODUCTS
from pgboundary.products.catalog import (
    FileFormat,
    GeometryType,
    IGNProduct,
    LayerConfig,
    ProductCatalog,
    ProductCategory,
    TerritoryCode,
    get_admin_express_product,
    get_codes_postaux_product,
    get_default_catalog,
)
from pgboundary.products.codes_postaux import CODES_POSTAUX_PRODUCTS
from pgboundary.products.other import OTHER_PRODUCTS

__all__ = [
    # Produits
    "ADMIN_EXPRESS_PRODUCTS",
    "CODES_POSTAUX_PRODUCTS",
    "OTHER_PRODUCTS",
    # Enums
    "FileFormat",
    "GeometryType",
    # Modèles
    "IGNProduct",
    "LayerConfig",
    # Catalogue
    "ProductCatalog",
    "ProductCategory",
    "TerritoryCode",
    # Fonctions
    "get_admin_express_product",
    "get_codes_postaux_product",
    "get_default_catalog",
]
