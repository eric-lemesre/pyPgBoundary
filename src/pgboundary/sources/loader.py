"""Product definition loader from YAML files.

This module traverses YAML files in the sources/ directory
and converts them into IGNProduct objects for the catalog.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from pgboundary.products.catalog import (
    FileFormat,
    GeometryType,
    IGNProduct,
    LayerConfig,
    ProductCatalog,
    ProductCategory,
    TerritoryCode,
)

logger = logging.getLogger(__name__)

# Root directory for YAML sources
SOURCES_DIR = Path(__file__).parent

# Category string to enum mapping
CATEGORY_MAPPING: dict[str, ProductCategory] = {
    "administrative": ProductCategory.ADMIN,
    "statistics": ProductCategory.STATS,
    "electoral": ProductCategory.ELECTORAL,
    "landcover": ProductCategory.LAND,
    "address": ProductCategory.ADDRESS,
    "cartography": ProductCategory.CARTO,
}

# Format string to enum mapping
FORMAT_MAPPING: dict[str, FileFormat] = {
    "shp": FileFormat.SHP,
    "gpkg": FileFormat.GPKG,
    "csv": FileFormat.CSV,
}

# Geometry type string to enum mapping
GEOMETRY_MAPPING: dict[str, GeometryType] = {
    "Point": GeometryType.POINT,
    "MultiPoint": GeometryType.MULTIPOINT,
    "LineString": GeometryType.LINESTRING,
    "MultiLineString": GeometryType.MULTILINESTRING,
    "Polygon": GeometryType.POLYGON,
    "MultiPolygon": GeometryType.MULTIPOLYGON,
}

# Territory string to enum mapping
TERRITORY_MAPPING: dict[str, TerritoryCode] = {
    "FRA": TerritoryCode.FRA,
    "FXX": TerritoryCode.FXX,
    "GLP": TerritoryCode.GLP,
    "MTQ": TerritoryCode.MTQ,
    "GUF": TerritoryCode.GUF,
    "REU": TerritoryCode.REU,
    "MYT": TerritoryCode.MYT,
}


def load_territory_crs(territories_dir: Path | None = None) -> dict[str, str]:
    """Load the territory to CRS mapping from YAML files.

    Args:
        territories_dir: Directory containing the territory files.
            Defaults to sources/territories/.

    Returns:
        Dictionary {territory_code: crs}.
    """
    if territories_dir is None:
        territories_dir = SOURCES_DIR / "territories"

    crs_mapping: dict[str, str] = {}

    for yml_path in territories_dir.glob("*.yml"):
        with yml_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data and "territories" in data:
            for code, info in data["territories"].items():
                crs_mapping[code] = info["crs"]

    return crs_mapping


def _parse_layer(layer_data: dict[str, Any]) -> LayerConfig:
    """Parse a YAML dictionary into a LayerConfig.

    Args:
        layer_data: YAML data for the layer.

    Returns:
        Layer configuration.
    """
    description = layer_data.get("description", {})
    if isinstance(description, str):
        description_fr = description
        description_en = ""
    else:
        description_fr = description.get("fr", "")
        description_en = description.get("en", "")

    return LayerConfig(
        name=layer_data["name"],
        table_key=layer_data["table_key"],
        geometry_type=GEOMETRY_MAPPING.get(
            layer_data.get("geometry_type", "MultiPolygon"),
            GeometryType.MULTIPOLYGON,
        ),
        description_fr=description_fr,
        description_en=description_en,
        optional=layer_data.get("optional", False),
    )


def _parse_product(data: dict[str, Any]) -> IGNProduct:
    """Parse a YAML dictionary into an IGNProduct.

    Args:
        data: YAML data for the product.

    Returns:
        IGN product.
    """
    description = data.get("description", {})
    if isinstance(description, str):
        description_fr = description
        description_en = ""
    else:
        description_fr = description.get("fr", "")
        description_en = description.get("en", "")

    # Clean url_template (YAML multi-line blocks add extra spaces)
    url_template = data["url_template"].replace(" ", "").strip()

    # Clean department_url_template (same treatment)
    department_url_template = data.get("department_url_template")
    if department_url_template:
        department_url_template = department_url_template.replace(" ", "").strip()

    category_str = data.get("category", "")
    category = CATEGORY_MAPPING.get(category_str)
    if category is None:
        raise ValueError(f"Catégorie inconnue: {category_str}")

    formats = [FORMAT_MAPPING[f] for f in data.get("formats", [])]
    territories = [TERRITORY_MAPPING[t] for t in data.get("territories", [])]
    layers = [_parse_layer(layer) for layer in data.get("layers", [])]

    return IGNProduct(
        id=data["id"],
        name=data["name"],
        api_product=data.get("api_product"),
        provider=data.get("provider", "IGN"),
        description_fr=description_fr,
        description_en=description_en,
        category=category,
        formats=formats,
        territories=territories,
        layers=layers,
        url_template=url_template,
        version_pattern=str(data.get("version", "")),
        archive_extension=data.get("archive_extension", "7z"),
        last_date=data.get("last_date"),
        available_dates=[str(d) for d in data.get("available_dates", [])],
        size_mb=data.get("size_mb"),
        department_url_template=department_url_template,
    )


def load_products(sources_dir: Path | None = None) -> list[IGNProduct]:
    """Load all products from YAML files.

    Recursively traverses the subdirectories of sources/ to
    find product definition .yml files.

    Args:
        sources_dir: Root directory for sources.
            Defaults to the module directory.

    Returns:
        List of loaded IGN products.
    """
    if sources_dir is None:
        sources_dir = SOURCES_DIR

    products: list[IGNProduct] = []

    # Directories containing products (exclude territories/)
    product_dirs = [
        "administrative",
        "statistical",
        "electoral",
        "address",
        "cartography",
        "landcover",
    ]

    for subdir in product_dirs:
        dir_path = sources_dir / subdir
        if not dir_path.exists():
            continue

        for yml_path in sorted(dir_path.glob("**/*.yml")):
            try:
                with yml_path.open(encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if data and "id" in data:
                    product = _parse_product(data)
                    products.append(product)
                    logger.debug("Produit chargé: %s depuis %s", product.id, yml_path)

            except Exception:
                logger.exception("Erreur lors du chargement de %s", yml_path)

    return products


def load_sources(sources_dir: Path | None = None) -> ProductCatalog:
    """Load YAML sources and return a product catalog.

    This is the main entry point for obtaining the catalog
    from YAML definitions.

    Args:
        sources_dir: Root directory for sources.

    Returns:
        Catalog initialized with all YAML products.
    """
    products = load_products(sources_dir)
    catalog = ProductCatalog()
    catalog.register_many(products)
    return catalog
