"""
pyPgBoundary - Python module for loading IGN geographic data into PostgreSQL/PostGIS.

This module allows downloading and loading IGN geographic data
into a PostgreSQL database with the PostGIS extension.

Supported products:
- Admin Express (5 variants)
- Contours IRIS
- BD FORET and Masque FORET
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
    # Products
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
