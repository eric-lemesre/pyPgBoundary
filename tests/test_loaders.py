"""Tests pour les loaders."""

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

from pgboundary.config import Settings
from pgboundary.db.models import TableFactory
from pgboundary.loaders.admin_express import AdminExpressLoader
from pgboundary.loaders.base import BaseLoader
from pgboundary.products.catalog import GeometryType, LayerConfig


class TestBaseLoader:
    """Tests pour la classe BaseLoader."""

    def test_reproject(self, settings: Settings) -> None:
        """Teste la reprojection d'un GeoDataFrame."""
        polygon = Polygon([(2.35, 48.85), (2.36, 48.85), (2.36, 48.86), (2.35, 48.86)])
        gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326")

        class ConcreteLoader(BaseLoader):
            def load(self, _source_path: Path | None = None, **_kwargs) -> int:
                return 0

        loader = ConcreteLoader(settings=settings)
        result = loader.reproject(gdf, target_srid=4326)

        assert result.crs.to_epsg() == 4326

    def test_to_multipolygon(self, settings: Settings) -> None:
        """Teste la conversion en MultiPolygon."""
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326")

        class ConcreteLoader(BaseLoader):
            def load(self, _source_path: Path | None = None, **_kwargs) -> int:
                return 0

        loader = ConcreteLoader(settings=settings)
        result = loader.to_multipolygon(gdf)

        assert result.geometry.iloc[0].geom_type == "MultiPolygon"


class TestAdminExpressLoader:
    """Tests pour AdminExpressLoader."""

    def test_column_mappings_exist(self, settings: Settings) -> None:
        """Teste que les mappings de colonnes sont définis."""
        table_factory = TableFactory(settings.schema_config)

        assert table_factory.get_column_mapping("REGION")
        assert table_factory.get_column_mapping("DEPARTEMENT")
        assert table_factory.get_column_mapping("COMMUNE")
        assert table_factory.get_column_mapping("EPCI")

    def test_region_column_mapping(self, settings: Settings) -> None:
        """Teste le mapping des colonnes pour les régions."""
        table_factory = TableFactory(settings.schema_config)
        mapping = table_factory.get_column_mapping("REGION")

        # Les colonnes utilisent les préfixes configurés
        assert mapping["NOM"] == "lb_nom"
        assert mapping["INSEE_REG"] == "cd_insee"

    def test_prepare_geodataframe(self, settings: Settings) -> None:
        """Teste la préparation d'un GeoDataFrame."""
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        gdf = gpd.GeoDataFrame(
            {
                "ID": ["REG01"],
                "NOM": ["Test Region"],
                "INSEE_REG": ["01"],
                "EXTRA_COL": ["extra"],
            },
            geometry=[polygon],
            crs="EPSG:4326",
        )

        # Créer un LayerConfig pour la couche REGION
        region_layer = LayerConfig(
            name="REGION",
            table_key="region",
            geometry_type=GeometryType.MULTIPOLYGON,
            description_fr="Régions administratives",
        )

        loader = AdminExpressLoader(settings=settings)
        result = loader._prepare_geodataframe(gdf, region_layer)

        # Les colonnes renommées utilisent les préfixes
        assert "lb_nom" in result.columns
        assert "cd_insee" in result.columns
        assert "EXTRA_COL" not in result.columns

    def test_loader_has_product(self, settings: Settings) -> None:
        """Teste que le loader a un produit associé."""
        loader = AdminExpressLoader(settings=settings)

        assert loader.product is not None
        assert loader.product.id == "admin-express-cog"

    def test_loader_variant_selection(self, settings: Settings) -> None:
        """Teste la sélection de variante."""
        loader_cog = AdminExpressLoader(variant="cog", settings=settings)
        assert loader_cog.product.id == "admin-express-cog"

        loader_carto = AdminExpressLoader(variant="carto", settings=settings)
        assert loader_carto.product.id == "admin-express-cog-carto"

    def test_list_available_layers(self, settings: Settings) -> None:
        """Teste la liste des couches disponibles."""
        loader = AdminExpressLoader(settings=settings)
        layers = loader.list_available_layers()

        assert "REGION" in layers
        assert "DEPARTEMENT" in layers
        assert "COMMUNE" in layers
        assert "EPCI" in layers
