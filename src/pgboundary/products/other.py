"""Définitions des autres produits IGN.

Ce module contient les configurations des produits IGN autres qu'Admin Express:
- Contours IRIS : découpage statistique infra-communal
- BD FORÊT : occupation du sol forestier
- BD CARTO : base cartographique multi-thèmes
- ADRESSE PREMIUM : points adresse enrichis
- BAN PLUS : Base Adresse Nationale enrichie
- BCAE : Bonnes Conditions Agricoles et Environnementales
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

# Territoires standard (métropole + DROM)
ALL_TERRITORIES = [
    TerritoryCode.FRA,
    TerritoryCode.FXX,
    TerritoryCode.GLP,
    TerritoryCode.MTQ,
    TerritoryCode.GUF,
    TerritoryCode.REU,
    TerritoryCode.MYT,
]

# Territoires France métropolitaine uniquement
METROPOLITAN_TERRITORIES = [
    TerritoryCode.FRA,
    TerritoryCode.FXX,
]


# =============================================================================
# CONTOURS IRIS
# =============================================================================
IRIS_LAYERS = [
    LayerConfig(
        name="IRIS_GE",
        table_key="iris",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Contours IRIS (Îlots Regroupés pour l'Information Statistique)",
        description_en="IRIS contours (Aggregated Units for Statistical Information)",
    ),
]

CONTOURS_IRIS = IGNProduct(
    id="contours-iris",
    name="Contours... IRIS",
    description_fr=(
        "Îlots Regroupés pour l'Information Statistique - découpage infra-communal "
        "de l'INSEE pour les communes de plus de 10 000 habitants."
    ),
    description_en=(
        "Aggregated Units for Statistical Information - sub-municipal division "
        "from INSEE for municipalities with more than 10,000 inhabitants."
    ),
    category=ProductCategory.STATS,
    formats=[FileFormat.SHP, FileFormat.GPKG],
    territories=METROPOLITAN_TERRITORIES,
    layers=IRIS_LAYERS,
    url_template=(
        "https://data.geopf.fr/telechargement/download/CONTOURS-IRIS/"
        "CONTOURS-IRIS_3-0__{format}_{crs}_{territory}_{date}/"
        "CONTOURS-IRIS_3-0__{format}_{crs}_{territory}_{date}.7z"
    ),
    version_pattern="3-0",
    size_mb=150,
)


# =============================================================================
# BD FORÊT
# =============================================================================
BD_FORET_LAYERS = [
    LayerConfig(
        name="FORMATION_VEGETALE",
        table_key="formation_vegetale",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Formations végétales forestières",
        description_en="Forest vegetation formations",
    ),
]

BD_FORET = IGNProduct(
    id="bd-foret",
    name="BD FORÊT",
    description_fr=(
        "Base de données forestière - occupation du sol des forêts et formations "
        "végétales ligneuses. Mise à jour par département."
    ),
    description_en=(
        "Forest database - forest land cover and woody vegetation formations. "
        "Updated by department."
    ),
    category=ProductCategory.LAND,
    formats=[FileFormat.SHP, FileFormat.GPKG],
    territories=METROPOLITAN_TERRITORIES,
    layers=BD_FORET_LAYERS,
    url_template=(
        "https://data.geopf.fr/telechargement/download/BD-FORET/"
        "BD-FORET_{version}__{format}_{crs}_{territory}_{date}/"
        "BD-FORET_{version}__{format}_{crs}_{territory}_{date}.7z"
    ),
    version_pattern="2-0",
    size_mb=2500,
)


# =============================================================================
# MASQUE FORÊT
# =============================================================================
MASQUE_FORET_LAYERS = [
    LayerConfig(
        name="MASQUE_FORET",
        table_key="masque_foret",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Masque des zones forestières",
        description_en="Forest area mask",
    ),
]

MASQUE_FORET = IGNProduct(
    id="masque-foret",
    name="MASQUE FORÊT",
    description_fr=(
        "Masque simplifié des zones forestières de France. "
        "Dérivé de la BD FORÊT pour visualisation à petite échelle."
    ),
    description_en=(
        "Simplified mask of French forest areas. "
        "Derived from BD FORÊT for small-scale visualization."
    ),
    category=ProductCategory.LAND,
    formats=[FileFormat.SHP, FileFormat.GPKG],
    territories=METROPOLITAN_TERRITORIES,
    layers=MASQUE_FORET_LAYERS,
    url_template=(
        "https://data.geopf.fr/telechargement/download/MASQUE-FORET/"
        "MASQUE-FORET_{version}__{format}_{crs}_{territory}_{date}/"
        "MASQUE-FORET_{version}__{format}_{crs}_{territory}_{date}.7z"
    ),
    version_pattern="2-0",
    size_mb=300,
)


# =============================================================================
# BD CARTO
# =============================================================================
BD_CARTO_LAYERS = [
    LayerConfig(
        name="COMMUNE",
        table_key="commune_carto",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Communes (BD CARTO)",
        description_en="Municipalities (BD CARTO)",
    ),
    LayerConfig(
        name="LIMITE_ADMINISTRATIVE",
        table_key="limite_administrative",
        geometry_type=GeometryType.MULTILINESTRING,
        description_fr="Limites administratives linéaires",
        description_en="Linear administrative boundaries",
    ),
    LayerConfig(
        name="ZONE_D_ACTIVITE",
        table_key="zone_activite",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Zones d'activité",
        description_en="Activity zones",
        optional=True,
    ),
    LayerConfig(
        name="ZONE_D_HABITATION",
        table_key="zone_habitation",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Zones d'habitation",
        description_en="Residential zones",
        optional=True,
    ),
    LayerConfig(
        name="AERODROME",
        table_key="aerodrome",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Aérodromes",
        description_en="Airfields",
        optional=True,
    ),
    LayerConfig(
        name="CIMETIERE",
        table_key="cimetiere",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Cimetières",
        description_en="Cemeteries",
        optional=True,
    ),
    LayerConfig(
        name="CONSTRUCTION_SURFACIQUE",
        table_key="construction_surfacique",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Constructions surfaciques",
        description_en="Surface constructions",
        optional=True,
    ),
    LayerConfig(
        name="TERRAIN_DE_SPORT",
        table_key="terrain_sport",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Terrains de sport",
        description_en="Sports fields",
        optional=True,
    ),
]

BD_CARTO = IGNProduct(
    id="bd-carto",
    name="BD CARTO",
    description_fr=(
        "Base cartographique multi-thèmes pour cartes moyennes échelles. "
        "Contient les limites administratives, zones d'activité, équipements."
    ),
    description_en=(
        "Multi-theme cartographic database for medium-scale maps. "
        "Contains administrative boundaries, activity zones, facilities."
    ),
    category=ProductCategory.CARTO,
    formats=[FileFormat.SHP, FileFormat.GPKG],
    territories=ALL_TERRITORIES,
    layers=BD_CARTO_LAYERS,
    url_template=(
        "https://data.geopf.fr/telechargement/download/BD-CARTO/"
        "BD-CARTO_{version}__{format}_{crs}_{territory}_{date}/"
        "BD-CARTO_{version}__{format}_{crs}_{territory}_{date}.7z"
    ),
    version_pattern="4-0",
    size_mb=1200,
)


# =============================================================================
# ADRESSE PREMIUM
# =============================================================================
ADRESSE_PREMIUM_LAYERS = [
    LayerConfig(
        name="ADRESSE",
        table_key="adresse",
        geometry_type=GeometryType.POINT,
        description_fr="Points adresse géolocalisés",
        description_en="Geolocated address points",
    ),
]

ADRESSE_PREMIUM = IGNProduct(
    id="adresse-premium",
    name="ADRESSE PREMIUM",
    description_fr=(
        "Points adresse géolocalisés avec attributs enrichis. "
        "Inclut le positionnement précis et métadonnées de qualité."
    ),
    description_en=(
        "Geolocated address points with enriched attributes. "
        "Includes precise positioning and quality metadata."
    ),
    category=ProductCategory.ADDRESS,
    formats=[FileFormat.SHP, FileFormat.GPKG],
    territories=ALL_TERRITORIES,
    layers=ADRESSE_PREMIUM_LAYERS,
    url_template=(
        "https://data.geopf.fr/telechargement/download/ADRESSE-PREMIUM/"
        "ADRESSE-PREMIUM_{version}__{format}_{crs}_{territory}_{date}/"
        "ADRESSE-PREMIUM_{version}__{format}_{crs}_{territory}_{date}.7z"
    ),
    version_pattern="3-0",
    size_mb=4000,
)


# =============================================================================
# BAN PLUS (Base Adresse Nationale enrichie)
# =============================================================================
BAN_PLUS_LAYERS = [
    LayerConfig(
        name="ADRESSE",
        table_key="adresse_ban",
        geometry_type=GeometryType.POINT,
        description_fr="Adresses de la Base Adresse Nationale",
        description_en="National Address Database addresses",
    ),
]

BAN_PLUS = IGNProduct(
    id="ban-plus",
    name="BAN PLUS",
    description_fr=(
        "Base Adresse Nationale enrichie par l'IGN. "
        "Fusion des sources BAN, BANO et autres référentiels adresse."
    ),
    description_en=(
        "National Address Database enriched by IGN. "
        "Fusion of BAN, BANO and other address repositories."
    ),
    category=ProductCategory.ADDRESS,
    formats=[FileFormat.SHP, FileFormat.GPKG],
    territories=ALL_TERRITORIES,
    layers=BAN_PLUS_LAYERS,
    url_template=(
        "https://data.geopf.fr/telechargement/download/BAN-PLUS/"
        "BAN-PLUS_{version}__{format}_{crs}_{territory}_{date}/"
        "BAN-PLUS_{version}__{format}_{crs}_{territory}_{date}.7z"
    ),
    version_pattern="1-0",
    size_mb=3000,
)


# =============================================================================
# BCAE (Bonnes Conditions Agricoles et Environnementales)
# =============================================================================
BCAE_LAYERS = [
    LayerConfig(
        name="BCAE",
        table_key="bcae",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Zones BCAE (prairies permanentes, haies, etc.)",
        description_en="BCAE zones (permanent grasslands, hedgerows, etc.)",
    ),
    LayerConfig(
        name="HAIE",
        table_key="haie",
        geometry_type=GeometryType.MULTILINESTRING,
        description_fr="Haies et éléments linéaires",
        description_en="Hedgerows and linear elements",
        optional=True,
    ),
    LayerConfig(
        name="MARE",
        table_key="mare",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Mares et points d'eau",
        description_en="Ponds and water points",
        optional=True,
    ),
]

BCAE = IGNProduct(
    id="bcae",
    name="BCAE",
    description_fr=(
        "Bonnes Conditions Agricoles et Environnementales - éléments paysagers "
        "protégés dans le cadre de la PAC (haies, mares, prairies permanentes)."
    ),
    description_en=(
        "Good Agricultural and Environmental Conditions - landscape elements "
        "protected under CAP (hedgerows, ponds, permanent grasslands)."
    ),
    category=ProductCategory.LAND,
    formats=[FileFormat.SHP, FileFormat.GPKG],
    territories=METROPOLITAN_TERRITORIES,
    layers=BCAE_LAYERS,
    url_template=(
        "https://data.geopf.fr/telechargement/download/BCAE/"
        "BCAE_{version}__{format}_{crs}_{territory}_{date}/"
        "BCAE_{version}__{format}_{crs}_{territory}_{date}.7z"
    ),
    version_pattern="1-0",
    size_mb=800,
)


# =============================================================================
# CIRCONSCRIPTIONS LÉGISLATIVES
# =============================================================================
CIRCONSCRIPTION_LEGISLATIVE_LAYERS = [
    LayerConfig(
        name="CIRCONSCRIPTION_LEGISLATIVE",
        table_key="circonscription_legislative",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Circonscriptions législatives (577 en France)",
        description_en="Legislative constituencies (577 in France)",
    ),
]

CIRCONSCRIPTIONS_LEGISLATIVES = IGNProduct(
    id="circonscriptions-legislatives",
    name="Circonscriptions Législatives",
    description_fr=(
        "Contours des 577 circonscriptions législatives de France. "
        "Découpage électoral pour l'élection des députés à l'Assemblée nationale. "
        "Inclut la métropole (539), les DROM (19), les COM (8) et l'étranger (11). "
        "Découpage inchangé depuis la réforme de 2012."
    ),
    description_en=(
        "Boundaries of France's 577 legislative constituencies. "
        "Electoral districts for National Assembly deputy elections. "
        "Includes mainland (539), overseas departments (19), overseas collectivities (8), "
        "and abroad (11). Boundaries unchanged since 2012 reform."
    ),
    category=ProductCategory.ELECTORAL,
    formats=[FileFormat.SHP, FileFormat.GPKG],
    territories=[TerritoryCode.FRA],
    layers=CIRCONSCRIPTION_LEGISLATIVE_LAYERS,
    # Source: data.gouv.fr (agrégation des bureaux de vote)
    url_template=(
        "https://www.data.gouv.fr/fr/datasets/r/"
        "eb27b498-a498-4d24-bb5e-ea3e49694f6a"  # circonscriptions-legislatives-shp.zip
    ),
    version_pattern="2024",
    archive_extension="zip",
    size_mb=10,
)


# =============================================================================
# BUREAUX DE VOTE
# =============================================================================
BUREAU_VOTE_LAYERS = [
    LayerConfig(
        name="BUREAU_DE_VOTE",
        table_key="bureau_vote",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Contours des bureaux de vote (environ 69 000 en France)",
        description_en="Polling station boundaries (approximately 69,000 in France)",
    ),
]

BUREAUX_DE_VOTE = IGNProduct(
    id="bureaux-de-vote",
    name="Bureaux de Vote",
    description_fr=(
        "Contours approximatifs des bureaux de vote français générés par diagrammes "
        "de Voronoï à partir des adresses du Répertoire Électoral Unique (REU). "
        "Source: data.gouv.fr / Etalab. Millésime septembre 2022. "
        "Environ 69 000 bureaux de vote couvrant la France entière."
    ),
    description_en=(
        "Approximate boundaries of French polling stations generated using Voronoi "
        "diagrams from addresses in the Single Electoral Register (REU). "
        "Source: data.gouv.fr / Etalab. Vintage September 2022. "
        "Approximately 69,000 polling stations covering all of France."
    ),
    category=ProductCategory.ELECTORAL,
    formats=[FileFormat.GPKG],  # GeoJSON converti en GPKG pour compatibilité
    territories=[TerritoryCode.FRA],
    layers=BUREAU_VOTE_LAYERS,
    # Source: data.gouv.fr (contours Voronoï Etalab)
    url_template=(
        "https://object.files.data.gouv.fr/data-pipeline-open/reu/"
        "contours-france-entiere-latest-v2.geojson"
    ),
    version_pattern="2022",
    archive_extension="geojson",  # Téléchargement direct, pas d'archive
    size_mb=645,
)


# Liste de tous les autres produits
OTHER_PRODUCTS: list[IGNProduct] = [
    CONTOURS_IRIS,
    BD_FORET,
    MASQUE_FORET,
    BD_CARTO,
    ADRESSE_PREMIUM,
    BAN_PLUS,
    BCAE,
    CIRCONSCRIPTIONS_LEGISLATIVES,
    BUREAUX_DE_VOTE,
]
