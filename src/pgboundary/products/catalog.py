"""IGN product catalog model.

This module defines the data structures used to describe geographic
products available on the IGN geoportal.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Iterator


class FileFormat(StrEnum):
    """Available file formats."""

    SHP = "shp"
    GPKG = "gpkg"
    CSV = "csv"


class ProductCategory(StrEnum):
    """IGN product categories."""

    ADMIN = "administrative"  # Administrative boundaries
    STATS = "statistics"  # Statistical data (IRIS)
    ELECTORAL = "electoral"  # Electoral districts
    LAND = "landcover"  # Land cover (forest, BCAE)
    ADDRESS = "address"  # Addresses
    CARTO = "cartography"  # Cartographic data


class GeometryType(StrEnum):
    """Supported geometry types."""

    POINT = "Point"
    MULTIPOINT = "MultiPoint"
    LINESTRING = "LineString"
    MULTILINESTRING = "MultiLineString"
    POLYGON = "Polygon"
    MULTIPOLYGON = "MultiPolygon"


class LayerConfig(BaseModel):
    """Data layer configuration.

    Attributes:
        name: Technical name of the layer (e.g. REGION, COMMUNE).
        table_key: Key for the table mapping in the configuration.
        geometry_type: Geometry type of the layer.
        description_fr: Description in French.
        description_en: Description in English.
        optional: If True, the layer may not be present in the product.
    """

    name: str = Field(..., description="Technical name of the layer")
    table_key: str = Field(..., description="Key for the table mapping")
    geometry_type: GeometryType = Field(
        default=GeometryType.MULTIPOLYGON,
        description="Geometry type",
    )
    description_fr: str = Field(default="", description="Description in French")
    description_en: str = Field(default="", description="Description in English")
    optional: bool = Field(default=False, description="Optional layer")


class TerritoryCode(StrEnum):
    """Available territory codes.

    These codes correspond to the IGN codes used in download URLs.
    """

    FRA = "FRA"  # All of France (metropolitan + overseas)
    FXX = "FXX"  # Metropolitan France only
    GLP = "GLP"  # Guadeloupe
    MTQ = "MTQ"  # Martinique
    GUF = "GUF"  # French Guiana
    REU = "REU"  # Reunion
    MYT = "MYT"  # Mayotte


FRENCH_DEPARTMENTS: list[str] = [
    *(f"{i:02d}" for i in range(1, 20)),  # 01-19
    "2A",
    "2B",  # Corsica
    *(f"{i}" for i in range(21, 96)),  # 21-95
    "971",
    "972",
    "973",
    "974",
    "976",  # Overseas departments (excluding 975 Saint-Pierre-et-Miquelon)
]
"""List of the 101 French department codes."""


def validate_department_code(code: str) -> bool:
    """Check whether a department code is valid.

    Args:
        code: Department code to check.

    Returns:
        True if the code is valid.
    """
    return code in FRENCH_DEPARTMENTS


class IGNProduct(BaseModel):
    """Definition of an IGN product.

    Attributes:
        id: Unique product identifier (e.g. admin-express-cog).
        name: Official product name.
        description_fr: Description in French.
        description_en: Description in English.
        category: Product category.
        formats: List of available file formats.
        territories: List of available territories.
        layers: List of available data layers.
        url_template: URL template for downloading.
        version_pattern: Version pattern (e.g. "3-2", "{year}").
        archive_extension: Archive extension (7z by default).
        size_mb: Approximate size in MB (for all of France, SHP format).
    """

    id: str = Field(..., description="Unique product identifier")
    name: str = Field(..., description="Official product name")
    api_product: str | None = Field(default=None, description="IGN Atom API name")
    provider: str = Field(default="IGN", description="Provider (IGN, data.gouv.fr, etc.)")
    description_fr: str = Field(..., description="Description in French")
    description_en: str = Field(..., description="Description in English")
    category: ProductCategory = Field(..., description="Product category")
    formats: list[FileFormat] = Field(..., description="Available formats")
    territories: list[TerritoryCode] = Field(..., description="Available territories")
    layers: list[LayerConfig] = Field(..., description="Available layers")
    url_template: str = Field(..., description="URL template for downloading")
    version_pattern: str = Field(..., description="Version pattern")
    archive_extension: str = Field(default="7z", description="Archive extension")
    last_date: str | None = Field(
        default=None,
        description="Latest known publication date (YYYY-MM-DD or YYYY)",
    )
    available_dates: list[str] = Field(
        default_factory=list,
        description="List of known publication dates (YYYY-MM-DD or YYYY)",
    )
    size_mb: float | None = Field(
        default=None, description="Approximate size in MB (all of France, SHP)"
    )
    department_url_template: str | None = Field(
        default=None,
        description="URL template for per-department download (with {department} placeholder)",
    )

    @property
    def supports_department_download(self) -> bool:
        """Indicate whether the product supports per-department download."""
        return self.department_url_template is not None

    def get_layer(self, name: str) -> LayerConfig | None:
        """Return the configuration of a layer by its name.

        Args:
            name: Name of the layer.

        Returns:
            Layer configuration, or None if not found.
        """
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def get_layer_names(self) -> list[str]:
        """Return the list of layer names.

        Returns:
            List of layer names.
        """
        return [layer.name for layer in self.layers]

    def supports_format(self, format: FileFormat) -> bool:
        """Check whether the product supports a given format.

        Args:
            format: Format to check.

        Returns:
            True if the format is supported.
        """
        return format in self.formats

    def supports_territory(self, territory: TerritoryCode) -> bool:
        """Check whether the product supports a given territory.

        Args:
            territory: Territory to check.

        Returns:
            True if the territory is supported.
        """
        return territory in self.territories

    def get_size_formatted(self) -> str:
        """Return the size formatted with the appropriate unit.

        Returns:
            Formatted size (e.g. "500 Mo", "1.2 Go", "50 Ko") or "?" if unknown.
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
    """Catalog of available IGN products.

    This class manages the registration and lookup of IGN products.
    It serves as the entry point for discovering available products.
    """

    def __init__(self) -> None:
        """Initialize an empty catalog."""
        self._products: dict[str, IGNProduct] = {}

    def register(self, product: IGNProduct) -> None:
        """Register a product in the catalog.

        Args:
            product: Product to register.
        """
        self._products[product.id] = product

    def register_many(self, products: list[IGNProduct]) -> None:
        """Register multiple products in the catalog.

        Args:
            products: List of products to register.
        """
        for product in products:
            self.register(product)

    def get(self, product_id: str) -> IGNProduct | None:
        """Return a product by its identifier.

        Args:
            product_id: Product identifier.

        Returns:
            Product, or None if not found.
        """
        return self._products.get(product_id)

    def list_by_category(self, category: ProductCategory) -> list[IGNProduct]:
        """List products belonging to a given category.

        Args:
            category: Product category.

        Returns:
            List of products in that category.
        """
        return [p for p in self._products.values() if p.category == category]

    def list_all(self) -> list[IGNProduct]:
        """List all registered products.

        Returns:
            List of all products.
        """
        return list(self._products.values())

    def list_ids(self) -> list[str]:
        """List the identifiers of all products.

        Returns:
            List of identifiers.
        """
        return list(self._products.keys())

    def __iter__(self) -> Iterator[IGNProduct]:
        """Iterate over the products in the catalog."""
        return iter(self._products.values())

    def __len__(self) -> int:
        """Return the number of products."""
        return len(self._products)

    def __contains__(self, product_id: str) -> bool:
        """Check whether a product exists in the catalog."""
        return product_id in self._products


