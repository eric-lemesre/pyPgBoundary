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
    get_admin_express_product,
    get_default_catalog,
)
from pgboundary.sources.loader import load_products, load_territory_crs


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
        assert "masque-foret" in catalog

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
        # Produits non-ADMIN et non-ADDRESS: IRIS, masque-foret, bd-carto,
        # circo. legislatives, bureaux de vote = 5
        assert len(OTHER_PRODUCTS) >= 4

    def test_iris_product(self):
        """Test du produit IRIS."""
        iris = next((p for p in OTHER_PRODUCTS if p.id == "contours-iris"), None)
        assert iris is not None
        assert iris.category == ProductCategory.STATS
        assert "IRIS_GE" in iris.get_layer_names()

    def test_masque_foret_product(self):
        """Test du produit MASQUE FORÊT."""
        foret = next((p for p in OTHER_PRODUCTS if p.id == "masque-foret"), None)
        assert foret is not None
        assert foret.category == ProductCategory.LAND
        assert "MASQUE_FORET" in foret.get_layer_names()


class TestYAMLLoader:
    """Tests pour le chargeur YAML."""

    def test_load_products_returns_list(self):
        """Test que load_products retourne une liste non vide."""
        products = load_products()
        assert isinstance(products, list)
        assert len(products) > 0

    def test_load_products_all_have_id(self):
        """Test que tous les produits ont un ID."""
        products = load_products()
        for product in products:
            assert product.id is not None
            assert len(product.id) > 0

    def test_load_products_all_have_layers(self):
        """Test que tous les produits ont au moins une couche."""
        products = load_products()
        for product in products:
            assert len(product.layers) > 0, f"{product.id} n'a pas de couches"

    def test_load_territory_crs(self):
        """Test du chargement des mappings CRS territoriaux."""
        crs = load_territory_crs()
        assert "FRA" in crs
        assert "FXX" in crs
        assert crs["FRA"] == "WGS84G"
        assert crs["FXX"] == "LAMB93"
        assert crs["GLP"] == "RGAF09UTM20"
        assert crs["REU"] == "RGR92UTM40S"

    def test_load_sources_returns_catalog(self):
        """Test que load_sources retourne un ProductCatalog."""
        from pgboundary.sources.loader import load_sources

        catalog = load_sources()
        assert isinstance(catalog, ProductCatalog)
        assert len(catalog) > 0


class TestURLBuilding:
    """Tests pour la construction d'URLs avec CRS territorial."""

    def test_build_url_fra_wgs84g(self):
        """Test de construction URL pour FRA (WGS84G)."""
        from pgboundary.sources.ign import IGNDataSource

        catalog = get_default_catalog()
        product = catalog.get("admin-express-cog")
        assert product is not None

        source = IGNDataSource()
        url = source.build_url(product, FileFormat.GPKG, "FRA", "2024")

        assert "WGS84G" in url
        assert "GPKG" in url
        assert "FRA" in url
        assert "2024-01-01" in url
        assert "4-0" in url

    def test_build_url_fxx_lamb93(self):
        """Test de construction URL pour FXX (LAMB93)."""
        from pgboundary.sources.ign import IGNDataSource

        catalog = get_default_catalog()
        product = catalog.get("admin-express-cog")
        assert product is not None

        source = IGNDataSource()
        url = source.build_url(product, FileFormat.GPKG, "FXX", "2024")

        assert "LAMB93" in url
        assert "FXX" in url

    def test_build_url_drom_crs(self):
        """Test de construction URL pour DROM avec CRS spécifique."""
        from pgboundary.sources.ign import IGNDataSource

        catalog = get_default_catalog()
        product = catalog.get("admin-express-cog")
        assert product is not None

        source = IGNDataSource()

        # Guadeloupe
        url = source.build_url(product, FileFormat.GPKG, "GLP", "2024")
        assert "RGAF09UTM20" in url

        # Réunion
        url = source.build_url(product, FileFormat.GPKG, "REU", "2024")
        assert "RGR92UTM40S" in url

    def test_build_url_date_normalization(self):
        """Test de la normalisation de date YYYY → YYYY-01-01."""
        from pgboundary.sources.ign import IGNDataSource

        catalog = get_default_catalog()
        product = catalog.get("admin-express-cog")
        assert product is not None

        source = IGNDataSource()

        # YYYY doit devenir YYYY-01-01
        url = source.build_url(product, FileFormat.GPKG, "FRA", "2024")
        assert "2024-01-01" in url

        # YYYY-MM-DD doit rester tel quel
        url = source.build_url(product, FileFormat.GPKG, "FRA", "2024-06-15")
        assert "2024-06-15" in url

    def test_format_string_no_crs(self):
        """Test que le format IGN ne contient plus le CRS."""
        from pgboundary.sources.ign import IGNDataSource

        assert IGNDataSource._format_to_ign_string(FileFormat.SHP) == "SHP"
        assert IGNDataSource._format_to_ign_string(FileFormat.GPKG) == "GPKG"
