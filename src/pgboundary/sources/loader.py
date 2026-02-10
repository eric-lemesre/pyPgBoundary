"""Chargeur de définitions de produits depuis les fichiers YAML.

Ce module parcourt les fichiers YAML dans le répertoire sources/
et les convertit en objets IGNProduct pour le catalogue.
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

# Répertoire racine des sources YAML
SOURCES_DIR = Path(__file__).parent

# Mapping catégorie string → enum
CATEGORY_MAPPING: dict[str, ProductCategory] = {
    "administrative": ProductCategory.ADMIN,
    "statistics": ProductCategory.STATS,
    "electoral": ProductCategory.ELECTORAL,
    "landcover": ProductCategory.LAND,
    "address": ProductCategory.ADDRESS,
    "cartography": ProductCategory.CARTO,
}

# Mapping format string → enum
FORMAT_MAPPING: dict[str, FileFormat] = {
    "shp": FileFormat.SHP,
    "gpkg": FileFormat.GPKG,
}

# Mapping geometry type string → enum
GEOMETRY_MAPPING: dict[str, GeometryType] = {
    "Point": GeometryType.POINT,
    "MultiPoint": GeometryType.MULTIPOINT,
    "LineString": GeometryType.LINESTRING,
    "MultiLineString": GeometryType.MULTILINESTRING,
    "Polygon": GeometryType.POLYGON,
    "MultiPolygon": GeometryType.MULTIPOLYGON,
}

# Mapping territoire string → enum
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
    """Charge le mapping territoire → CRS depuis les fichiers YAML.

    Args:
        territories_dir: Répertoire contenant les fichiers territoires.
            Par défaut, utilise sources/territories/.

    Returns:
        Dictionnaire {code_territoire: crs}.
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
    """Parse un dictionnaire YAML en LayerConfig.

    Args:
        layer_data: Données YAML de la couche.

    Returns:
        Configuration de couche.
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
    """Parse un dictionnaire YAML en IGNProduct.

    Args:
        data: Données YAML du produit.

    Returns:
        Produit IGN.
    """
    description = data.get("description", {})
    if isinstance(description, str):
        description_fr = description
        description_en = ""
    else:
        description_fr = description.get("fr", "")
        description_en = description.get("en", "")

    # Nettoyage du url_template (les blocs YAML multi-lignes ajoutent des espaces)
    url_template = data["url_template"].replace("\n", "").replace("  ", "").strip()

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
        description_fr=description_fr,
        description_en=description_en,
        category=category,
        formats=formats,
        territories=territories,
        layers=layers,
        url_template=url_template,
        version_pattern=str(data.get("version", "")),
        archive_extension=data.get("archive_extension", "7z"),
        size_mb=data.get("size_mb"),
    )


def load_products(sources_dir: Path | None = None) -> list[IGNProduct]:
    """Charge tous les produits depuis les fichiers YAML.

    Parcourt récursivement les sous-répertoires de sources/ pour
    trouver les fichiers .yml de définition de produits.

    Args:
        sources_dir: Répertoire racine des sources.
            Par défaut, utilise le répertoire du module.

    Returns:
        Liste des produits IGN chargés.
    """
    if sources_dir is None:
        sources_dir = SOURCES_DIR

    products: list[IGNProduct] = []

    # Répertoires contenant des produits (exclure territories/)
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
    """Charge les sources YAML et retourne un catalogue de produits.

    C'est le point d'entrée principal pour obtenir le catalogue
    depuis les définitions YAML.

    Args:
        sources_dir: Répertoire racine des sources.

    Returns:
        Catalogue initialisé avec tous les produits YAML.
    """
    products = load_products(sources_dir)
    catalog = ProductCatalog()
    catalog.register_many(products)
    return catalog
