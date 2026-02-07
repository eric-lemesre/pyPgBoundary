"""
pyPgBoundary - Module Python pour charger les limites administratives françaises dans PostgreSQL/PostGIS.

Ce module permet de télécharger et charger les données Admin Express de l'IGN
dans une base de données PostgreSQL avec l'extension PostGIS.
"""

from pgboundary.config import Settings
from pgboundary.loaders.admin_express import AdminExpressLoader
from pgboundary.schema_config import SchemaConfig, StorageMode

__version__ = "0.1.0"
__all__ = ["AdminExpressLoader", "SchemaConfig", "Settings", "StorageMode", "__version__"]
