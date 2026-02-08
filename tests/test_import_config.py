"""Tests pour le module import_config.

Ce module teste les structures de configuration pour les imports
de produits IGN avec support de l'historisation.
"""

from __future__ import annotations

import pytest

from pgboundary.import_config import (
    DEFAULT_PRODUCT_CONFIGS,
    HistorizationConfig,
    ImportsConfig,
    ProductImportConfig,
    SimilarityLevel,
    SimilarityMethod,
    SimilarityResult,
    SimilarityThresholds,
    get_default_key_field,
)


class TestSimilarityMethod:
    """Tests pour l'énumération SimilarityMethod."""

    def test_method_values(self) -> None:
        """Test des valeurs de l'énumération."""
        assert SimilarityMethod.MD5 == "md5"
        assert SimilarityMethod.JACCARD == "jaccard"
        assert SimilarityMethod.HAUSDORFF == "hausdorff"
        assert SimilarityMethod.COMBINED == "combined"

    def test_method_count(self) -> None:
        """Test du nombre de méthodes."""
        assert len(SimilarityMethod) == 4


class TestSimilarityLevel:
    """Tests pour l'énumération SimilarityLevel."""

    def test_level_values(self) -> None:
        """Test des valeurs de l'énumération."""
        assert SimilarityLevel.IDENTICAL == "identical"
        assert SimilarityLevel.LIKELY_MATCH == "likely_match"
        assert SimilarityLevel.SUSPECT == "suspect"
        assert SimilarityLevel.DISTINCT == "distinct"

    def test_level_count(self) -> None:
        """Test du nombre de niveaux."""
        assert len(SimilarityLevel) == 4


class TestSimilarityResult:
    """Tests pour la dataclass SimilarityResult."""

    def test_default_values(self) -> None:
        """Test des valeurs par défaut."""
        result = SimilarityResult(
            level=SimilarityLevel.IDENTICAL,
            iou_score=0.98,
        )
        assert result.level == SimilarityLevel.IDENTICAL
        assert result.iou_score == 0.98
        assert result.hausdorff_distance is None
        assert result.combined_score == 0.0
        assert result.needs_validation is False
        assert result.reason == ""

    def test_full_values(self) -> None:
        """Test avec toutes les valeurs."""
        result = SimilarityResult(
            level=SimilarityLevel.LIKELY_MATCH,
            iou_score=0.85,
            hausdorff_distance=5.2,
            combined_score=0.88,
            needs_validation=True,
            reason="Attributs différents",
        )
        assert result.hausdorff_distance == 5.2
        assert result.combined_score == 0.88
        assert result.needs_validation is True
        assert result.reason == "Attributs différents"

    def test_is_match_identical(self) -> None:
        """Test is_match pour IDENTICAL."""
        result = SimilarityResult(
            level=SimilarityLevel.IDENTICAL,
            iou_score=0.98,
        )
        assert result.is_match() is True

    def test_is_match_likely_match(self) -> None:
        """Test is_match pour LIKELY_MATCH."""
        result = SimilarityResult(
            level=SimilarityLevel.LIKELY_MATCH,
            iou_score=0.85,
        )
        assert result.is_match() is True

    def test_is_match_suspect(self) -> None:
        """Test is_match pour SUSPECT."""
        result = SimilarityResult(
            level=SimilarityLevel.SUSPECT,
            iou_score=0.60,
        )
        assert result.is_match() is False

    def test_is_match_distinct(self) -> None:
        """Test is_match pour DISTINCT."""
        result = SimilarityResult(
            level=SimilarityLevel.DISTINCT,
            iou_score=0.20,
        )
        assert result.is_match() is False

    def test_is_auto_merge_identical(self) -> None:
        """Test is_auto_merge pour IDENTICAL."""
        result = SimilarityResult(
            level=SimilarityLevel.IDENTICAL,
            iou_score=0.98,
        )
        assert result.is_auto_merge() is True

    def test_is_auto_merge_other_levels(self) -> None:
        """Test is_auto_merge pour autres niveaux."""
        for level in [
            SimilarityLevel.LIKELY_MATCH,
            SimilarityLevel.SUSPECT,
            SimilarityLevel.DISTINCT,
        ]:
            result = SimilarityResult(level=level, iou_score=0.5)
            assert result.is_auto_merge() is False