def get_default_catalog() -> ProductCatalog:
    """Return the default catalog with all products.

    Loads definitions from YAML files in sources/, then enriches
    IGN products with SQLite data if available.

    Returns:
        Catalog initialized with all products.
    """
    from pgboundary.sources.loader import load_sources

    catalog = load_sources()
    _enrich_from_sqlite(catalog)
    return catalog


def _enrich_from_sqlite(catalog: ProductCatalog) -> None:
    """Enrich catalog products with SQLite data.

    For each product that has an `api_product`, looks up available dates
    and the latest date in the SQLite database, then updates the product
    accordingly. Degrades gracefully if the database does not exist.

    Args:
        catalog: Catalog to enrich (modified in place).
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
    """Return an Admin Express product by its variant.

    Args:
        variant: Product variant:
            - "base" or "express": ADMIN EXPRESS
            - "cog": ADMIN EXPRESS COG (default)
            - "carto": ADMIN EXPRESS COG CARTO
            - "pe": ADMIN EXPRESS COG CARTO PE
            - "plus" or "plus-pe": ADMIN EXPRESS COG CARTO PLUS PE

    Returns:
        Matching product, or None if not found.
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
    """Return a postal codes product by its variant.

    Args:
        variant: Product variant:
            - "ban" or "contours": BAN computed contours (default)
            - "laposte", "hexaposte" or "official": Official La Poste database
            - "geoclip" or "fond": Geoclip basemap
            - "generated", "voronoi" or "computed": Voronoi generation

    Returns:
        Matching product, or None if not found.
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
