"""Modèle de catalogue des produits IGN.

Ce module définit les structures de données pour décrire les produits
géographiques disponibles sur le géoportail IGN.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Iterator


class FileFormat(StrEnum):
    """Formats de fichiers disponibles."""

    SHP = "shp"
    GPKG = "gpkg"
    CSV = "csv"


class ProductCategory(StrEnum):
    """Catégories de produits IGN."""

    ADMIN = "administrative"  # Limites administratives
    STATS = "statistics"  # Données statistiques (IRIS)
    ELECTORAL = "electoral"  # Circonscriptions électorales
    LAND = "landcover"  # Occupation du sol (forêt, BCAE)
    ADDRESS = "address"  # Adresses
    CARTO = "cartography"  # Données cartographiques


class GeometryType(StrEnum):
    """Types de géométrie supportés."""

    POINT = "Point"
    MULTIPOINT = "MultiPoint"
    LINESTRING = "LineString"
    MULTILINESTRING = "MultiLineString"
    POLYGON = "Polygon"
    MULTIPOLYGON = "MultiPolygon"


class LayerConfig(BaseModel):
    """Configuration d'une couche de données.

    Attributes:
        name: Nom technique de la couche (ex: REGION, COMMUNE).
        table_key: Clé pour le mapping de table dans la configuration.
        geometry_type: Type de géométrie de la couche.
        description_fr: Description en français.
        description_en: Description en anglais.
        optional: Si True, la couche peut ne pas être présente dans le produit.
    """

    name: str = Field(..., description="Nom technique de la couche")
    table_key: str = Field(..., description="Clé pour le mapping de table")
    geometry_type: GeometryType = Field(
        default=GeometryType.MULTIPOLYGON,
        description="Type de géométrie",
    )
    description_fr: str = Field(default="", description="Description en français")
    description_en: str = Field(default="", description="Description en anglais")
    optional: bool = Field(default=False, description="Couche optionnelle")


class TerritoryCode(StrEnum):
    """Codes des territoires disponibles.

    Ces codes correspondent aux codes IGN utilisés dans les URLs de téléchargement.
    """

    FRA = "FRA"  # France entière (métropole + DROM)
    FXX = "FXX"  # France métropolitaine uniquement
    GLP = "GLP"  # Guadeloupe
    MTQ = "MTQ"  # Martinique
    GUF = "GUF"  # Guyane française
    REU = "REU"  # La Réunion
    MYT = "MYT"  # Mayotte


FRENCH_DEPARTMENTS: list[str] = [
    *(f"{i:02d}" for i in range(1, 20)),  # 01-19
    "2A",
    "2B",  # Corse
    *(f"{i}" for i in range(21, 96)),  # 21-95
    "971",
    "972",
    "973",
    "974",
    "976",  # DROM (hors 975 Saint-Pierre-et-Miquelon)
]
"""Liste des 101 codes départements français."""


def validate_department_code(code: str) -> bool:
    """Vérifie si un code département est valide.

    Args:
        code: Code département à vérifier.

    Returns:
        True si le code est valide.
    """
    return code in FRENCH_DEPARTMENTS


class IGNProduct(BaseModel):
    """Définition d'un produit IGN.

    Attributes:
        id: Identifiant unique du produit (ex: admin-express-cog).
        name: Nom officiel du produit.
        description_fr: Description en français.
        description_en: Description en anglais.
        category: Catégorie du produit.
        formats: Liste des formats de fichiers disponibles.
        territories: Liste des territoires disponibles.
        layers: Liste des couches de données disponibles.
        url_template: Template d'URL pour le téléchargement.
        version_pattern: Pattern de version (ex: "3-2", "{year}").
        archive_extension: Extension de l'archive (7z par défaut).
        size_mb: Taille approximative en Mo (pour France entière, format SHP).
    """

    id: str = Field(..., description="Identifiant unique du produit")
    name: str = Field(..., description="Nom officiel du produit")
    api_product: str | None = Field(default=None, description="Nom API Atom IGN")
    provider: str = Field(default="IGN", description="Fournisseur (IGN, data.gouv.fr, etc.)")
    description_fr: str = Field(..., description="Description en français")
    description_en: str = Field(..., description="Description en anglais")
    category: ProductCategory = Field(..., description="Catégorie du produit")
    formats: list[FileFormat] = Field(..., description="Formats disponibles")
    territories: list[TerritoryCode] = Field(..., description="Territoires disponibles")
    layers: list[LayerConfig] = Field(..., description="Couches disponibles")
    url_template: str = Field(..., description="Template URL pour le téléchargement")
    version_pattern: str = Field(..., description="Pattern de version")
    archive_extension: str = Field(default="7z", description="Extension de l'archive")
    last_date: str | None = Field(
        default=None,
        description="Dernière date de publication connue (YYYY-MM-DD ou YYYY)",
    )
    available_dates: list[str] = Field(
        default_factory=list,
        description="Liste des dates de publication connues (YYYY-MM-DD ou YYYY)",
    )
    size_mb: float | None = Field(
        default=None, description="Taille approximative en Mo (France entière, SHP)"
    )
    department_url_template: str | None = Field(
        default=None,
        description="Template URL pour le téléchargement par département (avec placeholder {department})",
    )

    @property
    def supports_department_download(self) -> bool:
        """Indique si le produit supporte le téléchargement par département."""
        return self.department_url_template is not None

    def get_layer(self, name: str) -> LayerConfig | None:
        """Retourne la configuration d'une couche par son nom.

        Args:
            name: Nom de la couche.

        Returns:
            Configuration de la couche ou None si non trouvée.
        """
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def get_layer_names(self) -> list[str]:
        """Retourne la liste des noms de couches.

        Returns:
            Liste des noms de couches.
        """
        return [layer.name for layer in self.layers]

    def supports_format(self, format: FileFormat) -> bool:
        """Vérifie si le produit supporte un format donné.

        Args:
            format: Format à vérifier.

        Returns:
            True si le format est supporté.
        """
        return format in self.formats

    def supports_territory(self, territory: TerritoryCode) -> bool:
        """Vérifie si le produit supporte un territoire donné.

        Args:
            territory: Territoire à vérifier.

        Returns:
            True si le territoire est supporté.
        """
        return territory in self.territories

    def get_size_formatted(self) -> str:
        """Retourne la taille formatée avec l'unité appropriée.

        Returns:
            Taille formatée (ex: "500 Mo", "1.2 Go", "50 Ko") ou "?" si inconnue.
        """
        if self.size_mb is None:
            return "?"

        if self.size_mb >= 1000:
            return f"{self.size_mb / 1000:.1f} Go"
        elif self.size_mb >= 1:
            return f"{self.size_mb:.0f} Mo"
        else:
            return f"{self.size_mb * 1000:.0f} Ko"


class ProductCatalog:
    """Catalogue des produits IGN disponibles.

    Cette classe gère l'enregistrement et la recherche de produits IGN.
    Elle est utilisée comme point d'entrée pour découvrir les produits disponibles.
    """

    def __init__(self) -> None:
        """Initialise un catalogue vide."""
        self._products: dict[str, IGNProduct] = {}

    def register(self, product: IGNProduct) -> None:
        """Enregistre un produit dans le catalogue.

        Args:
            product: Produit à enregistrer.
        """
        self._products[product.id] = product

    def register_many(self, products: list[IGNProduct]) -> None:
        """Enregistre plusieurs produits dans le catalogue.

        Args:
            products: Liste de produits à enregistrer.
        """
        for product in products:
            self.register(product)

    def get(self, product_id: str) -> IGNProduct | None:
        """Retourne un produit par son identifiant.

        Args:
            product_id: Identifiant du produit.

        Returns:
            Produit ou None si non trouvé.
        """
        return self._products.get(product_id)

    def list_by_category(self, category: ProductCategory) -> list[IGNProduct]:
        """Liste les produits d'une catégorie donnée.

        Args:
            category: Catégorie de produits.

        Returns:
            Liste des produits de cette catégorie.
        """
        return [p for p in self._products.values() if p.category == category]

    def list_all(self) -> list[IGNProduct]:
        """Liste tous les produits enregistrés.

        Returns:
            Liste de tous les produits.
        """
        return list(self._products.values())

    def list_ids(self) -> list[str]:
        """Liste les identifiants de tous les produits.

        Returns:
            Liste des identifiants.
        """
        return list(self._products.keys())

    def __iter__(self) -> Iterator[IGNProduct]:
        """Itère sur les produits du catalogue."""
        return iter(self._products.values())

    def __len__(self) -> int:
        """Retourne le nombre de produits."""
        return len(self._products)

    def __contains__(self, product_id: str) -> bool:
        """Vérifie si un produit existe dans le catalogue."""
        return product_id in self._products


def get_default_catalog() -> ProductCatalog:
    """Retourne le catalogue par défaut avec tous les produits.

    Charge les définitions depuis les fichiers YAML dans sources/,
    puis enrichit les produits IGN avec les données SQLite si disponibles.

    Returns:
        Catalogue initialisé avec tous les produits.
    """
    from pgboundary.sources.loader import load_sources

    catalog = load_sources()
    _enrich_from_sqlite(catalog)
    return catalog


def _enrich_from_sqlite(catalog: ProductCatalog) -> None:
    """Enrichit les produits du catalogue avec les données SQLite.

    Pour chaque produit ayant un `api_product`, cherche dans la base
    SQLite les dates disponibles et la dernière date, puis met à jour
    le produit en conséquence. Dégradation gracieuse si la base n'existe pas.

    Args:
        catalog: Catalogue à enrichir (modifié sur place).
    """
    import logging

    from pgboundary.config import Settings

    logger = logging.getLogger(__name__)

    try:
        settings = Settings()
        db_path = settings.catalog_db
    except Exception:
        return

    if not db_path.exists():
        return

    try:
        from pgboundary.products.catalog_db import CatalogDatabase

        with CatalogDatabase(db_path) as db:
            for product in catalog:
                if not product.api_product:
                    continue

                dates = db.get_available_dates(product.api_product)
                if dates:
                    product.available_dates = dates
                    latest = db.get_latest_date(product.api_product)
                    if latest:
                        product.last_date = latest
    except Exception:
        logger.debug("Impossible d'enrichir le catalogue depuis SQLite", exc_info=True)


def get_admin_express_product(variant: str = "cog") -> IGNProduct | None:
    """Retourne un produit Admin Express par sa variante.

    Args:
        variant: Variante du produit:
            - "base" ou "express": ADMIN EXPRESS
            - "cog": ADMIN EXPRESS COG (défaut)
            - "carto": ADMIN EXPRESS COG CARTO
            - "pe": ADMIN EXPRESS COG CARTO PE
            - "plus" ou "plus-pe": ADMIN EXPRESS COG CARTO PLUS PE

    Returns:
        Produit correspondant ou None si non trouvé.
    """
    variant_mapping = {
        "base": "admin-express",
        "express": "admin-express",
        "cog": "admin-express-cog",
        "carto": "admin-express-cog-carto",
        "pe": "admin-express-cog-carto-pe",
        "plus": "admin-express-cog-carto-plus-pe",
        "plus-pe": "admin-express-cog-carto-plus-pe",
    }

    product_id = variant_mapping.get(variant.lower())
    if product_id is None:
        return None

    catalog = get_default_catalog()
    return catalog.get(product_id)


def get_codes_postaux_product(variant: str = "ban") -> IGNProduct | None:
    """Retourne un produit codes postaux par sa variante.

    Args:
        variant: Variante du produit:
            - "ban" ou "contours": Contours calculés BAN (défaut)
            - "laposte", "hexaposte" ou "official": Base officielle La Poste
            - "geoclip" ou "fond": Fond de carte Géoclip
            - "generated", "voronoi" ou "computed": Génération Voronoï

    Returns:
        Produit correspondant ou None si non trouvé.
    """
    variant_mapping = {
        "ban": "codes-postaux-ban",
        "contours": "codes-postaux-ban",
        "laposte": "codes-postaux-laposte",
        "hexaposte": "codes-postaux-laposte",
        "official": "codes-postaux-laposte",
        "geoclip": "codes-postaux-geoclip",
        "fond": "codes-postaux-geoclip",
        "generated": "codes-postaux-generated",
        "voronoi": "codes-postaux-generated",
        "computed": "codes-postaux-generated",
    }

    product_id = variant_mapping.get(variant.lower())
    if product_id is None:
        return None

    catalog = get_default_catalog()
    return catalog.get(product_id)
