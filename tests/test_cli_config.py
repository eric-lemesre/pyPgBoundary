"""Tests pour le module CLI de configuration (cli_config.py)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from pgboundary.cli_config import (
    _format_size,
    _get_enabled_layers_count,
    _get_product_editions,
    _mask_password,
    config_app,
)


@pytest.fixture
def runner() -> CliRunner:
    """Fixture pour le CliRunner."""
    return CliRunner()


@pytest.fixture
def temp_config_file() -> Path:
    """Crée un fichier de configuration temporaire."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("""
storage:
  mode: schema
  schema_name: geo_test

field_prefixes:
  code: cd_
  label: lb_
  date: dt_

srid: 4326

imports: {}
""")
        f.flush()
        path = Path(f.name)
    yield path  # type: ignore[misc]
    path.unlink(missing_ok=True)


# =============================================================================
# Tests des fonctions pures
# =============================================================================


class TestGetEnabledLayersCount:
    """Tests pour _get_enabled_layers_count."""

    def test_no_layers(self) -> None:
        """Test avec aucune couche."""
        config: dict = {}
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 0
        assert total == 0

    def test_empty_layers_dict(self) -> None:
        """Test avec un dict de couches vide."""
        config = {"layers": {}}
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 0
        assert total == 0

    def test_all_enabled(self) -> None:
        """Test avec toutes les couches activées."""
        config = {
            "layers": {
                "COMMUNE": {"enabled": True},
                "REGION": {"enabled": True},
                "DEPARTEMENT": {"enabled": True},
            }
        }
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 3
        assert total == 3

    def test_some_disabled(self) -> None:
        """Test avec certaines couches désactivées."""
        config = {
            "layers": {
                "COMMUNE": {"enabled": True},
                "REGION": {"enabled": False},
                "DEPARTEMENT": {"enabled": True},
            }
        }
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 2
        assert total == 3

    def test_all_disabled(self) -> None:
        """Test avec toutes les couches désactivées."""
        config = {
            "layers": {
                "COMMUNE": {"enabled": False},
                "REGION": {"enabled": False},
            }
        }
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 0
        assert total == 2

    def test_default_enabled_when_key_missing(self) -> None:
        """Test que les couches sans clé 'enabled' sont activées par défaut."""
        config = {
            "layers": {
                "COMMUNE": {},
                "REGION": {"table_name": "region"},
            }
        }
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 2
        assert total == 2

    def test_legacy_list_structure(self) -> None:
        """Test avec l'ancienne structure en liste."""
        config = {"layers": ["COMMUNE", "REGION"]}
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 2
        assert total == 2

    def test_legacy_empty_list(self) -> None:
        """Test avec une liste vide (legacy)."""
        config = {"layers": []}
        enabled, total = _get_enabled_layers_count(config)
        assert enabled == 0
        assert total == 0


class TestFormatSize:
    """Tests pour _format_size."""

    def test_none(self) -> None:
        """Test avec None."""
        assert _format_size(None) == "?"

    def test_megabytes(self) -> None:
        """Test avec des Mo."""
        assert _format_size(500) == "500 Mo"

    def test_gigabytes(self) -> None:
        """Test avec des Go."""
        assert _format_size(2048) == "2.0 Go"

    def test_small_gigabytes(self) -> None:
        """Test avec juste au-dessus de 1 Go."""
        assert _format_size(1024) == "1.0 Go"

    def test_zero(self) -> None:
        """Test avec 0."""
        assert _format_size(0) == "0 Mo"

    def test_float_value(self) -> None:
        """Test avec un float."""
        assert _format_size(1.5) == "1.5 Mo"

    def test_large_value(self) -> None:
        """Test avec une très grande valeur."""
        result = _format_size(10240)
        assert "Go" in result


class TestGetProductEditions:
    """Tests pour _get_product_editions."""

    def test_none_product(self) -> None:
        """Test avec un produit None."""
        assert _get_product_editions(None) is None

    def test_product_without_dates(self) -> None:
        """Test avec un produit sans dates."""
        product = MagicMock()
        product.available_dates = None
        assert _get_product_editions(product) is None

    def test_product_with_empty_dates(self) -> None:
        """Test avec un produit avec des dates vides."""
        product = MagicMock()
        product.available_dates = []
        assert _get_product_editions(product) is None

    def test_product_with_dates(self) -> None:
        """Test avec un produit avec des dates."""
        product = MagicMock()
        product.available_dates = ["2024-01-01", "2023-06-15"]
        result = _get_product_editions(product)
        assert result == ["2024-01-01", "2023-06-15"]

    def test_product_with_year_dates(self) -> None:
        """Test avec des dates au format année."""
        product = MagicMock()
        product.available_dates = ["2024", "2023"]
        result = _get_product_editions(product)
        assert result == ["2024", "2023"]


