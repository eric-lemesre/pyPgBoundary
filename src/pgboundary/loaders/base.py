"""Base class for geographic data loaders."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import geopandas as gpd

from pgboundary.config import Settings
from pgboundary.db.connection import DatabaseManager

logger = logging.getLogger(__name__)


class BaseLoader(ABC):
    """Abstract base class for data loaders."""

    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the loader.

        Args:
            db_manager: Database manager.
            settings: Module configuration.
        """
        self.settings = settings or Settings()
        self.db_manager = db_manager or DatabaseManager(self.settings)

    @abstractmethod
    def load(self, source_path: Path | None = None, **kwargs: Any) -> int:
        """Load data from a source file.

        Args:
            source_path: Path to the source file (optional for some loaders).
            **kwargs: Additional arguments.

        Returns:
            Number of loaded records.
        """
        pass

    def read_shapefile(self, path: Path, encoding: str = "utf-8") -> gpd.GeoDataFrame:
        """Read a shapefile and return a GeoDataFrame.

        Args:
            path: Path to the shapefile.
            encoding: File encoding.

        Returns:
            GeoDataFrame with the data.
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
        """Reproject a GeoDataFrame to the target SRID.

        Args:
            gdf: GeoDataFrame to reproject.
            target_srid: Target SRID (uses the config value if not provided).

        Returns:
            Reprojected GeoDataFrame.
        """
        target_srid = target_srid or self.settings.srid
        current_srid = gdf.crs.to_epsg() if gdf.crs else None

        if current_srid != target_srid:
            logger.debug("Reprojection de EPSG:%s vers EPSG:%s", current_srid, target_srid)
            gdf = gdf.to_crs(epsg=target_srid)

        return gdf

    def to_multipolygon(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Convert all geometries to MultiPolygon.

        Args:
            gdf: GeoDataFrame to convert.

        Returns:
            GeoDataFrame with MultiPolygon geometries.
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
        """Load a GeoDataFrame into PostgreSQL.

        Args:
            gdf: GeoDataFrame to load.
            table_name: Target table name.
            schema: PostgreSQL schema.
            if_exists: Behavior if the table exists ('replace', 'append', 'fail').

        Returns:
            Number of loaded records.
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
