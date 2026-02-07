"""Définitions des produits Admin Express IGN.

Ce module contient les configurations des 5 variantes du produit Admin Express:
- ADMIN EXPRESS : version simplifiée
- ADMIN EXPRESS COG : avec Code Officiel Géographique
- ADMIN EXPRESS COG CARTO : version cartographique avec chefs-lieux
- ADMIN EXPRESS COG CARTO PE : Petite Échelle
- ADMIN EXPRESS COG CARTO PLUS PE : Petite Échelle enrichie
"""

from __future__ import annotations

from pgboundary.products.catalog import (
    FileFormat,
    GeometryType,
    IGNProduct,
    LayerConfig,
    ProductCategory,
    TerritoryCode,
)

# Territoires disponibles pour Admin Express
ADMIN_EXPRESS_TERRITORIES = [
    TerritoryCode.FRA,
    TerritoryCode.FXX,
    TerritoryCode.GLP,
    TerritoryCode.MTQ,
    TerritoryCode.GUF,
    TerritoryCode.REU,
    TerritoryCode.MYT,
]

# Couches de base communes à toutes les variantes Admin Express
BASE_ADMIN_LAYERS = [
    LayerConfig(
        name="REGION",
        table_key="region",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Régions administratives",
        description_en="Administrative regions",
    ),
    LayerConfig(
        name="DEPARTEMENT",
        table_key="departement",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Départements",
        description_en="Departments",
    ),
    LayerConfig(
        name="ARRONDISSEMENT",
        table_key="arrondissement",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Arrondissements départementaux",
        description_en="Departmental districts",
    ),
    LayerConfig(
        name="EPCI",
        table_key="epci",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Établissements Publics de Coopération Intercommunale",
        description_en="Public Establishments for Intercommunal Cooperation",
    ),
    LayerConfig(
        name="COMMUNE",
        table_key="commune",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Communes",
        description_en="Municipalities",
    ),
    LayerConfig(
        name="COMMUNE_ASSOCIEE_OU_DELEGUEE",
        table_key="commune_associee_deleguee",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Communes associées ou déléguées",
        description_en="Associated or delegated municipalities",
    ),
]

# Couches supplémentaires pour les versions cartographiques
CARTO_LAYERS = [
    LayerConfig(
        name="CHFLIEU_COMMUNE",
        table_key="chef_lieu_commune",
        geometry_type=GeometryType.POINT,
        description_fr="Chefs-lieux de commune",
        description_en="Municipal capitals",
    ),
    LayerConfig(
        name="CHFLIEU_ARRONDISSEMENT_MUNICIPAL",
        table_key="chef_lieu_arrondissement_municipal",
        geometry_type=GeometryType.POINT,
        description_fr="Chefs-lieux d'arrondissement municipal",
        description_en="Municipal district capitals",
        optional=True,
    ),
]

# Couches pour arrondissements municipaux (Paris, Lyon, Marseille)
ARRONDISSEMENT_MUNICIPAL_LAYERS = [
    LayerConfig(
        name="ARRONDISSEMENT_MUNICIPAL",
        table_key="arrondissement_municipal",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Arrondissements municipaux (Paris, Lyon, Marseille)",
        description_en="Municipal districts (Paris, Lyon, Marseille)",
    ),
]

# Couches supplémentaires pour les versions PLUS (enrichies)
PLUS_LAYERS = [
    LayerConfig(
        name="CANTON",
        table_key="canton",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Cantons",
        description_en="Cantons",
    ),
    LayerConfig(
        name="COLLECTIVITE_TERRITORIALE",
        table_key="collectivite_territoriale",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Collectivités territoriales",
        description_en="Territorial collectivities",
        optional=True,
    ),
]


def _build_url_template(product_code: str) -> str:
    """Construit le template d'URL pour un produit Admin Express.

    Args:
        product_code: Code du produit (ex: ADMIN-EXPRESS-COG).

    Returns:
        Template d'URL avec placeholders.
    """
    return (
        f"https://data.geopf.fr/telechargement/download/{product_code}/"
        f"{product_code}_{{version}}__{{format}}_{{crs}}_{{territory}}_{{date}}/"
        f"{product_code}_{{version}}__{{format}}_{{crs}}_{{territory}}_{{date}}.7z"
    )


