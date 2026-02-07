"""Tests pour le ProductLoader."""

from unittest.mock import MagicMock, patch

import pytest

from pgboundary.exceptions import LoaderError
from pgboundary.loaders.product_loader import ProductLoader
from pgboundary.products import (
    FileFormat,
    GeometryType,
    IGNProduct,
    LayerConfig,
    ProductCategory,
    TerritoryCode,
    get_default_catalog,
)


class TestProductLoaderInit:
    """Tests d'initialisation du ProductLoader."""

    def test_init_with_product_object(self, settings):
        """Test d'initialisation avec un objet IGNProduct."""
        product = IGNProduct(
            id="test-product",
            name="Test",
            description_fr="Test",
            description_en="Test",
            category=ProductCategory.ADMIN,
            formats=[FileFormat.SHP],
            territories=[TerritoryCode.FRA],
            layers=[LayerConfig(name="LAYER", table_key="layer")],
            url_template="https://example.com",
            version_pattern="1-0",
        )

        loader = ProductLoader(product=product, settings=settings)

        assert loader.product == product
        assert loader.settings == settings

    def test_init_with_product_id(self, settings):
        """Test d'initialisation avec un ID de produit."""
        catalog = get_default_catalog()

        loader = ProductLoader(
            product="admin-express-cog",
            catalog=catalog,
            settings=settings,
        )

        assert loader.product.id == "admin-express-cog"

    def test_init_with_invalid_product_id(self, settings):
        """Test avec un ID de produit invalide."""
        catalog = get_default_catalog()

        with pytest.raises(LoaderError) as exc_info:
            ProductLoader(
                product="invalid-product",
                catalog=catalog,
                settings=settings,
            )

        assert "Produit non trouvé" in str(exc_info.value)

    def test_init_creates_data_source(self, settings):
        """Test que le data source est créé."""
        product = IGNProduct(
            id="test",
            name="Test",
            description_fr="Test",
            description_en="Test",
            category=ProductCategory.ADMIN,
            formats=[FileFormat.SHP],
            territories=[TerritoryCode.FRA],
            layers=[],
            url_template="https://example.com",
            version_pattern="1-0",
        )

        loader = ProductLoader(product=product, settings=settings)

        assert loader.data_source is not None


class TestProductLoaderMethods:
    """Tests des méthodes du ProductLoader."""

    @pytest.fixture
    def sample_product(self) -> IGNProduct:
        """Fixture pour un produit de test."""
        return IGNProduct(
            id="test-product",
            name="Test Product",
            description_fr="Produit de test",
            description_en="Test product",
            category=ProductCategory.ADMIN,
            formats=[FileFormat.SHP, FileFormat.GPKG],
            territories=[TerritoryCode.FRA],
            layers=[
                LayerConfig(
                    name="REGION",
                    table_key="region",
                    geometry_type=GeometryType.MULTIPOLYGON,
                ),
                LayerConfig(
                    name="COMMUNE",
                    table_key="commune",
                    geometry_type=GeometryType.MULTIPOLYGON,
                ),
                LayerConfig(
                    name="OPTIONAL",
                    table_key="optional",
                    optional=True,
                ),
            ],
            url_template="https://example.com/{version}/{format}/{territory}",
            version_pattern="1-0",
        )

    @pytest.fixture
    def loader(self, sample_product, settings) -> ProductLoader:
        """Fixture pour un loader de test."""
        return ProductLoader(product=sample_product, settings=settings)

    def test_list_available_layers(self, loader):
        """Test de la liste des couches disponibles."""
        layers = loader.list_available_layers()

        assert "REGION" in layers
        assert "COMMUNE" in layers
        assert "OPTIONAL" in layers

    def test_get_layers_to_load_all(self, loader):
        """Test de récupération de toutes les couches."""
        layers = loader._get_layers_to_load(None)

        assert len(layers) == 3

    def test_get_layers_to_load_filtered(self, loader):
        """Test de récupération de couches filtrées."""
        layers = loader._get_layers_to_load(["REGION"])

        assert len(layers) == 1
        assert layers[0].name == "REGION"

    def test_get_table_name(self, loader):
        """Test de récupération du nom de table."""
        layer = LayerConfig(name="REGION", table_key="region")

        table_name = loader._get_table_name(layer)

        assert "region" in table_name

    def test_close(self, loader):
        """Test de fermeture des ressources."""
        loader.close()
        # Vérifie que ça ne lève pas d'exception


class TestProductLoaderWithMocks:
    """Tests du ProductLoader avec des mocks."""

    @pytest.fixture
    def mock_data_source(self):
        """Fixture pour un mock de IGNDataSource."""
        mock = MagicMock()
        mock.download_product.return_value = (
            MagicMock(),  # extract_dir
            {"REGION": MagicMock()},  # data_files
        )
        return mock

    def test_download_and_extract(self, settings, mock_data_source):
        """Test du téléchargement et extraction."""
        product = IGNProduct(
            id="test",
            name="Test",
            description_fr="Test",
            description_en="Test",
            category=ProductCategory.ADMIN,
            formats=[FileFormat.SHP],
            territories=[TerritoryCode.FRA],
            layers=[LayerConfig(name="REGION", table_key="region")],
            url_template="https://example.com",
            version_pattern="1-0",
        )

        with patch(
            "pgboundary.loaders.product_loader.IGNDataSource",
            return_value=mock_data_source,
        ):
            loader = ProductLoader(product=product, settings=settings)
            files = loader._download_and_extract(FileFormat.SHP, "FRA", "2024")

            mock_data_source.download_product.assert_called_once()
            assert "REGION" in files


class TestAdminExpressLoaderCompatibility:
    """Tests de compatibilité de AdminExpressLoader."""

    def test_admin_express_loader_import(self):
        """Test d'import du AdminExpressLoader."""
        from pgboundary.loaders.admin_express import AdminExpressLoader

        assert AdminExpressLoader is not None

    def test_admin_express_loader_is_product_loader(self, settings):
        """Test que AdminExpressLoader hérite de ProductLoader."""
        from pgboundary.loaders.admin_express import AdminExpressLoader

        loader = AdminExpressLoader(settings=settings)

        assert isinstance(loader, ProductLoader)

    def test_admin_express_loader_default_variant(self, settings):
        """Test de la variante par défaut."""
        from pgboundary.loaders.admin_express import AdminExpressLoader

        loader = AdminExpressLoader(settings=settings)

        assert loader.product.id == "admin-express-cog"

    def test_admin_express_loader_carto_variant(self, settings):
        """Test de la variante CARTO."""
        from pgboundary.loaders.admin_express import AdminExpressLoader

        loader = AdminExpressLoader(variant="carto", settings=settings)

        assert loader.product.id == "admin-express-cog-carto"

    def test_admin_express_loader_convenience_methods(self, settings):
        """Test des méthodes de commodité."""
        from pgboundary.loaders.admin_express import AdminExpressLoader

        loader = AdminExpressLoader(settings=settings)

        # Vérification que les méthodes existent
        assert hasattr(loader, "load_regions")
        assert hasattr(loader, "load_departements")
        assert hasattr(loader, "load_communes")
        assert hasattr(loader, "load_epci")
        assert hasattr(loader, "load_arrondissements")
        assert hasattr(loader, "load_communes_associees")
        assert hasattr(loader, "load_all_admin_layers")
