"""Sources de données géographiques.

Ce package contient les implémentations des sources de données
pour le téléchargement et l'extraction des données géographiques.
"""

from pgboundary.sources.base import DataSource
from pgboundary.sources.ign import (
    ADMIN_EXPRESS_LAYERS,
    ADMIN_EXPRESS_URLS,
    IGNDataSource,
    Territory,
)

__all__ = [
    "ADMIN_EXPRESS_LAYERS",
    "ADMIN_EXPRESS_URLS",
    "DataSource",
    "IGNDataSource",
    "Territory",
]