class TestMaskPassword:
    """Tests pour _mask_password."""

    def test_mask_password_simple(self) -> None:
        """Test masquage simple."""
        url = "postgresql://user:secret@localhost/db"
        masked = _mask_password(url)
        assert "secret" not in masked
        assert "****" in masked

    def test_no_password(self) -> None:
        """Test sans mot de passe."""
        url = "postgresql://user@localhost/db"
        masked = _mask_password(url)
        assert masked == url


# =============================================================================
# Tests des commandes typer
# =============================================================================


class TestConfigMain:
    """Tests pour config_main (callback)."""

    def test_config_help(self, runner: CliRunner) -> None:
        """Test aide de config."""
        result = runner.invoke(config_app, ["--help"])
        assert result.exit_code == 0

    def test_config_no_file(self, runner: CliRunner) -> None:
        """Test config sans fichier existant."""
        with patch(
            "pgboundary.cli_config._get_config_path",
            return_value=Path("/tmp/nonexistent_pgboundary.yml"),
        ):
            result = runner.invoke(config_app)
            assert "non trouvé" in result.output or result.exit_code == 0

    def test_config_with_file(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test config avec fichier existant."""
        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=temp_config_file,
            ),
            patch("pgboundary.cli_config.Settings") as mock_settings,
        ):
            mock_settings.return_value.database_url = "postgresql://u:p@h/d"
            mock_settings.return_value.data_dir = Path("/tmp/data")
            result = runner.invoke(config_app)
            assert result.exit_code == 0


class TestConfigInfo:
    """Tests pour config_info."""

    def test_info_no_file(self, runner: CliRunner) -> None:
        """Test info sans fichier."""
        with patch(
            "pgboundary.cli_config._get_config_path",
            return_value=Path("/tmp/nonexistent.yml"),
        ):
            result = runner.invoke(config_app, ["info"])
            assert result.exit_code == 1

    def test_info_with_file(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test info avec fichier existant."""
        with patch(
            "pgboundary.cli_config._get_config_path",
            return_value=temp_config_file,
        ):
            result = runner.invoke(config_app, ["info"])
            assert result.exit_code == 0


class TestConfigInit:
    """Tests pour config_init."""

    def test_init_existing_file_decline(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test init avec fichier existant et refus de modifier."""
        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=temp_config_file,
            ),
            patch("pgboundary.cli_config.Confirm.ask", return_value=False),
        ):
            result = runner.invoke(config_app, ["init"])
            assert result.exit_code == 0

    def test_init_force(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test init avec --force."""
        config_path = tmp_path / "pgboundary.yml"
        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=config_path,
            ),
            patch(
                "pgboundary.cli_config.Prompt.ask",
                side_effect=["schema", "geo_test", "4326", "/tmp/data"],
            ),
            patch("pgboundary.cli_config.Confirm.ask", return_value=False),
            patch("pgboundary.cli_config.save_config"),
        ):
            result = runner.invoke(config_app, ["init", "--force"])
            assert result.exit_code == 0


class TestConfigUpdate:
    """Tests pour config_update."""

    def test_update_no_file(self, runner: CliRunner) -> None:
        """Test update sans fichier."""
        with patch(
            "pgboundary.cli_config._get_config_path",
            return_value=Path("/tmp/nonexistent.yml"),
        ):
            result = runner.invoke(config_app, ["update"])
            assert result.exit_code == 1

    def test_update_quit_immediately(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test update puis quitter immédiatement."""
        mock_menu_result = MagicMock()
        mock_menu_result.cancelled = True

        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=temp_config_file,
            ),
            patch(
                "pgboundary.cli_widgets.select_menu",
                return_value=mock_menu_result,
            ),
            patch("pgboundary.cli_config.save_config"),
        ):
            result = runner.invoke(config_app, ["update"])
            assert result.exit_code == 0


class TestDataAdd:
    """Tests pour data_add."""

    def test_add_no_config_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test ajout sans fichier de config (crée un défaut)."""
        config_path = tmp_path / "pgboundary.yml"
        mock_result = MagicMock()
        mock_result.cancelled = True
        mock_result.value = None

        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=config_path,
            ),
            patch(
                "pgboundary.cli_widgets.select_single",
                return_value=mock_result,
            ),
            patch("pgboundary.cli_config.save_config"),
        ):
            result = runner.invoke(config_app, ["data", "add"])
            assert result.exit_code == 0


