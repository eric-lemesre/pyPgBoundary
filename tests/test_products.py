"""Tests pour le catalogue de produits IGN."""

import pytest

from pgboundary.products import (
    ADMIN_EXPRESS_PRODUCTS,
    OTHER_PRODUCTS,
    FileFormat,
    GeometryType,
    IGNProduct,
    LayerConfig,
    ProductCatalog,
    ProductCategory,
    TerritoryCode,
    get_default_catalog,
)
from pgboundary.products.admin_express import get_admin_express_product


class TestLayerConfig:
    """Tests pour LayerConfig."""

    def test_layer_config_defaults(self):
        """Test des valeurs par défaut de LayerConfig."""
        layer = LayerConfig(name="TEST", table_key="test")
        assert layer.name == "TEST"
        assert layer.table_key == "test"
        assert layer.geometry_type == GeometryType.MULTIPOLYGON
        assert layer.description_fr == ""
        assert layer.description_en == ""
        assert layer.optional is False

    def test_layer_config_full(self):
        """Test de LayerConfig avec toutes les valeurs."""
        layer = LayerConfig(
            name="REGION",
            table_key="region",
            geometry_type=GeometryType.MULTIPOLYGON,
            description_fr="Régions administratives",
            description_en="Administrative regions",
            optional=False,
        )
        assert layer.name == "REGION"
        assert layer.geometry_type == GeometryType.MULTIPOLYGON
        assert layer.description_fr == "Régions administratives"


class TestIGNProduct:
    """Tests pour IGNProduct."""

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
            territories=[TerritoryCode.FRA, TerritoryCode.FXX],
            layers=[
                LayerConfig(name="LAYER1", table_key="layer1"),
                LayerConfig(name="LAYER2", table_key="layer2", optional=True),
            ],
            url_template="https://example.com/{version}/{format}/{territory}",
            version_pattern="1-0",
        )

    def test_product_attributes(self, sample_product: IGNProduct):
        """Test des attributs du produit."""
        assert sample_product.id == "test-product"
        assert sample_product.name == "Test Product"
        assert sample_product.category == ProductCategory.ADMIN
        assert len(sample_product.formats) == 2
        assert len(sample_product.territories) == 2
        assert len(sample_product.layers) == 2

    def test_get_layer(self, sample_product: IGNProduct):
        """Test de récupération d'une couche."""
        layer = sample_product.get_layer("LAYER1")
        assert layer is not None
        assert layer.name == "LAYER1"

        none_layer = sample_product.get_layer("NONEXISTENT")
        assert none_layer is None

    def test_get_layer_names(self, sample_product: IGNProduct):
        """Test de la liste des noms de couches."""
        names = sample_product.get_layer_names()
        assert names == ["LAYER1", "LAYER2"]

    def test_supports_format(self, sample_product: IGNProduct):
        """Test de vérification de support de format."""
        assert sample_product.supports_format(FileFormat.SHP)
        assert sample_product.supports_format(FileFormat.GPKG)

    def test_supports_territory(self, sample_product: IGNProduct):
        """Test de vérification de support de territoire."""
        assert sample_product.supports_territory(TerritoryCode.FRA)
        assert sample_product.supports_territory(TerritoryCode.FXX)
        assert not sample_product.supports_territory(TerritoryCode.GLP)


class TestProductCatalog:
    """Tests pour ProductCatalog."""

    def test_empty_catalog(self):
        """Test d'un catalogue vide."""
        catalog = ProductCatalog()
        assert len(catalog) == 0
        assert catalog.list_all() == []
        assert catalog.list_ids() == []

    def test_register_product(self):
        """Test d'enregistrement d'un produit."""
        catalog = ProductCatalog()
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
        catalog.register(product)

        assert len(catalog) == 1
        assert "test" in catalog
        assert catalog.get("test") == product

    def test_register_many(self):
        """Test d'enregistrement de plusieurs produits."""
        catalog = ProductCatalog()
        products = [
            IGNProduct(
                id=f"product-{i}",
                name=f"Product {i}",
                description_fr=f"Produit {i}",
                description_en=f"Product {i}",
                category=ProductCategory.ADMIN,
                formats=[FileFormat.SHP],
                territories=[TerritoryCode.FRA],
                layers=[],
                url_template="https://example.com",
                version_pattern="1-0",
            )
            for i in range(3)
        ]
        catalog.register_many(products)

        assert len(catalog) == 3
        assert "product-0" in catalog
        assert "product-1" in catalog
        assert "product-2" in catalog

    def test_list_by_category(self):
        """Test du filtrage par catégorie."""
        catalog = ProductCatalog()

        admin_product = IGNProduct(
            id="admin",
            name="Admin",
            description_fr="Admin",
            description_en="Admin",
            category=ProductCategory.ADMIN,
            formats=[FileFormat.SHP],
            territories=[TerritoryCode.FRA],
            layers=[],
            url_template="https://example.com",
            version_pattern="1-0",
        )
        stats_product = IGNProduct(
            id="stats",
            name="Stats",
            description_fr="Stats",
            description_en="Stats",
            category=ProductCategory.STATS,
            formats=[FileFormat.SHP],
            territories=[TerritoryCode.FRA],
            layers=[],
            url_template="https://example.com",
            version_pattern="1-0",
        )

        catalog.register(admin_product)
        catalog.register(stats_product)

        admin_list = catalog.list_by_category(ProductCategory.ADMIN)
        assert len(admin_list) == 1
        assert admin_list[0].id == "admin"

        stats_list = catalog.list_by_category(ProductCategory.STATS)
        assert len(stats_list) == 1
        assert stats_list[0].id == "stats"

    def test_iteration(self):
        """Test de l'itération sur le catalogue."""
        catalog = ProductCatalog()
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
        catalog.register(product)

        products = list(catalog)
        assert len(products) == 1
        assert products[0] == product


