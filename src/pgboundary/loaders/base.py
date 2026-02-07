"""Classe de base pour les loaders de données géographiques."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import geopandas as gpd

from pgboundary.config import Settings
from pgboundary.db.connection import DatabaseManager

logger = logging.getLogger(__name__)


class BaseLoader(ABC):
    """Classe de base abstraite pour les loaders de données."""

    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialise le loader.

        Args:
            db_manager: Gestionnaire de base de données.
            settings: Configuration du module.
        """
        self.settings = settings or Settings()
        self.db_manager = db_manager or DatabaseManager(self.settings)

    @abstractmethod
    def load(self, source_path: Path | None = None, **kwargs: Any) -> int:
        """Charge les données depuis un fichier source.

        Args:
            source_path: Chemin vers le fichier source (optionnel pour certains loaders).
            **kwargs: Arguments supplémentaires.

        Returns:
            Nombre d'enregistrements chargés.
        """
        pass

    def read_shapefile(self, path: Path, encoding: str = "utf-8") -> gpd.GeoDataFrame:
        """Lit un shapefile et retourne un GeoDataFrame.

        Args:
            path: Chemin vers le shapefile.
            encoding: Encodage du fichier.

        Returns:
            GeoDataFrame avec les données.
        """
        logger.debug("Lecture du shapefile: %s", path)
        gdf = gpd.read_file(path, encoding=encoding)
        logger.info("Shapefile lu: %d entités", len(gdf))
        return gdf

    def reproject(
        self,
        gdf: gpd.GeoDataFrame,
        target_srid: int | None = None,
    ) -> gpd.GeoDataFrame:
        """Reprojette un GeoDataFrame vers le SRID cible.

        Args:
            gdf: GeoDataFrame à reprojeter.
            target_srid: SRID cible (utilise celui de la config si non fourni).

        Returns:
            GeoDataFrame reprojeté.
        """
        target_srid = target_srid or self.settings.srid
        current_srid = gdf.crs.to_epsg() if gdf.crs else None

        if current_srid != target_srid:
            logger.debug("Reprojection de EPSG:%s vers EPSG:%s", current_srid, target_srid)
            gdf = gdf.to_crs(epsg=target_srid)

        return gdf

    def to_multipolygon(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Convertit toutes les géométries en MultiPolygon.

        Args:
            gdf: GeoDataFrame à convertir.

        Returns:
            GeoDataFrame avec géométries MultiPolygon.
        """
        from shapely.geometry import MultiPolygon, Polygon

        def ensure_multi(geom: Polygon | MultiPolygon) -> MultiPolygon:
            if isinstance(geom, Polygon):
                return MultiPolygon([geom])
            return geom

        gdf = gdf.copy()
        gdf["geometry"] = gdf["geometry"].apply(ensure_multi)
        return gdf

    def load_geodataframe(
        self,
        gdf: gpd.GeoDataFrame,
        table_name: str,
        schema: str | None = None,
        if_exists: str = "replace",
    ) -> int:
        """Charge un GeoDataFrame dans PostgreSQL.

        Args:
            gdf: GeoDataFrame à charger.
            table_name: Nom de la table cible.
            schema: Schéma PostgreSQL.
            if_exists: Comportement si la table existe ('replace', 'append', 'fail').

        Returns:
            Nombre d'enregistrements chargés.
        """
        schema = schema or self.settings.schema_name

        logger.info("Chargement de %d entités dans %s.%s", len(gdf), schema, table_name)

        gdf.to_postgis(
            name=table_name,
            con=self.db_manager.engine,
            schema=schema,
            if_exists=if_exists,
            index=False,
        )

        logger.info("Chargement terminé: %d entités", len(gdf))
        return len(gdf)