class TestDataRemove:
    """Tests pour data_remove."""

    def test_remove_no_config(self, runner: CliRunner) -> None:
        """Test suppression sans fichier de config."""
        with patch(
            "pgboundary.cli_config._get_config_path",
            return_value=Path("/tmp/nonexistent.yml"),
        ):
            result = runner.invoke(config_app, ["data", "remove"])
            assert result.exit_code == 1

    def test_remove_product_directly(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test suppression directe d'un produit."""
        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=temp_config_file,
            ),
            patch("pgboundary.cli_config.load_config") as mock_load,
            patch("pgboundary.cli_config.save_config"),
        ):
            mock_config = MagicMock()
            mock_config.imports = {"test-product": {"layers": {}}}
            mock_load.return_value = mock_config

            result = runner.invoke(config_app, ["data", "remove", "test-product"])
            assert result.exit_code == 0

    def test_remove_product_not_found(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test suppression d'un produit inexistant."""
        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=temp_config_file,
            ),
            patch("pgboundary.cli_config.load_config") as mock_load,
        ):
            mock_config = MagicMock()
            mock_config.imports = {"other-product": {}}
            mock_load.return_value = mock_config

            result = runner.invoke(config_app, ["data", "remove", "nonexistent"])
            assert "non trouvés" in result.output or result.exit_code == 0

    def test_remove_empty_imports(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test suppression avec aucun produit configuré."""
        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=temp_config_file,
            ),
            patch("pgboundary.cli_config.load_config") as mock_load,
        ):
            mock_config = MagicMock()
            mock_config.imports = {}
            mock_load.return_value = mock_config

            result = runner.invoke(config_app, ["data", "remove"])
            assert result.exit_code == 0


class TestDataUpdate:
    """Tests pour data_update."""

    def test_update_quit_immediately(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test data update puis quitter immédiatement."""
        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=temp_config_file,
            ),
            patch("pgboundary.cli_config.load_config") as mock_load,
            patch(
                "pgboundary.cli_config.Prompt.ask",
                return_value="q",
            ),
            patch("pgboundary.cli_config.save_config"),
            patch("pgboundary.cli_config.get_default_catalog") as mock_catalog,
        ):
            mock_config = MagicMock()
            mock_config.imports = {}
            mock_load.return_value = mock_config
            mock_catalog.return_value.__iter__ = MagicMock(return_value=iter([]))

            result = runner.invoke(config_app, ["data", "update"])
            assert result.exit_code == 0


class TestConfigSyncProduct:
    """Tests pour config_sync_product."""

    def test_sync_no_config(self, runner: CliRunner) -> None:
        """Test sync sans fichier de config."""
        with patch(
            "pgboundary.cli_config._get_config_path",
            return_value=Path("/tmp/nonexistent.yml"),
        ):
            result = runner.invoke(config_app, ["sync-product"])
            assert result.exit_code == 1

    def test_sync_empty_imports(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test sync sans produits configurés."""
        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=temp_config_file,
            ),
            patch("pgboundary.cli_config.load_config") as mock_load,
        ):
            mock_config = MagicMock()
            mock_config.imports = {}
            mock_load.return_value = mock_config

            result = runner.invoke(config_app, ["sync-product"])
            assert result.exit_code == 0

    def test_sync_product_not_found(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test sync d'un produit non configuré."""
        with (
            patch(
                "pgboundary.cli_config._get_config_path",
                return_value=temp_config_file,
            ),
            patch("pgboundary.cli_config.load_config") as mock_load,
        ):
            mock_config = MagicMock()
            mock_config.imports = {"other-product": {}}
            mock_load.return_value = mock_config

            result = runner.invoke(config_app, ["sync-product", "nonexistent"])
            assert result.exit_code == 1