class TestSimilarityThresholds:
    """Tests pour le modèle SimilarityThresholds."""

    def test_default_values(self) -> None:
        """Test des valeurs par défaut."""
        thresholds = SimilarityThresholds()
        assert thresholds.identical_min == 0.95
        assert thresholds.likely_match_min == 0.80
        assert thresholds.suspect_min == 0.50
        assert thresholds.hausdorff_max == 10.0

    def test_custom_values(self) -> None:
        """Test avec valeurs personnalisées."""
        thresholds = SimilarityThresholds(
            identical_min=0.98,
            likely_match_min=0.85,
            suspect_min=0.60,
            hausdorff_max=5.0,
        )
        assert thresholds.identical_min == 0.98
        assert thresholds.likely_match_min == 0.85
        assert thresholds.suspect_min == 0.60
        assert thresholds.hausdorff_max == 5.0

    def test_validation_bounds(self) -> None:
        """Test de la validation des bornes."""
        # Valeurs valides aux limites
        t = SimilarityThresholds(identical_min=0.0)
        assert t.identical_min == 0.0

        t = SimilarityThresholds(identical_min=1.0)
        assert t.identical_min == 1.0

    def test_validation_invalid(self) -> None:
        """Test de la validation avec valeurs invalides."""
        with pytest.raises(ValueError):
            SimilarityThresholds(identical_min=-0.1)

        with pytest.raises(ValueError):
            SimilarityThresholds(identical_min=1.5)

        with pytest.raises(ValueError):
            SimilarityThresholds(hausdorff_max=-1.0)


class TestHistorizationConfig:
    """Tests pour le modèle HistorizationConfig."""

    def test_default_values(self) -> None:
        """Test des valeurs par défaut."""
        config = HistorizationConfig()
        assert config.enabled is False
        assert config.method == SimilarityMethod.COMBINED
        assert config.key_field == "cd_insee"
        assert config.threshold is None

    def test_custom_values(self) -> None:
        """Test avec valeurs personnalisées."""
        config = HistorizationConfig(
            enabled=True,
            method=SimilarityMethod.JACCARD,
            key_field="code_iris",
        )
        assert config.enabled is True
        assert config.method == SimilarityMethod.JACCARD
        assert config.key_field == "code_iris"

    def test_get_effective_thresholds_default(self) -> None:
        """Test get_effective_thresholds sans threshold legacy."""
        config = HistorizationConfig()
        thresholds = config.get_effective_thresholds()
        assert thresholds.identical_min == 0.95

    def test_get_effective_thresholds_legacy(self) -> None:
        """Test get_effective_thresholds avec threshold legacy."""
        config = HistorizationConfig(threshold=0.90)
        thresholds = config.get_effective_thresholds()
        assert thresholds.identical_min == 0.90

    def test_get_threshold_description_md5(self) -> None:
        """Test description pour MD5."""
        config = HistorizationConfig(method=SimilarityMethod.MD5)
        desc = config.get_threshold_description()
        assert "MD5" in desc

    def test_get_threshold_description_combined(self) -> None:
        """Test description pour COMBINED."""
        config = HistorizationConfig(method=SimilarityMethod.COMBINED)
        desc = config.get_threshold_description()
        assert "IoU" in desc
        assert "Hausdorff" in desc

    def test_get_threshold_description_jaccard(self) -> None:
        """Test description pour JACCARD."""
        config = HistorizationConfig(method=SimilarityMethod.JACCARD)
        desc = config.get_threshold_description()
        assert "IoU" in desc

    def test_get_threshold_description_hausdorff(self) -> None:
        """Test description pour HAUSDORFF."""
        config = HistorizationConfig(method=SimilarityMethod.HAUSDORFF)
        desc = config.get_threshold_description()
        assert "Distance" in desc


class TestProductImportConfig:
    """Tests pour le modèle ProductImportConfig."""

    def test_default_values(self) -> None:
        """Test des valeurs par défaut."""
        config = ProductImportConfig()
        assert config.enabled is True
        assert config.layers == []
        assert config.territory == "FRA"
        assert config.format == "shp"
        assert config.years == ["2024"]
        assert config.historization.enabled is False

    def test_custom_values(self) -> None:
        """Test avec valeurs personnalisées."""
        config = ProductImportConfig(
            enabled=False,
            layers=["REGION", "COMMUNE"],
            territory="FXX",
            format="gpkg",
            years=["2023", "2024"],
        )
        assert config.enabled is False
        assert config.layers == ["REGION", "COMMUNE"]
        assert config.territory == "FXX"
        assert config.format == "gpkg"
        assert config.years == ["2023", "2024"]

    def test_get_latest_year(self) -> None:
        """Test get_latest_year."""
        config = ProductImportConfig(years=["2022", "2024", "2023"])
        assert config.get_latest_year() == "2024"

    def test_get_latest_year_empty(self) -> None:
        """Test get_latest_year avec liste vide."""
        config = ProductImportConfig(years=[])
        assert config.get_latest_year() is None

    def test_get_layers_display_all(self) -> None:
        """Test get_layers_display sans couches spécifiques."""
        config = ProductImportConfig(layers=[])
        assert config.get_layers_display() == "toutes"

    def test_get_layers_display_specific(self) -> None:
        """Test get_layers_display avec couches spécifiques."""
        config = ProductImportConfig(layers=["REGION", "COMMUNE"])
        assert config.get_layers_display() == "REGION, COMMUNE"


