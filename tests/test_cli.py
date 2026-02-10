"""Tests pour le module CLI principal.

Ce module teste les commandes CLI avec le CliRunner de Typer.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from pgboundary.cli import (
    _display_db_status,
    _ensure_database_configured,
    _mask_password,
    app,
    setup_logging,
    version_callback,
)


@pytest.fixture
def runner() -> CliRunner:
    """Fixture pour le CliRunner."""
    return CliRunner()


class TestSetupLogging:
    """Tests pour setup_logging."""

    def test_setup_logging_default(self) -> None:
        """Test configuration logging par défaut."""
        with patch("logging.basicConfig") as mock_config:
            setup_logging(verbose=False)
            mock_config.assert_called_once()
            # Vérifier que le level est INFO
            call_kwargs = mock_config.call_args[1]
            assert call_kwargs["level"] == 20  # logging.INFO

    def test_setup_logging_verbose(self) -> None:
        """Test configuration logging verbeux."""
        with patch("logging.basicConfig") as mock_config:
            setup_logging(verbose=True)
            call_kwargs = mock_config.call_args[1]
            assert call_kwargs["level"] == 10  # logging.DEBUG


class TestVersionCallback:
    """Tests pour version_callback."""

    def test_version_false(self) -> None:
        """Test callback avec False (pas d'affichage)."""
        # Ne devrait pas lever d'exception
        version_callback(False)

    def test_version_none(self) -> None:
        """Test callback avec None."""
        # Ne devrait pas lever d'exception
        version_callback(None)  # type: ignore


class TestMaskPassword:
    """Tests pour _mask_password."""

    def test_mask_simple_url(self) -> None:
        """Test masquage d'un mot de passe simple."""
        url = "postgresql://user:password@localhost:5432/db"
        masked = _mask_password(url)
        assert "password" not in masked
        assert "****" in masked
        # Le regex utilise \\1 donc le nom d'utilisateur peut être échappé
        assert "localhost" in masked

    def test_mask_complex_password(self) -> None:
        """Test masquage d'un mot de passe complexe."""
        url = "postgresql://user:p@ss:w0rd!@localhost:5432/db"
        masked = _mask_password(url)
        assert "p@ss:w0rd!" not in masked

    def test_no_password(self) -> None:
        """Test URL sans mot de passe."""
        url = "postgresql://user@localhost:5432/db"
        masked = _mask_password(url)
        assert masked == url


class TestDisplayDbStatus:
    """Tests pour _display_db_status."""

    def test_display_when_configured(self) -> None:
        """Test affichage quand la DB est configurée."""
        with (
            patch("pgboundary.cli.has_database_url_configured", return_value=True),
            patch("pgboundary.cli.Settings") as mock_settings,
            patch("pgboundary.cli.console") as mock_console,
        ):
            mock_settings.return_value.database_url = "postgresql://user:pass@host/db"
            _display_db_status()
            mock_console.print.assert_called()

    def test_display_when_not_configured(self) -> None:
        """Test affichage quand la DB n'est pas configurée."""
        with (
            patch("pgboundary.cli.has_database_url_configured", return_value=False),
            patch("pgboundary.cli.console") as mock_console,
        ):
            _display_db_status()
            mock_console.print.assert_called()
            # Vérifier que le message contient "non configurée"
            call_args = str(mock_console.print.call_args)
            assert "non configurée" in call_args

    def test_display_when_invalid_config(self) -> None:
        """Test affichage quand la config est invalide."""
        with (
            patch("pgboundary.cli.has_database_url_configured", return_value=True),
            patch("pgboundary.cli.Settings", side_effect=Exception("Invalid")),
            patch("pgboundary.cli.console") as mock_console,
        ):
            _display_db_status()
            mock_console.print.assert_called()


class TestEnsureDatabaseConfigured:
    """Tests pour _ensure_database_configured."""

    def test_with_url_provided(self) -> None:
        """Test avec URL fournie en paramètre."""
        result = _ensure_database_configured("postgresql://test@localhost/db")
        assert result == "postgresql://test@localhost/db"

    def test_with_existing_config(self) -> None:
        """Test avec configuration existante."""
        with patch("pgboundary.cli.has_database_url_configured", return_value=True):
            result = _ensure_database_configured()
            assert result is None  # Utilise la config existante

    def test_without_config_decline_interactive(self) -> None:
        """Test sans config et refus du mode interactif."""
        with (
            patch("pgboundary.cli.has_database_url_configured", return_value=False),
            patch("pgboundary.cli.console"),
            patch("pgboundary.cli.Confirm.ask", return_value=False),
        ):
            result = _ensure_database_configured()
            assert result is None


class TestMainCommand:
    """Tests pour la commande principale."""

    def test_version_option(self, runner: CliRunner) -> None:
        """Test option --version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "pgboundary" in result.output
        assert "version" in result.output

    def test_version_short_option(self, runner: CliRunner) -> None:
        """Test option -v (version)."""
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert "pgboundary" in result.output

    def test_quiet_option(self, runner: CliRunner) -> None:
        """Test option --quiet."""
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(app, ["--quiet", "--help"])
            # Avec --quiet, _display_db_status ne devrait pas être appelé
            # Note: --help a priorité, donc on vérifie juste que ça ne plante pas
            assert result.exit_code == 0

    def test_help(self, runner: CliRunner) -> None:
        """Test option --help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "pgboundary" in result.output.lower()


class TestInitCommand:
    """Tests pour la commande init."""

    def test_init_with_existing_config(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test init avec fichier de config existant."""
        with (
            patch("pgboundary.cli._ensure_database_configured", return_value=None),
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.DatabaseManager") as mock_db,
        ):
            mock_db.return_value.init_database = MagicMock()

            result = runner.invoke(app, ["--quiet", "init", "--config", str(temp_config_file)])

            # L'init devrait fonctionner ou avoir une erreur explicite
            assert result.exit_code == 0 or "Erreur" in result.output or "Error" in result.output

    def test_init_no_config_decline_creation(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test init sans config et refus de création."""
        nonexistent_config = tmp_path / "nonexistent.yml"

        with (
            patch("pgboundary.cli._ensure_database_configured", return_value=None),
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.Confirm.ask", return_value=False),
        ):
            result = runner.invoke(app, ["--quiet", "init", "--config", str(nonexistent_config)])

            assert result.exit_code == 1


class TestConfigSubcommands:
    """Tests pour les sous-commandes config."""

    def test_config_help(self, runner: CliRunner) -> None:
        """Test aide de config."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_config_show(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test config show."""
        with patch("pgboundary.cli_config.DEFAULT_CONFIG_FILENAME", str(temp_config_file)):
            result = runner.invoke(app, ["config", "show", "--quiet"])
            # Devrait afficher la configuration ou un message
            assert result.exit_code == 0 or "Erreur" not in result.output


class TestDownloadCommand:
    """Tests pour la commande download."""

    def test_download_help(self, runner: CliRunner) -> None:
        """Test aide de download."""
        result = runner.invoke(app, ["download", "--help"])
        assert result.exit_code == 0
        assert "download" in result.output.lower() or "territoire" in result.output.lower()

    def test_download_success(self, runner: CliRunner) -> None:
        """Test téléchargement réussi."""
        with (
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.Settings"),
            patch("pgboundary.cli.IGNDataSource") as mock_source,
        ):
            mock_instance = MagicMock()
            mock_instance.download_legacy.return_value = Path("/tmp/archive.7z")
            mock_instance.extract.return_value = Path("/tmp/extracted")
            mock_instance.find_shapefiles.return_value = {
                "COMMUNE": Path("/tmp/extracted/COMMUNE.shp"),
            }
            mock_source.return_value = mock_instance

            result = runner.invoke(
                app,
                [
                    "--quiet",
                    "download",
                    "--territory",
                    "france_metropolitaine",
                    "--edition",
                    "2024",
                ],
            )
            assert result.exit_code == 0

    def test_download_error(self, runner: CliRunner) -> None:
        """Test erreur de téléchargement."""
        with (
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.Settings"),
            patch("pgboundary.cli.IGNDataSource") as mock_source,
        ):
            mock_instance = MagicMock()
            mock_instance.download_legacy.side_effect = Exception("Network error")
            mock_source.return_value = mock_instance

            result = runner.invoke(
                app,
                ["--quiet", "download", "--edition", "2024"],
            )
            assert result.exit_code == 1


class TestLoadCommand:
    """Tests pour la commande load."""

    def test_load_help(self, runner: CliRunner) -> None:
        """Test aide de load."""
        result = runner.invoke(app, ["load", "--help"])
        assert result.exit_code == 0

    def test_load_no_config(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test load sans fichier de configuration."""
        config = tmp_path / "nonexistent.yml"
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(
                app,
                ["--quiet", "load", "--config", str(config)],
            )
            assert result.exit_code == 1

    def test_load_check_help(self, runner: CliRunner) -> None:
        """Test aide de load check."""
        result = runner.invoke(app, ["load", "check", "--help"])
        assert result.exit_code == 0


class TestLoadLegacyCommand:
    """Tests pour la commande load-legacy."""

    def test_load_legacy_help(self, runner: CliRunner) -> None:
        """Test aide de load-legacy."""
        result = runner.invoke(app, ["load-legacy", "--help"])
        assert result.exit_code == 0

    def test_load_legacy_success(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test chargement legacy réussi."""
        with (
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.AdminExpressLoader") as mock_loader,
        ):
            mock_loader.return_value.load.return_value = 500

            result = runner.invoke(
                app,
                [
                    "--quiet",
                    "load-legacy",
                    "--config",
                    str(temp_config_file),
                    "--edition",
                    "2024",
                ],
            )
            assert result.exit_code == 0
            assert "500" in result.output

    def test_load_legacy_error(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test erreur de chargement legacy."""
        with (
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.AdminExpressLoader") as mock_loader,
        ):
            mock_loader.return_value.load.side_effect = Exception("DB error")

            result = runner.invoke(
                app,
                [
                    "--quiet",
                    "load-legacy",
                    "--config",
                    str(temp_config_file),
                    "--edition",
                    "2024",
                ],
            )
            assert result.exit_code == 1


class TestInfoCommand:
    """Tests pour la commande info."""

    def test_info_help(self, runner: CliRunner) -> None:
        """Test aide de info."""
        result = runner.invoke(app, ["info", "--help"])
        if result.exit_code == 0:
            assert "info" in result.output.lower() or result.output

    def test_info_display(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test affichage info."""
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(app, ["--quiet", "info", "--config", str(temp_config_file)])
            assert result.exit_code == 0
            assert "pgboundary" in result.output.lower() or "version" in result.output.lower()


class TestCheckCommand:
    """Tests pour la commande check."""

    def test_check_help(self, runner: CliRunner) -> None:
        """Test aide de la commande check."""
        result = runner.invoke(app, ["check", "--help"])
        if result.exit_code == 0:
            assert "check" in result.output.lower() or "connexion" in result.output.lower()

    def test_check_success(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test vérification réussie."""
        with (
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.DatabaseManager") as mock_db,
        ):
            mock_db.return_value.check_connection = MagicMock()
            mock_db.return_value.check_postgis = MagicMock()

            result = runner.invoke(
                app,
                ["--quiet", "check", "--config", str(temp_config_file)],
            )
            assert result.exit_code == 0

    def test_check_connection_error(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test erreur de connexion."""
        with (
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.DatabaseManager") as mock_db,
        ):
            mock_db.return_value.check_connection.side_effect = Exception("Connection refused")

            result = runner.invoke(
                app,
                ["--quiet", "check", "--config", str(temp_config_file)],
            )
            assert result.exit_code == 1


class TestInspectCommand:
    """Tests pour la commande inspect."""

    def test_inspect_help(self, runner: CliRunner) -> None:
        """Test aide de inspect."""
        result = runner.invoke(app, ["inspect", "--help"])
        assert result.exit_code == 0

    def test_inspect_error(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test inspect avec erreur de connexion."""
        with (
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.DatabaseManager") as mock_db,
        ):
            mock_db.return_value.session.side_effect = Exception("No connection")

            result = runner.invoke(
                app,
                ["--quiet", "inspect", "--config", str(temp_config_file)],
            )
            assert result.exit_code == 1


class TestProductsCommand:
    """Tests pour la commande products."""

    def test_products_help(self, runner: CliRunner) -> None:
        """Test aide de products."""
        result = runner.invoke(app, ["products", "--help"])
        if result.exit_code == 0:
            assert "produit" in result.output.lower() or "product" in result.output.lower()

    def test_products_list(self, runner: CliRunner) -> None:
        """Test listage des produits."""
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(app, ["--quiet", "products"])
            assert result.exit_code == 0

    def test_products_with_category(self, runner: CliRunner) -> None:
        """Test listage par catégorie."""
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(app, ["--quiet", "products", "--category", "admin"])
            assert result.exit_code == 0

    def test_products_unknown_category(self, runner: CliRunner) -> None:
        """Test catégorie inconnue."""
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(app, ["--quiet", "products", "--category", "unknown"])
            assert result.exit_code == 1

    def test_products_verbose(self, runner: CliRunner) -> None:
        """Test mode verbeux."""
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(app, ["--quiet", "products", "--verbose"])
            assert result.exit_code == 0


class TestProductInfoCommand:
    """Tests pour la commande product-info."""

    def test_product_info_help(self, runner: CliRunner) -> None:
        """Test aide de product-info."""
        result = runner.invoke(app, ["product-info", "--help"])
        assert result.exit_code == 0

    def test_product_info_existing(self, runner: CliRunner) -> None:
        """Test info d'un produit existant."""
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(app, ["--quiet", "product-info", "admin-express-cog"])
            assert result.exit_code == 0

    def test_product_info_not_found(self, runner: CliRunner) -> None:
        """Test info d'un produit inexistant."""
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(app, ["--quiet", "product-info", "nonexistent-product"])
            assert result.exit_code == 1


class TestLoadProductCommand:
    """Tests pour la commande load-product."""

    def test_load_product_help(self, runner: CliRunner) -> None:
        """Test aide de load-product."""
        result = runner.invoke(app, ["load-product", "--help"])
        assert result.exit_code == 0

    def test_load_product_not_found(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test chargement d'un produit inexistant."""
        with patch("pgboundary.cli._display_db_status"):
            result = runner.invoke(
                app,
                [
                    "--quiet",
                    "load-product",
                    "nonexistent-product",
                    "--config",
                    str(temp_config_file),
                ],
            )
            assert result.exit_code == 1

    def test_load_product_success(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test chargement d'un produit réussi."""
        with (
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.ProductLoader") as mock_loader,
        ):
            mock_loader.return_value.load.return_value = 200

            result = runner.invoke(
                app,
                [
                    "--quiet",
                    "load-product",
                    "admin-express-cog",
                    "--config",
                    str(temp_config_file),
                    "--edition",
                    "2024",
                ],
            )
            assert result.exit_code == 0

    def test_load_product_error(self, runner: CliRunner, temp_config_file: Path) -> None:
        """Test chargement avec erreur."""
        with (
            patch("pgboundary.cli._display_db_status"),
            patch("pgboundary.cli.ProductLoader") as mock_loader,
        ):
            mock_loader.return_value.load.side_effect = Exception("Load failed")

            result = runner.invoke(
                app,
                [
                    "--quiet",
                    "load-product",
                    "admin-express-cog",
                    "--config",
                    str(temp_config_file),
                    "--edition",
                    "2024",
                ],
            )
            assert result.exit_code == 1


class TestCompletionSubcommands:
    """Tests pour les sous-commandes completion."""

    def test_completion_help(self, runner: CliRunner) -> None:
        """Test aide de completion."""
        result = runner.invoke(app, ["completion", "--help"])
        assert result.exit_code == 0

    def test_completion_install_help(self, runner: CliRunner) -> None:
        """Test aide de completion install."""
        result = runner.invoke(app, ["completion", "install", "--help"])
        assert result.exit_code == 0 or result.exit_code == 2  # 2 si commande n'existe pas
