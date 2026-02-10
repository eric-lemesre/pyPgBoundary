"""Loader pour les données de codes postaux.

Ce module fournit des loaders spécialisés pour les différentes sources
de codes postaux français.

Sources supportées:
1. Contours calculés BAN (GeoJSON officiel)
2. Base officielle La Poste (CSV avec centroïdes)
3. Fond de carte Géoclip (Shapefile ancien)
4. Génération Voronoï (à partir de La Poste + AdminExpress)
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
import zipfile
from typing import TYPE_CHECKING, Any, Literal

import geopandas as gpd
import httpx
from shapely.geometry import MultiPolygon, Point, Polygon

from pgboundary.exceptions import LoaderError
from pgboundary.loaders.base import BaseLoader
from pgboundary.products.catalog import get_codes_postaux_product

if TYPE_CHECKING:
    from pathlib import Path

    from pgboundary.config import Settings
    from pgboundary.db.connection import DatabaseManager
    from pgboundary.products.catalog import IGNProduct

logger = logging.getLogger(__name__)


class CodesPostauxLoader(BaseLoader):
    """Loader pour les données de codes postaux.

    Supporte plusieurs sources de données avec différentes caractéristiques:
    - BAN: contours officiels (2021, GeoJSON)
    - La Poste: points centroïdes (mis à jour 2x/an)
    - Géoclip: contours anciens (2013, métropole)
    - Voronoï: génération locale (à jour)
    """

    def __init__(
        self,
        source: str = "ban",
        db_manager: DatabaseManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialise le loader de codes postaux.

        Args:
            source: Source de données:
                - "ban": Contours calculés BAN (défaut)
                - "laposte": Base officielle La Poste (points)
                - "geoclip": Fond de carte Géoclip (ancien)
                - "voronoi" ou "generated": Génération Voronoï
            db_manager: Gestionnaire de base de données.
            settings: Configuration du module.
        """
        super().__init__(db_manager, settings)
        self.source = source

        product = get_codes_postaux_product(source)
        if product is None:
            raise LoaderError(
                f"Source de codes postaux non reconnue: {source}. "
                "Sources valides: ban, laposte, geoclip, voronoi"
            )
        self.product: IGNProduct = product

        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Retourne le client HTTP."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(60.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    def load(
        self,
        source_path: Path | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
        **kwargs: Any,
    ) -> int:
        """Charge les données de codes postaux.

        Args:
            source_path: Chemin vers les données locales (optionnel).
            if_exists: Comportement si la table existe.
            **kwargs: Arguments supplémentaires (admin_express_path pour Voronoï).

        Returns:
            Nombre d'enregistrements chargés.
        """
        if self.source in ("voronoi", "generated"):
            return self._load_voronoi(
                admin_express_path=kwargs.get("admin_express_path"),
                if_exists=if_exists,
            )
        elif self.source == "ban":
            return self._load_ban(source_path, if_exists)
        elif self.source == "laposte":
            return self._load_laposte(source_path, if_exists)
        elif self.source == "geoclip":
            return self._load_geoclip(source_path, if_exists)
        else:
            raise LoaderError(f"Source non supportée: {self.source}")

    def _load_ban(
        self,
        source_path: Path | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Charge les contours calculés BAN.

        Args:
            source_path: Chemin vers le GeoJSON local.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        logger.info("Chargement des contours codes postaux BAN")
        logger.warning(
            "ATTENTION: Les contours BAN datent de 2021 et ne sont pas mis à jour. "
            "Les polygones se chevauchent car les codes postaux ne sont pas "
            "des découpages géographiques distincts."
        )

        if source_path is None:
            # Téléchargement du GeoJSON
            url = self.product.url_template
            logger.info("Téléchargement depuis: %s", url)

            response = self.client.get(url)
            response.raise_for_status()

            gdf = gpd.read_file(io.BytesIO(response.content))
        else:
            gdf = gpd.read_file(source_path)

        # Préparation des données
        gdf = self._prepare_ban_gdf(gdf)
        gdf = self.reproject(gdf)
        gdf = self._ensure_multipolygon(gdf)

        # Chargement
        table_name = self.settings.schema_config.get_full_table_name("code_postal_ban")
        schema_name = self.settings.schema_config.get_schema_name()

        return self.load_geodataframe(
            gdf=gdf,
            table_name=table_name,
            schema=schema_name,
            if_exists=if_exists,
        )

    def _load_laposte(
        self,
        source_path: Path | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Charge la base officielle La Poste (points).

        Args:
            source_path: Chemin vers le CSV local.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        logger.info("Chargement de la base officielle La Poste")
        logger.info("NOTE: Cette source ne contient que des points (centroïdes)")

        if source_path is None:
            # Téléchargement du CSV
            url = self.product.url_template
            logger.info("Téléchargement depuis: %s", url)

            response = self.client.get(url)
            response.raise_for_status()

            content = response.content.decode("utf-8")
        else:
            content = source_path.read_text(encoding="utf-8")

        # Parse CSV
        gdf = self._parse_laposte_csv(content)
        gdf = self.reproject(gdf)

        # Chargement
        table_name = self.settings.schema_config.get_full_table_name("correspondance_cp_insee")
        schema_name = self.settings.schema_config.get_schema_name()

        return self.load_geodataframe(
            gdf=gdf,
            table_name=table_name,
            schema=schema_name,
            if_exists=if_exists,
        )

    def _load_geoclip(
        self,
        source_path: Path | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Charge le fond de carte Géoclip.

        Args:
            source_path: Chemin vers le shapefile ou archive zip.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        logger.info("Chargement du fond de carte Géoclip")
        logger.warning(
            "ATTENTION: Les données Géoclip datent de 2013-2014 et ne couvrent "
            "que la France métropolitaine."
        )

        if source_path is None:
            # Téléchargement et extraction
            url = self.product.url_template
            logger.info("Téléchargement depuis: %s", url)

            response = self.client.get(url)
            response.raise_for_status()

            # Extraction en mémoire
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                # Trouver le shapefile
                shp_files = [n for n in zf.namelist() if n.endswith(".shp")]
                if not shp_files:
                    raise LoaderError("Pas de shapefile trouvé dans l'archive")

                # Extraire dans un répertoire temporaire
                extract_dir = self.settings.ensure_data_dir() / "geoclip_temp"
                extract_dir.mkdir(exist_ok=True)
                zf.extractall(extract_dir)

                gdf = gpd.read_file(extract_dir / shp_files[0])
        else:
            gdf = gpd.read_file(source_path)

        # Préparation
        gdf = self._prepare_geoclip_gdf(gdf)
        gdf = self.reproject(gdf)
        gdf = self._ensure_multipolygon(gdf)

        # Chargement
        table_name = self.settings.schema_config.get_full_table_name("code_postal_geoclip")
        schema_name = self.settings.schema_config.get_schema_name()

        return self.load_geodataframe(
            gdf=gdf,
            table_name=table_name,
            schema=schema_name,
            if_exists=if_exists,
        )

    def _load_voronoi(
        self,
        admin_express_path: Path | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Génère et charge les contours par Voronoï.

        Cette méthode génère les contours des codes postaux en utilisant
        la tessellation de Voronoï à partir des centroïdes La Poste,
        découpée par les limites départementales AdminExpress.

        Args:
            admin_express_path: Chemin vers les données AdminExpress.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        logger.info("Génération des contours codes postaux par Voronoï")
        logger.info("Cette méthode combine la base La Poste avec les limites AdminExpress")

        # 1. Charger les données La Poste
        logger.info("Étape 1/4: Chargement de la base La Poste")
        laposte_url = (
            "https://datanova.laposte.fr/data-fair/api/v1/datasets/laposte-hexasmal/"
            "metadata-attachments/base-officielle-codes-postaux.csv"
        )
        response = self.client.get(laposte_url)
        response.raise_for_status()
        laposte_gdf = self._parse_laposte_csv(response.content.decode("utf-8"))

        # 2. Charger les limites départementales
        logger.info("Étape 2/4: Chargement des limites départementales")
        if admin_express_path is None:
            raise LoaderError(
                "Pour la génération Voronoï, vous devez fournir le chemin vers "
                "les données AdminExpress via admin_express_path. "
                "Téléchargez d'abord avec: pgboundary download"
            )

        dept_shp = list(admin_express_path.glob("**/DEPARTEMENT.shp"))
        if not dept_shp:
            raise LoaderError(f"Fichier DEPARTEMENT.shp non trouvé dans {admin_express_path}")

        dept_gdf = gpd.read_file(dept_shp[0])
        dept_gdf = dept_gdf.to_crs(epsg=2154)  # Lambert 93 pour le calcul

        # 3. Générer les polygones Voronoï
        logger.info("Étape 3/4: Génération des polygones Voronoï")
        voronoi_gdf = self._generate_voronoi(laposte_gdf, dept_gdf)

        # 4. Reprojection et chargement
        logger.info("Étape 4/4: Chargement en base de données")
        voronoi_gdf = self.reproject(voronoi_gdf)

        table_name = self.settings.schema_config.get_full_table_name("code_postal")
        schema_name = self.settings.schema_config.get_schema_name()

        return self.load_geodataframe(
            gdf=voronoi_gdf,
            table_name=table_name,
            schema=schema_name,
            if_exists=if_exists,
        )

    def _prepare_ban_gdf(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Prépare le GeoDataFrame BAN.

        Args:
            gdf: GeoDataFrame source.

        Returns:
            GeoDataFrame préparé.
        """
        gdf = gdf.copy()

        # Renommage des colonnes
        column_mapping = {
            "codePostal": "cd_postal",
            "nbNumeros": "nb_adresses",
        }
        gdf = gdf.rename(columns=column_mapping)

        # Ajout UID
        gdf["uid"] = [uuid.uuid4() for _ in range(len(gdf))]

        # Sélection des colonnes
        cols = ["uid", "cd_postal", "nb_adresses", "geometry"]
        gdf = gdf[[c for c in cols if c in gdf.columns]]

        return gdf

    def _prepare_geoclip_gdf(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Prépare le GeoDataFrame Géoclip.

        Args:
            gdf: GeoDataFrame source.

        Returns:
            GeoDataFrame préparé.
        """
        gdf = gdf.copy()

        # Renommage probable des colonnes (selon le shapefile Géoclip)
        column_mapping = {
            "ID": "cd_postal",
            "LIBELLE": "lb_nom",
            "POP": "population",
            "MENAGES": "menages",
        }

        for old, new in column_mapping.items():
            if old in gdf.columns:
                gdf = gdf.rename(columns={old: new})

        # Ajout UID
        gdf["uid"] = [uuid.uuid4() for _ in range(len(gdf))]

        return gdf

    def _parse_laposte_csv(self, content: str) -> gpd.GeoDataFrame:
        """Parse le CSV La Poste en GeoDataFrame.

        Args:
            content: Contenu CSV.

        Returns:
            GeoDataFrame avec géométries Point.
        """
        # Détecter le séparateur
        delimiter = ";" if ";" in content[:500] else ","

        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            raise LoaderError("Le fichier CSV La Poste est vide")

        # Identifier les colonnes de coordonnées
        first_row = rows[0]
        lon_col = None
        lat_col = None

        for col in first_row:
            col_lower = col.lower()
            if "longitude" in col_lower or col_lower == "lon":
                lon_col = col
            elif "latitude" in col_lower or col_lower == "lat":
                lat_col = col
            elif "_x" in col_lower:
                lon_col = col
            elif "_y" in col_lower:
                lat_col = col

        # Construire le GeoDataFrame
        data = []
        geometries = []

        for row in rows:
            # Extraire les coordonnées
            try:
                if lon_col and lat_col and row.get(lon_col) and row.get(lat_col):
                    lon = float(row[lon_col].replace(",", "."))
                    lat = float(row[lat_col].replace(",", "."))
                    geom = Point(lon, lat)
                else:
                    geom = None
            except (ValueError, TypeError):
                geom = None

            geometries.append(geom)

            # Mapper les colonnes
            record = {
                "uid": uuid.uuid4(),
                "cd_postal": row.get("code_postal") or row.get("Code_postal"),
                "cd_insee": row.get("code_commune_insee") or row.get("Code_commune_INSEE"),
                "lb_commune": row.get("nom_de_la_commune") or row.get("Nom_commune"),
                "lb_acheminement": row.get("libelle_d_acheminement")
                or row.get("Libellé_acheminement"),
            }
            data.append(record)

        gdf = gpd.GeoDataFrame(data, geometry=geometries, crs="EPSG:4326")

        # Supprimer les lignes sans géométrie
        gdf = gdf[gdf.geometry.notna()]

        logger.info("Base La Poste chargée: %d enregistrements avec coordonnées", len(gdf))
        return gdf

    def _generate_voronoi(
        self,
        points_gdf: gpd.GeoDataFrame,
        boundaries_gdf: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """Génère les polygones Voronoï.

        Args:
            points_gdf: GeoDataFrame avec les points (codes postaux).
            boundaries_gdf: GeoDataFrame avec les limites (départements).

        Returns:
            GeoDataFrame avec les polygones générés.

        Raises:
            LoaderError: Si scipy n'est pas installé.
        """
        try:
            from scipy.spatial import Voronoi
        except ImportError:
            raise LoaderError(
                "scipy est requis pour la génération Voronoï. "
                "Installez-le avec: pip install pgboundary[voronoi]"
            ) from None

        from shapely.geometry import box
        from shapely.ops import unary_union

        # Reprojeter en Lambert 93
        points_gdf = points_gdf.to_crs(epsg=2154)

        # Grouper les points par code postal (prendre le centroïde)
        grouped = points_gdf.dissolve(by="cd_postal", as_index=False)
        grouped["geometry"] = grouped.geometry.centroid

        # Extraire les coordonnées
        coords = [(p.x, p.y) for p in grouped.geometry if p is not None]
        codes = grouped["cd_postal"].tolist()

        if len(coords) < 4:
            raise LoaderError("Pas assez de points pour générer les Voronoï")

        # Limites de la France
        france_bounds = unary_union(boundaries_gdf.geometry)
        minx, miny, maxx, maxy = france_bounds.bounds

        # Ajouter des points miroirs pour les bords
        margin = 100000  # 100 km
        mirror_points = [
            (minx - margin, miny - margin),
            (maxx + margin, miny - margin),
            (minx - margin, maxy + margin),
            (maxx + margin, maxy + margin),
        ]
        all_coords = coords + mirror_points

        # Générer le diagramme de Voronoï
        logger.info("Calcul du diagramme de Voronoï pour %d codes postaux", len(coords))
        vor = Voronoi(all_coords)

        # Construire les polygones
        polygons = []
        valid_codes = []

        box(minx - margin, miny - margin, maxx + margin, maxy + margin)

        for i, region_idx in enumerate(vor.point_region[: len(codes)]):
            region = vor.regions[region_idx]

            if -1 in region or len(region) == 0:
                continue

            try:
                polygon = Polygon([vor.vertices[j] for j in region])

                if not polygon.is_valid:
                    polygon = polygon.buffer(0)

                # Découper par la France
                polygon = polygon.intersection(france_bounds)

                if polygon.is_empty:
                    continue

                # Convertir en MultiPolygon si nécessaire
                if isinstance(polygon, Polygon):
                    polygon = MultiPolygon([polygon])

                polygons.append(polygon)
                valid_codes.append(codes[i])

            except Exception as e:
                logger.debug("Erreur pour le code postal %s: %s", codes[i], e)
                continue

        # Créer le GeoDataFrame résultat
        result = gpd.GeoDataFrame(
            {
                "uid": [uuid.uuid4() for _ in range(len(polygons))],
                "cd_postal": valid_codes,
            },
            geometry=polygons,
            crs="EPSG:2154",
        )

        logger.info("Voronoï généré: %d polygones", len(result))
        return result

    def _ensure_multipolygon(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Convertit les géométries en MultiPolygon.

        Args:
            gdf: GeoDataFrame à convertir.

        Returns:
            GeoDataFrame avec géométries MultiPolygon.
        """

        def to_multi(geom: Polygon | MultiPolygon | None) -> MultiPolygon | None:
            if geom is None:
                return None
            if isinstance(geom, Polygon):
                return MultiPolygon([geom])
            return geom

        gdf = gdf.copy()
        gdf["geometry"] = gdf["geometry"].apply(to_multi)
        return gdf

    def close(self) -> None:
        """Ferme les ressources."""
        if self._client is not None:
            self._client.close()
            self._client = None
