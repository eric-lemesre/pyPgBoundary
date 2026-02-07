"""Tests pour le loader de codes postaux."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

from pgboundary.loaders.codes_postaux import CodesPostauxLoader
from pgboundary.products.codes_postaux import (
    CODES_POSTAUX_PRODUCTS,
    get_codes_postaux_product,
)


class TestCodesPostauxProducts:
    """Tests pour les définitions de produits codes postaux."""

    def test_products_list_not_empty(self):
        """Vérifie que la liste des produits n'est pas vide."""
        assert len(CODES_POSTAUX_PRODUCTS) == 4

    def test_all_products_have_required_fields(self):
        """Vérifie que tous les produits ont les champs requis."""
        for product in CODES_POSTAUX_PRODUCTS:
            assert product.id is not None
            assert product.name is not None
            assert product.description_fr is not None
            assert product.category is not None
            assert len(product.formats) > 0

    def test_get_codes_postaux_product_ban(self):
        """Vérifie la récupération du produit BAN."""
        product = get_codes_postaux_product("ban")
        assert product is not None
        assert "ban" in product.id.lower()

    def test_get_codes_postaux_product_laposte(self):
        """Vérifie la récupération du produit La Poste."""
        product = get_codes_postaux_product("laposte")
        assert product is not None
        assert "laposte" in product.id.lower()

    def test_get_codes_postaux_product_geoclip(self):
        """Vérifie la récupération du produit Géoclip."""
        product = get_codes_postaux_product("geoclip")
        assert product is not None
        assert "geoclip" in product.id.lower()

    def test_get_codes_postaux_product_voronoi(self):
        """Vérifie la récupération du produit Voronoï."""
        product = get_codes_postaux_product("voronoi")
        assert product is not None
        assert "generated" in product.id.lower()

    def test_get_codes_postaux_product_generated_alias(self):
        """Vérifie que 'generated' est un alias pour 'voronoi'."""
        product = get_codes_postaux_product("generated")
        assert product is not None
        assert product.id == get_codes_postaux_product("voronoi").id

    def test_get_codes_postaux_product_invalid(self):
        """Vérifie que None est retourné pour une source invalide."""
        product = get_codes_postaux_product("invalid_source")
        assert product is None


class TestCodesPostauxLoader:
    """Tests pour le loader de codes postaux."""

    def test_loader_init_ban(self, settings):
        """Vérifie l'initialisation avec la source BAN."""
        loader = CodesPostauxLoader(source="ban", settings=settings)
        assert loader.source == "ban"
        assert loader.product is not None

    def test_loader_init_laposte(self, settings):
        """Vérifie l'initialisation avec la source La Poste."""
        loader = CodesPostauxLoader(source="laposte", settings=settings)
        assert loader.source == "laposte"
        assert loader.product is not None

    def test_loader_init_voronoi(self, settings):
        """Vérifie l'initialisation avec la source Voronoï."""
        loader = CodesPostauxLoader(source="voronoi", settings=settings)
        assert loader.source == "voronoi"
        assert loader.product is not None

    def test_loader_init_invalid_source(self, settings):
        """Vérifie qu'une source invalide lève une erreur."""
        from pgboundary.exceptions import LoaderError

        with pytest.raises(LoaderError, match="Source de codes postaux non reconnue"):
            CodesPostauxLoader(source="invalid", settings=settings)

    def test_loader_client_lazy_init(self, settings):
        """Vérifie que le client HTTP est initialisé paresseusement."""
        loader = CodesPostauxLoader(source="ban", settings=settings)
        assert loader._client is None
        _ = loader.client
        assert loader._client is not None

    def test_loader_close(self, settings):
        """Vérifie que close() libère les ressources."""
        loader = CodesPostauxLoader(source="ban", settings=settings)
        _ = loader.client  # Force l'initialisation
        loader.close()
        assert loader._client is None


