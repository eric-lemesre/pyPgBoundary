"""Tests pour le module CLI de chargement (cli_load.py)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from pgboundary.cli_load import (
    _check_url,
    _get_effective_layer_config,
    _get_enabled_layer_names,
    _get_enabled_layers_count,
)

# =============================================================================
# Tests des fonctions pures
# =============================================================================


class TestGetEnabledLayersCount:
    """Tests pour _get_enabled_layers_count."""

    def test_no_layers_key(self) -> None:
        """Test sans clé layers."""
        config: dict[str, Any] = {}
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 0
        assert total == 0

    def test_empty_layers(self) -> None:
        """Test avec layers vide."""
        config: dict[str, Any] = {"layers": {}}
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 0
        assert total == 0

    def test_all_enabled(self) -> None:
        """Test avec toutes les couches activées."""
        config: dict[str, Any] = {
            "layers": {
                "COMMUNE": {"enabled": True},
                "REGION": {"enabled": True},
            }
        }
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 2
        assert total == 2

    def test_mixed(self) -> None:
        """Test avec un mix activées/désactivées."""
        config: dict[str, Any] = {
            "layers": {
                "COMMUNE": {"enabled": True},
                "REGION": {"enabled": False},
                "EPCI": {"enabled": True},
            }
        }
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 2
        assert total == 3

    def test_default_enabled(self) -> None:
        """Test que sans clé enabled, la couche est activée par défaut."""
        config: dict[str, Any] = {
            "layers": {
                "COMMUNE": {},
                "REGION": {"table_name": "region"},
            }
        }
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 2
        assert total == 2


class TestGetEnabledLayerNames:
    """Tests pour _get_enabled_layer_names."""

    def test_no_layers(self) -> None:
        """Test sans couches."""
        config: dict[str, Any] = {}
        assert _get_enabled_layer_names(config) == []

    def test_empty_layers(self) -> None:
        """Test avec layers vide."""
        config: dict[str, Any] = {"layers": {}}
        assert _get_enabled_layer_names(config) == []

    def test_all_enabled(self) -> None:
        """Test avec toutes les couches activées."""
        config: dict[str, Any] = {
            "layers": {
                "COMMUNE": {"enabled": True},
                "REGION": {"enabled": True},
            }
        }
        result = _get_enabled_layer_names(config)
        assert set(result) == {"COMMUNE", "REGION"}

    def test_some_disabled(self) -> None:
        """Test avec certaines couches désactivées."""
        config: dict[str, Any] = {
            "layers": {
                "COMMUNE": {"enabled": True},
                "REGION": {"enabled": False},
                "EPCI": {"enabled": True},
            }
        }
        result = _get_enabled_layer_names(config)
        assert set(result) == {"COMMUNE", "EPCI"}

    def test_default_enabled(self) -> None:
        """Test que les couches sans clé enabled sont activées."""
        config: dict[str, Any] = {
            "layers": {
                "COMMUNE": {},
            }
        }
        assert _get_enabled_layer_names(config) == ["COMMUNE"]

    def test_legacy_list(self) -> None:
        """Test avec l'ancienne structure en liste."""
        config: dict[str, Any] = {"layers": ["COMMUNE", "REGION"]}
        result = _get_enabled_layer_names(config)
        assert result == ["COMMUNE", "REGION"]


class TestGetEffectiveLayerConfig:
    """Tests pour _get_effective_layer_config."""

    def test_inherits_product_defaults(self) -> None:
        """Test que la couche hérite des valeurs par défaut du produit."""
        prod_config: dict[str, Any] = {
            "territory": "FXX",
            "format": "gpkg",
            "editions": ["2024"],
            "historization": {"enabled": True},
            "layers": {
                "COMMUNE": {"enabled": True},
            },
        }
        result = _get_effective_layer_config(prod_config, "COMMUNE")
        assert result["territory"] == "FXX"
        assert result["format"] == "gpkg"
        assert result["editions"] == ["2024"]
        assert result["enabled"] is True

    def test_layer_overrides_territory(self) -> None:
        """Test que la couche surcharge le territoire."""
        prod_config: dict[str, Any] = {
            "territory": "FRA",
            "format": "shp",
            "editions": ["2024"],
            "layers": {
                "COMMUNE": {"enabled": True, "territory": "GLP"},
            },
        }
        result = _get_effective_layer_config(prod_config, "COMMUNE")
        assert result["territory"] == "GLP"

    def test_layer_overrides_editions(self) -> None:
        """Test que la couche surcharge les éditions."""
        prod_config: dict[str, Any] = {
            "territory": "FRA",
            "format": "shp",
            "editions": ["2024"],
            "layers": {
                "COMMUNE": {"editions": ["2023", "2024"]},
            },
        }
        result = _get_effective_layer_config(prod_config, "COMMUNE")
        assert result["editions"] == ["2023", "2024"]

    def test_unknown_layer_gets_defaults(self) -> None:
        """Test qu'une couche inconnue obtient les valeurs par défaut."""
        prod_config: dict[str, Any] = {
            "territory": "FRA",
            "format": "shp",
            "editions": ["2024"],
            "historization": {},
            "layers": {},
        }
        result = _get_effective_layer_config(prod_config, "UNKNOWN")
        assert result["territory"] == "FRA"
        assert result["format"] == "shp"
        assert result["enabled"] is True

    def test_defaults_when_no_product_values(self) -> None:
        """Test les valeurs par défaut quand le produit n'a rien."""
        prod_config: dict[str, Any] = {"layers": {}}
        result = _get_effective_layer_config(prod_config, "COMMUNE")
        assert result["territory"] == "FRA"
        assert result["format"] == "shp"
        assert result["editions"] == []

    def test_table_name_from_layer(self) -> None:
        """Test que le nom de table vient de la couche."""
        prod_config: dict[str, Any] = {
            "layers": {
                "COMMUNE": {"table_name": "communes_custom"},
            },
        }
        result = _get_effective_layer_config(prod_config, "COMMUNE")
        assert result["table_name"] == "communes_custom"

    def test_table_name_none_when_not_set(self) -> None:
        """Test que le nom de table est None quand pas défini."""
        prod_config: dict[str, Any] = {
            "layers": {
                "COMMUNE": {},
            },
        }
        result = _get_effective_layer_config(prod_config, "COMMUNE")
        assert result["table_name"] is None


