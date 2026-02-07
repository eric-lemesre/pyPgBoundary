"""Loaders pour charger les données géographiques dans PostgreSQL.

Ce package contient les loaders pour différents produits:
- ProductLoader: loader générique pour tout produit IGN
- AdminExpressLoader: loader spécialisé pour Admin Express
- CodesPostauxLoader: loader pour les codes postaux (multiples sources)
"""

from pgboundary.loaders.admin_express import AdminExpressLoader
from pgboundary.loaders.base import BaseLoader
from pgboundary.loaders.codes_postaux import CodesPostauxLoader
from pgboundary.loaders.product_loader import ProductLoader

__all__ = [
    "AdminExpressLoader",
    "BaseLoader",
    "CodesPostauxLoader",
    "ProductLoader",
]
