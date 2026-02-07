"""Définitions des produits de codes postaux.

Ce module contient les configurations pour les données de codes postaux français.

AVERTISSEMENT IMPORTANT:
========================
Il n'existe pas de source officielle IGN pour les contours géographiques des codes postaux.
Les codes postaux ne correspondent pas à un découpage administratif : une zone postale peut
être un regroupement de communes, une subdivision, ou un hybride.

Deux approches sont proposées :
1. Contours calculés BAN : enveloppes convexes officielles (2021, non mis à jour)
2. Génération Voronoï : calcul à partir de la base La Poste + AdminExpress (à jour)

Sources:
- Base officielle des codes postaux (La Poste) : https://datanova.laposte.fr/datasets/laposte-hexasmal
- Contours calculés : https://www.data.gouv.fr/datasets/contours-calcules-des-zones-codes-postaux
- Méthode Voronoï : https://r.iresmi.net/posts/2024/codes_postaux/
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

# =============================================================================
# CONTOURS CALCULÉS BAN (Source officielle adresse.data.gouv.fr)
# =============================================================================

CONTOURS_BAN_LAYERS = [
    LayerConfig(
        name="CODES_POSTAUX",
        table_key="code_postal_ban",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Contours des codes postaux (enveloppes convexes BAN)",
        description_en="Postal code boundaries (BAN convex hulls)",
    ),
]

CONTOURS_CODES_POSTAUX_BAN = IGNProduct(
    id="codes-postaux-ban",
    name="Contours Codes Postaux BAN",
    description_fr=(
        "Contours calculés des zones de codes postaux à partir de la Base Adresse Nationale. "
        "Chaque polygone est une enveloppe convexe autour des adresses utilisant un même code postal. "
        "ATTENTION: Millésime 2021, non mis à jour régulièrement. Les contours se chevauchent "
        "car les codes postaux ne correspondent pas à des découpages géographiques distincts."
    ),
    description_en=(
        "Calculated postal code zone boundaries from the National Address Database. "
        "Each polygon is a convex hull around addresses using the same postal code. "
        "WARNING: 2021 vintage, not regularly updated. Boundaries overlap because "
        "postal codes do not correspond to distinct geographic divisions."
    ),
    category=ProductCategory.ADDRESS,
    formats=[FileFormat.GPKG],  # GeoJSON converti en GPKG
    territories=[TerritoryCode.FRA],
    layers=CONTOURS_BAN_LAYERS,
    # URL directe vers le GeoJSON de data.gouv.fr
    url_template=("https://www.data.gouv.fr/fr/datasets/r/f9cbd039-6c7f-4e1b-aed0-5e361e8de0ec"),
    version_pattern="2021",
    archive_extension="geojson",  # Téléchargement direct, pas d'archive
)


# =============================================================================
# BASE OFFICIELLE LA POSTE (CSV avec coordonnées, pas de géométrie)
# =============================================================================

BASE_LAPOSTE_LAYERS = [
    LayerConfig(
        name="CORRESPONDANCE_CP_INSEE",
        table_key="correspondance_cp_insee",
        geometry_type=GeometryType.POINT,  # Centroïdes des communes
        description_fr="Correspondance codes postaux - codes INSEE avec centroïdes",
        description_en="Postal codes - INSEE codes correspondence with centroids",
    ),
]

BASE_CODES_POSTAUX_LAPOSTE = IGNProduct(
    id="codes-postaux-laposte",
    name="Base Codes Postaux La Poste",
    description_fr=(
        "Base officielle des codes postaux de La Poste (Hexaposte). "
        "Fournit la correspondance entre codes postaux et codes INSEE des communes, "
        "avec les coordonnées des centroïdes. Mise à jour 2 fois par an. "
        "NOTE: Pas de contours polygonaux, uniquement des points."
    ),
    description_en=(
        "Official postal code database from La Poste (Hexaposte). "
        "Provides correspondence between postal codes and INSEE municipality codes, "
        "with centroid coordinates. Updated twice a year. "
        "NOTE: No polygon boundaries, only points."
    ),
    category=ProductCategory.ADDRESS,
    formats=[FileFormat.GPKG],  # CSV converti en GPKG avec points
    territories=[TerritoryCode.FRA],
    layers=BASE_LAPOSTE_LAYERS,
    url_template=(
        "https://datanova.laposte.fr/data-fair/api/v1/datasets/laposte-hexasmal/"
        "metadata-attachments/base-officielle-codes-postaux.csv"
    ),
    version_pattern="latest",
    archive_extension="csv",
)


# =============================================================================
# FOND DE CARTE GÉOCLIP (Ancien mais complet pour métropole)
# =============================================================================

GEOCLIP_LAYERS = [
    LayerConfig(
        name="CODES_POSTAUX",
        table_key="code_postal_geoclip",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Contours des codes postaux (Géoclip 2013)",
        description_en="Postal code boundaries (Géoclip 2013)",
    ),
]

FOND_CARTE_CODES_POSTAUX_GEOCLIP = IGNProduct(
    id="codes-postaux-geoclip",
    name="Fond de Carte Codes Postaux Géoclip",
    description_fr=(
        "Fond de carte des codes postaux de France métropolitaine par Géoclip. "
        "Inclut les codes postaux supra-communaux avec estimations de population. "
        "ATTENTION: Données anciennes (2013-2014), métropole uniquement. "
        "Format Shapefile prêt à l'emploi mais non maintenu."
    ),
    description_en=(
        "Postal code basemap for metropolitan France by Géoclip. "
        "Includes supra-municipal postal codes with population estimates. "
        "WARNING: Old data (2013-2014), mainland France only. "
        "Ready-to-use Shapefile format but not maintained."
    ),
    category=ProductCategory.ADDRESS,
    formats=[FileFormat.SHP],
    territories=[TerritoryCode.FXX],  # Métropole uniquement
    layers=GEOCLIP_LAYERS,
    url_template="http://www.geoclip.fr/data/codes_postaux_V5.zip",
    version_pattern="V5",
    archive_extension="zip",
)


# =============================================================================
# CODES POSTAUX GÉNÉRÉS (Voronoï à partir de La Poste + AdminExpress)
# =============================================================================

GENERATED_LAYERS = [
    LayerConfig(
        name="CODES_POSTAUX",
        table_key="code_postal",
        geometry_type=GeometryType.MULTIPOLYGON,
        description_fr="Contours des codes postaux générés par Voronoï",
        description_en="Postal code boundaries generated by Voronoi",
    ),
]

CODES_POSTAUX_GENERATED = IGNProduct(
    id="codes-postaux-generated",
    name="Codes Postaux Générés",
    description_fr=(
        "Contours des codes postaux générés par diagrammes de Voronoï. "
        "Calculés à partir de la base officielle La Poste et des limites AdminExpress. "
        "Méthode: tessellation de Voronoï découpée par les limites départementales. "
        "NOTE: Génération locale requise, non téléchargeable directement."
    ),
    description_en=(
        "Postal code boundaries generated by Voronoi diagrams. "
        "Computed from official La Poste database and AdminExpress boundaries. "
        "Method: Voronoi tessellation clipped by departmental boundaries. "
        "NOTE: Local generation required, not directly downloadable."
    ),
    category=ProductCategory.ADDRESS,
    formats=[FileFormat.GPKG],
    territories=[TerritoryCode.FRA, TerritoryCode.FXX],
    layers=GENERATED_LAYERS,
    # Pas d'URL directe - génération locale
    url_template="generated://codes-postaux",
    version_pattern="{year}",
    archive_extension="gpkg",
)


# Liste de tous les produits codes postaux
CODES_POSTAUX_PRODUCTS: list[IGNProduct] = [
    CONTOURS_CODES_POSTAUX_BAN,
    BASE_CODES_POSTAUX_LAPOSTE,
    FOND_CARTE_CODES_POSTAUX_GEOCLIP,
    CODES_POSTAUX_GENERATED,
]


def get_codes_postaux_product(variant: str = "ban") -> IGNProduct | None:
    """Retourne un produit codes postaux par sa variante.

    Args:
        variant: Variante du produit:
            - "ban": Contours calculés BAN (défaut)
            - "laposte": Base officielle La Poste (points)
            - "geoclip": Fond de carte Géoclip (ancien)
            - "generated" ou "voronoi": Génération Voronoï

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

    for product in CODES_POSTAUX_PRODUCTS:
        if product.id == product_id:
            return product

    return None