# =============================================================================
# Tests de _check_url
# =============================================================================


class TestCheckUrl:
    """Tests pour _check_url."""

    def test_url_ok(self) -> None:
        """Test avec une URL accessible."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.head.return_value = mock_response

        status, message = _check_url(mock_client, "https://example.com")
        assert status == 200
        assert message == "OK"

    def test_url_redirect(self) -> None:
        """Test avec une URL qui redirige (3xx)."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 301
        mock_client.head.return_value = mock_response

        status, message = _check_url(mock_client, "https://example.com")
        assert status == 301
        assert message == "OK"

    def test_url_not_found(self) -> None:
        """Test avec une URL 404."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.head.return_value = mock_response

        status, message = _check_url(mock_client, "https://example.com")
        assert status == 404
        assert message == "Erreur"

    def test_url_server_error(self) -> None:
        """Test avec une erreur serveur."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.head.return_value = mock_response

        status, message = _check_url(mock_client, "https://example.com")
        assert status == 500
        assert message == "Erreur"

    def test_url_connection_error(self) -> None:
        """Test avec une erreur de connexion."""
        import httpx

        mock_client = MagicMock()
        mock_client.head.side_effect = httpx.ConnectError("Connection refused")

        status, message = _check_url(mock_client, "https://example.com")
        assert status is None
        assert "Connection refused" in message

    def test_url_timeout(self) -> None:
        """Test avec un timeout."""
        import httpx

        mock_client = MagicMock()
        mock_client.head.side_effect = httpx.ReadTimeout("Timeout")

        status, _message = _check_url(mock_client, "https://example.com")
        assert status is None


# =============================================================================
# Tests de run_import
# =============================================================================


class TestRunImport:
    """Tests pour run_import."""

    def test_unknown_product(self) -> None:
        """Test avec un produit inconnu."""
        from pgboundary.cli_load import run_import

        with (
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
            patch("pgboundary.cli_load.console"),
        ):
            mock_catalog.return_value.get.return_value = None
            settings = MagicMock()

            results = run_import(["unknown-product"], {}, settings)
            assert results == {}

    def test_no_enabled_layers(self) -> None:
        """Test avec un produit sans couches activées."""
        from pgboundary.cli_load import run_import

        with (
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
            patch("pgboundary.cli_load.console"),
        ):
            mock_product = MagicMock()
            mock_catalog.return_value.get.return_value = mock_product
            settings = MagicMock()

            config = {"layers": {"COMMUNE": {"enabled": False}}}
            results = run_import(["test-product"], {"test-product": config}, settings)
            assert results == {}

    def test_successful_import(self) -> None:
        """Test d'un import réussi."""
        from pgboundary.cli_load import run_import

        with (
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
            patch("pgboundary.loaders.product_loader.ProductLoader") as mock_loader_cls,
            patch("pgboundary.cli_load.console"),
        ):
            mock_product = MagicMock()
            mock_product.name = "Test Product"
            mock_product.last_date = "2024-01-01"
            mock_catalog.return_value.get.return_value = mock_product

            mock_loader = MagicMock()
            mock_loader.load.return_value = 100
            mock_loader_cls.return_value = mock_loader

            settings = MagicMock()
            config = {
                "layers": {"COMMUNE": {"enabled": True}},
                "territory": "FRA",
                "format": "shp",
                "editions": ["2024"],
            }

            results = run_import(["test-product"], {"test-product": config}, settings)
            assert results["test-product"] == 100

    def test_import_with_error(self) -> None:
        """Test d'un import avec erreur."""
        from pgboundary.cli_load import run_import

        with (
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
            patch("pgboundary.loaders.product_loader.ProductLoader") as mock_loader_cls,
            patch("pgboundary.cli_load.console"),
        ):
            mock_product = MagicMock()
            mock_product.name = "Test Product"
            mock_product.last_date = None
            mock_catalog.return_value.get.return_value = mock_product

            mock_loader_cls.side_effect = Exception("Connection error")

            settings = MagicMock()
            config = {
                "layers": {"COMMUNE": {"enabled": True}},
                "territory": "FRA",
                "format": "shp",
                "editions": ["2024"],
            }

            results = run_import(["test-product"], {"test-product": config}, settings)
            assert results["test-product"] == 0


# =============================================================================
# Tests de show_import_selection
# =============================================================================


class TestShowImportSelection:
    """Tests pour show_import_selection."""

    def test_empty_imports(self) -> None:
        """Test avec aucun import configuré."""
        from pgboundary.cli_load import show_import_selection

        with patch("pgboundary.cli_load.console"):
            result = show_import_selection({})
            assert result == []

    def test_cancelled_selection(self) -> None:
        """Test avec sélection annulée."""
        from pgboundary.cli_load import show_import_selection

        mock_result = MagicMock()
        mock_result.cancelled = True

        with (
            patch("pgboundary.cli_widgets.select_toggle_list", return_value=mock_result),
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
        ):
            mock_catalog.return_value.get.return_value = None

            result = show_import_selection({"test-product": {"layers": {}, "editions": ["2024"]}})
            assert result == []
