"""Catalogue des produits IGN et sources géographiques.

Ce package contient les définitions des produits géographiques
disponibles pour le téléchargement et l'importation.

Produits supportés:
- Admin Express (5 variantes)
- Contours IRIS
- BD FORÊT et Masque FORÊT
- BD CARTO
- ADRESSE PREMIUM
- BAN PLUS
- BCAE
- Codes Postaux (4 sources)
"""

from pgboundary.products.admin_express import (
    ADMIN_EXPRESS_PRODUCTS,
    get_admin_express_product,
)
from pgboundary.products.catalog import (
    FileFormat,
    GeometryType,
    IGNProduct,
    LayerConfig,
    ProductCatalog,
    ProductCategory,
    TerritoryCode,
    get_default_catalog,
)
from pgboundary.products.codes_postaux import (
    CODES_POSTAUX_PRODUCTS,
    get_codes_postaux_product,
)
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