class TestCodesPostauxLoaderParsing:
    """Tests pour les méthodes de parsing du loader."""

    def test_parse_laposte_csv_semicolon(self, settings):
        """Vérifie le parsing d'un CSV avec séparateur point-virgule."""
        csv_content = """code_postal;code_commune_insee;nom_de_la_commune;Longitude;Latitude
75001;75101;PARIS 01;2.3455;48.8603
75002;75102;PARIS 02;2.3445;48.8670
"""
        loader = CodesPostauxLoader(source="laposte", settings=settings)
        gdf = loader._parse_laposte_csv(csv_content)

        assert len(gdf) == 2
        assert "cd_postal" in gdf.columns
        assert "cd_insee" in gdf.columns
        assert gdf.geometry.dtype.name == "geometry"

    def test_parse_laposte_csv_comma(self, settings):
        """Vérifie le parsing d'un CSV avec séparateur virgule."""
        csv_content = """code_postal,code_commune_insee,nom_de_la_commune,Longitude,Latitude
75001,75101,PARIS 01,2.3455,48.8603
"""
        loader = CodesPostauxLoader(source="laposte", settings=settings)
        gdf = loader._parse_laposte_csv(csv_content)

        assert len(gdf) == 1
        assert gdf.iloc[0]["cd_postal"] == "75001"

    def test_parse_laposte_csv_empty(self, settings):
        """Vérifie qu'un CSV vide lève une erreur."""
        from pgboundary.exceptions import LoaderError

        csv_content = "code_postal;code_commune_insee\n"
        loader = CodesPostauxLoader(source="laposte", settings=settings)

        with pytest.raises(LoaderError, match="vide"):
            loader._parse_laposte_csv(csv_content)

    def test_prepare_ban_gdf(self, settings):
        """Vérifie la préparation du GeoDataFrame BAN."""
        gdf = gpd.GeoDataFrame(
            {
                "codePostal": ["75001", "75002"],
                "nbNumeros": [1000, 800],
            },
            geometry=[
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
            ],
            crs="EPSG:4326",
        )

        loader = CodesPostauxLoader(source="ban", settings=settings)
        result = loader._prepare_ban_gdf(gdf)

        assert "cd_postal" in result.columns
        assert "nb_adresses" in result.columns
        assert "uid" in result.columns
        assert "codePostal" not in result.columns

    def test_ensure_multipolygon(self, settings):
        """Vérifie la conversion en MultiPolygon."""
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        gdf = gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[polygon],
            crs="EPSG:4326",
        )

        loader = CodesPostauxLoader(source="ban", settings=settings)
        result = loader._ensure_multipolygon(gdf)

        assert isinstance(result.iloc[0].geometry, MultiPolygon)


class TestCodesPostauxLoaderVoronoi:
    """Tests pour la génération Voronoï."""

    @pytest.fixture(autouse=True)
    def require_scipy(self):
        """Skip les tests si scipy n'est pas installé."""
        pytest.importorskip("scipy")

    def test_generate_voronoi_basic(self, settings):
        """Vérifie la génération basique de Voronoï."""
        # Points pour les codes postaux
        points_gdf = gpd.GeoDataFrame(
            {"cd_postal": ["75001", "75002", "75003", "75004", "75005"]},
            geometry=[
                Point(2.34, 48.86),
                Point(2.35, 48.87),
                Point(2.36, 48.86),
                Point(2.35, 48.85),
                Point(2.34, 48.87),
            ],
            crs="EPSG:4326",
        )

        # Limite simplifiée (carré)
        boundaries_gdf = gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[
                Polygon(
                    [
                        (2.33, 48.84),
                        (2.37, 48.84),
                        (2.37, 48.88),
                        (2.33, 48.88),
                    ]
                )
            ],
            crs="EPSG:4326",
        ).to_crs(epsg=2154)

        loader = CodesPostauxLoader(source="voronoi", settings=settings)
        result = loader._generate_voronoi(points_gdf, boundaries_gdf)

        assert len(result) > 0
        assert "cd_postal" in result.columns
        assert "uid" in result.columns
        assert result.crs.to_epsg() == 2154

    def test_generate_voronoi_insufficient_points(self, settings):
        """Vérifie qu'une erreur est levée avec trop peu de points."""
        from pgboundary.exceptions import LoaderError

        points_gdf = gpd.GeoDataFrame(
            {"cd_postal": ["75001", "75002"]},
            geometry=[Point(2.34, 48.86), Point(2.35, 48.87)],
            crs="EPSG:4326",
        )

        boundaries_gdf = gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
            crs="EPSG:4326",
        ).to_crs(epsg=2154)

        loader = CodesPostauxLoader(source="voronoi", settings=settings)

        with pytest.raises(LoaderError, match="Pas assez de points"):
            loader._generate_voronoi(points_gdf, boundaries_gdf)


class TestCodesPostauxLoaderIntegration:
    """Tests d'intégration pour le loader (avec mocking)."""

    @patch("httpx.Client")
    def test_load_ban_downloads_data(self, mock_client_class, settings):
        """Vérifie que load télécharge les données BAN."""
        mock_response = MagicMock()
        mock_response.content = b"""{
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"codePostal": "75001", "nbNumeros": 1000},
                    "geometry": {"type": "Polygon", "coordinates": [[[2.33, 48.85], [2.34, 48.85], [2.34, 48.86], [2.33, 48.86], [2.33, 48.85]]]}
                }
            ]
        }"""
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        loader = CodesPostauxLoader(source="ban", settings=settings)
        loader._client = mock_client

        # Mock de load_geodataframe
        with patch.object(loader, "load_geodataframe", return_value=1):
            count = loader.load()
            assert count == 1

    def test_load_voronoi_requires_admin_express_path(self, settings):
        """Vérifie que la génération Voronoï nécessite admin_express_path."""
        from pgboundary.exceptions import LoaderError

        loader = CodesPostauxLoader(source="voronoi", settings=settings)

        with pytest.raises(LoaderError, match="admin_express_path"):
            loader.load()