class TestDefaultCatalog:
    """Tests pour le catalogue par défaut."""

    def test_default_catalog_not_empty(self):
        """Test que le catalogue par défaut n'est pas vide."""
        catalog = get_default_catalog()
        assert len(catalog) > 0

    def test_admin_express_products_registered(self):
        """Test que les produits Admin Express sont enregistrés."""
        catalog = get_default_catalog()

        assert "admin-express" in catalog
        assert "admin-express-cog" in catalog
        assert "admin-express-cog-carto" in catalog

    def test_other_products_registered(self):
        """Test que les autres produits sont enregistrés."""
        catalog = get_default_catalog()

        assert "contours-iris" in catalog
        assert "bd-foret" in catalog

    def test_admin_express_categories(self):
        """Test des catégories de produits."""
        catalog = get_default_catalog()

        admin_products = catalog.list_by_category(ProductCategory.ADMIN)
        assert len(admin_products) >= 5  # 5 variantes Admin Express


class TestAdminExpressProducts:
    """Tests spécifiques aux produits Admin Express."""

    def test_admin_express_variants_count(self):
        """Test du nombre de variantes Admin Express."""
        assert len(ADMIN_EXPRESS_PRODUCTS) == 5

    def test_admin_express_ids(self):
        """Test des identifiants des variantes."""
        ids = [p.id for p in ADMIN_EXPRESS_PRODUCTS]
        assert "admin-express" in ids
        assert "admin-express-cog" in ids
        assert "admin-express-cog-carto" in ids
        assert "admin-express-cog-carto-pe" in ids
        assert "admin-express-cog-carto-plus-pe" in ids

    def test_all_have_base_layers(self):
        """Test que toutes les variantes ont les couches de base."""
        base_layers = {"REGION", "DEPARTEMENT", "COMMUNE"}

        for product in ADMIN_EXPRESS_PRODUCTS:
            layer_names = set(product.get_layer_names())
            assert base_layers.issubset(layer_names), (
                f"{product.id} manque des couches de base: {base_layers - layer_names}"
            )

    def test_carto_has_chef_lieu(self):
        """Test que les versions CARTO ont les chefs-lieux."""
        carto_products = [p for p in ADMIN_EXPRESS_PRODUCTS if "carto" in p.id]

        for product in carto_products:
            layer_names = product.get_layer_names()
            assert "CHFLIEU_COMMUNE" in layer_names, f"{product.id} devrait avoir CHFLIEU_COMMUNE"

    def test_get_admin_express_product_variants(self):
        """Test de get_admin_express_product avec différentes variantes."""
        assert get_admin_express_product("cog") is not None
        assert get_admin_express_product("cog").id == "admin-express-cog"

        assert get_admin_express_product("carto") is not None
        assert get_admin_express_product("carto").id == "admin-express-cog-carto"

        assert get_admin_express_product("pe") is not None
        assert get_admin_express_product("plus") is not None

    def test_get_admin_express_product_invalid(self):
        """Test avec une variante invalide."""
        assert get_admin_express_product("invalid") is None


class TestOtherProducts:
    """Tests pour les autres produits."""

    def test_other_products_count(self):
        """Test du nombre d'autres produits."""
        assert len(OTHER_PRODUCTS) >= 7

    def test_iris_product(self):
        """Test du produit IRIS."""
        iris = next((p for p in OTHER_PRODUCTS if p.id == "contours-iris"), None)
        assert iris is not None
        assert iris.category == ProductCategory.STATS
        assert "IRIS_GE" in iris.get_layer_names()

    def test_bd_foret_product(self):
        """Test du produit BD FORÊT."""
        foret = next((p for p in OTHER_PRODUCTS if p.id == "bd-foret"), None)
        assert foret is not None
        assert foret.category == ProductCategory.LAND
        assert "FORMATION_VEGETALE" in foret.get_layer_names()

    def test_bcae_product(self):
        """Test du produit BCAE."""
        bcae = next((p for p in OTHER_PRODUCTS if p.id == "bcae"), None)
        assert bcae is not None
        assert bcae.category == ProductCategory.LAND