# Définitions des 5 variantes Admin Express
ADMIN_EXPRESS_PRODUCTS: list[IGNProduct] = [
    # 1. ADMIN EXPRESS - Version simplifiée
    IGNProduct(
        id="admin-express",
        name="ADMIN EXPRESS",
        description_fr=(
            "Limites administratives simplifiées de la France. "
            "Version de base sans le Code Officiel Géographique."
        ),
        description_en=(
            "Simplified administrative boundaries of France. "
            "Basic version without Official Geographic Code."
        ),
        category=ProductCategory.ADMIN,
        formats=[FileFormat.SHP, FileFormat.GPKG],
        territories=ADMIN_EXPRESS_TERRITORIES,
        layers=BASE_ADMIN_LAYERS.copy(),
        url_template=_build_url_template("ADMIN-EXPRESS"),
        version_pattern="3-2",
    ),
    # 2. ADMIN EXPRESS COG - Avec Code Officiel Géographique
    IGNProduct(
        id="admin-express-cog",
        name="ADMIN EXPRESS COG",
        description_fr=(
            "Limites administratives avec Code Officiel Géographique (COG). "
            "Référentiel officiel des codes communes et régions."
        ),
        description_en=(
            "Administrative boundaries with Official Geographic Code (COG). "
            "Official reference for municipality and region codes."
        ),
        category=ProductCategory.ADMIN,
        formats=[FileFormat.SHP, FileFormat.GPKG],
        territories=ADMIN_EXPRESS_TERRITORIES,
        layers=BASE_ADMIN_LAYERS.copy(),
        url_template=_build_url_template("ADMIN-EXPRESS-COG"),
        version_pattern="3-2",
    ),
    # 3. ADMIN EXPRESS COG CARTO - Version cartographique
    IGNProduct(
        id="admin-express-cog-carto",
        name="ADMIN EXPRESS COG CARTO",
        description_fr=(
            "Version cartographique avec chefs-lieux et arrondissements municipaux. "
            "Inclut les points représentatifs des communes."
        ),
        description_en=(
            "Cartographic version with administrative centers and municipal districts. "
            "Includes representative points for municipalities."
        ),
        category=ProductCategory.ADMIN,
        formats=[FileFormat.SHP, FileFormat.GPKG],
        territories=ADMIN_EXPRESS_TERRITORIES,
        layers=BASE_ADMIN_LAYERS + ARRONDISSEMENT_MUNICIPAL_LAYERS + CARTO_LAYERS,
        url_template=_build_url_template("ADMIN-EXPRESS-COG-CARTO"),
        version_pattern="3-2",
    ),
    # 4. ADMIN EXPRESS COG CARTO PE - Petite Échelle
    IGNProduct(
        id="admin-express-cog-carto-pe",
        name="ADMIN EXPRESS COG CARTO PE",
        description_fr=(
            "Version petite échelle pour cartes générales. "
            "Géométries simplifiées pour affichage à petite échelle."
        ),
        description_en=(
            "Small scale version for general maps. Simplified geometries for small-scale display."
        ),
        category=ProductCategory.ADMIN,
        formats=[FileFormat.SHP, FileFormat.GPKG],
        territories=ADMIN_EXPRESS_TERRITORIES,
        layers=BASE_ADMIN_LAYERS + ARRONDISSEMENT_MUNICIPAL_LAYERS + CARTO_LAYERS,
        url_template=_build_url_template("ADMIN-EXPRESS-COG-CARTO-PE"),
        version_pattern="3-2",
    ),
    # 5. ADMIN EXPRESS COG CARTO PLUS PE - Enrichie Petite Échelle
    IGNProduct(
        id="admin-express-cog-carto-plus-pe",
        name="ADMIN EXPRESS COG CARTO PLUS PE",
        description_fr=(
            "Version enrichie petite échelle avec cantons et collectivités territoriales. "
            "Contient le maximum de données administratives."
        ),
        description_en=(
            "Enriched small-scale version with cantons and territorial collectivities. "
            "Contains maximum administrative data."
        ),
        category=ProductCategory.ADMIN,
        formats=[FileFormat.SHP, FileFormat.GPKG],
        territories=ADMIN_EXPRESS_TERRITORIES,
        layers=(BASE_ADMIN_LAYERS + ARRONDISSEMENT_MUNICIPAL_LAYERS + CARTO_LAYERS + PLUS_LAYERS),
        url_template=_build_url_template("ADMIN-EXPRESS-COG-CARTO-PLUS-PE"),
        version_pattern="3-2",
    ),
]


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

    for product in ADMIN_EXPRESS_PRODUCTS:
        if product.id == product_id:
            return product

    return None
