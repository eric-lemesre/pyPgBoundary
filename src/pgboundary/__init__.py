"""
pyPgBoundary - Module Python pour charger les données géographiques IGN dans PostgreSQL/PostGIS.

Ce module permet de télécharger et charger les données géographiques de l'IGN
dans une base de données PostgreSQL avec l'extension PostGIS.

Produits supportés:
- Admin Express (5 variantes)
- Contours IRIS
- BD FORÊT et Masque FORÊT
- BD CARTO
- ADRESSE PREMIUM
- BAN PLUS
- BCAE
"""

from pgboundary.config import Settings
from pgboundary.loaders.admin_express import AdminExpressLoader
from pgboundary.loaders.product_loader import ProductLoader
from pgboundary.products import (
    FileFormat,
    IGNProduct,
    ProductCatalog,
    ProductCategory,
    TerritoryCode,
    get_default_catalog,
)
from pgboundary.schema_config import SchemaConfig, StorageMode

__version__ = "0.4.0"
__all__ = [
    # Loaders
    "AdminExpressLoader",
    "FileFormat",
    "IGNProduct",
    # Produits
    "ProductCatalog",
    "ProductCategory",
    "ProductLoader",
    "SchemaConfig",
    # Configuration
    "Settings",
    "StorageMode",
    "TerritoryCode",
    # Version
    "__version__",
    "get_default_catalog",
]