class TestImportsConfig:
    """Tests pour le modèle ImportsConfig."""

    def test_empty_config(self) -> None:
        """Test configuration vide."""
        config = ImportsConfig()
        assert config.products == {}
        assert config.count_total() == 0
        assert config.count_enabled() == 0

    def test_add_product(self) -> None:
        """Test ajout d'un produit."""
        config = ImportsConfig()
        config.add_product("test-product")
        assert "test-product" in config.products
        assert config.count_total() == 1

    def test_add_product_with_config(self) -> None:
        """Test ajout d'un produit avec configuration."""
        config = ImportsConfig()
        prod_config = ProductImportConfig(enabled=False, territory="FXX")
        config.add_product("test-product", prod_config)
        assert config.products["test-product"].enabled is False
        assert config.products["test-product"].territory == "FXX"

    def test_remove_product(self) -> None:
        """Test suppression d'un produit."""
        config = ImportsConfig()
        config.add_product("test-product")
        assert config.remove_product("test-product") is True
        assert "test-product" not in config.products

    def test_remove_product_not_found(self) -> None:
        """Test suppression d'un produit inexistant."""
        config = ImportsConfig()
        assert config.remove_product("inexistant") is False

    def test_get_product(self) -> None:
        """Test récupération d'un produit."""
        config = ImportsConfig()
        config.add_product("test-product")
        prod = config.get_product("test-product")
        assert prod is not None
        assert prod.enabled is True

    def test_get_product_not_found(self) -> None:
        """Test récupération d'un produit inexistant."""
        config = ImportsConfig()
        assert config.get_product("inexistant") is None

    def test_get_enabled_products(self) -> None:
        """Test récupération des produits activés."""
        config = ImportsConfig()
        config.add_product("enabled-1", ProductImportConfig(enabled=True))
        config.add_product("disabled-1", ProductImportConfig(enabled=False))
        config.add_product("enabled-2", ProductImportConfig(enabled=True))

        enabled = config.get_enabled_products()
        assert len(enabled) == 2
        assert "enabled-1" in enabled
        assert "enabled-2" in enabled
        assert "disabled-1" not in enabled

    def test_count_enabled(self) -> None:
        """Test comptage des produits activés."""
        config = ImportsConfig()
        config.add_product("enabled-1", ProductImportConfig(enabled=True))
        config.add_product("disabled-1", ProductImportConfig(enabled=False))
        config.add_product("enabled-2", ProductImportConfig(enabled=True))

        assert config.count_enabled() == 2
        assert config.count_total() == 3


class TestDefaultProductConfigs:
    """Tests pour les configurations par défaut."""

    def test_admin_express_cog_exists(self) -> None:
        """Test que admin-express-cog existe."""
        assert "admin-express-cog" in DEFAULT_PRODUCT_CONFIGS

    def test_admin_express_cog_config(self) -> None:
        """Test de la configuration admin-express-cog."""
        config = DEFAULT_PRODUCT_CONFIGS["admin-express-cog"]
        assert config.enabled is True
        assert "REGION" in config.layers
        assert "COMMUNE" in config.layers
        assert config.territory == "FRA"
        assert config.historization.enabled is True
        assert config.historization.method == SimilarityMethod.COMBINED

    def test_contours_iris_exists(self) -> None:
        """Test que contours-iris existe."""
        assert "contours-iris" in DEFAULT_PRODUCT_CONFIGS

    def test_contours_iris_disabled(self) -> None:
        """Test que contours-iris est désactivé par défaut."""
        config = DEFAULT_PRODUCT_CONFIGS["contours-iris"]
        assert config.enabled is False

    def test_codes_postaux_ban_exists(self) -> None:
        """Test que codes-postaux-ban existe."""
        assert "codes-postaux-ban" in DEFAULT_PRODUCT_CONFIGS


class TestGetDefaultKeyField:
    """Tests pour la fonction get_default_key_field."""

    @pytest.mark.parametrize(
        ("layer_name", "expected"),
        [
            ("REGION", "cd_insee"),
            ("DEPARTEMENT", "cd_insee"),
            ("ARRONDISSEMENT", "cd_insee"),
            ("COMMUNE", "cd_insee"),
            ("COMMUNE_ASSOCIEE_OU_DELEGUEE", "cd_insee"),
            ("EPCI", "cd_siren"),
            ("IRIS_GE", "code_iris"),
        ],
    )
    def test_known_layers(self, layer_name: str, expected: str) -> None:
        """Test des couches connues."""
        result = get_default_key_field("any-product", layer_name)
        assert result == expected

    def test_unknown_layer(self) -> None:
        """Test d'une couche inconnue (retourne cd_insee par défaut)."""
        result = get_default_key_field("any-product", "UNKNOWN_LAYER")
        assert result == "cd_insee"
