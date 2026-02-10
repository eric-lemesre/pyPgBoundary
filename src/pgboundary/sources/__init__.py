"""Sources de données géographiques.

Ce package contient les implémentations des sources de données
pour le téléchargement et l'extraction des données géographiques.

Les définitions de produits sont stockées en YAML dans les sous-répertoires.
"""

from pgboundary.sources.base import DataSource
from pgboundary.sources.ign import (
    ADMIN_EXPRESS_LAYERS,
    ADMIN_EXPRESS_URLS,
    IGNDataSource,
    Territory,
)
from pgboundary.sources.loader import load_sources, load_territory_crs

__all__ = [
    "ADMIN_EXPRESS_LAYERS",
    "ADMIN_EXPRESS_URLS",
    "DataSource",
    "IGNDataSource",
    "Territory",
    "load_sources",
    "load_territory_crs",
]
