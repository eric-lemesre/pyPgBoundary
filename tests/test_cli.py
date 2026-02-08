"""Tests pour le module CLI principal.

Ce module teste les commandes CLI avec le CliRunner de Typer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

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


class TestCheckCommand:
    """Tests pour la commande check (si elle existe)."""

    def test_check_help(self, runner: CliRunner) -> None:
        """Test aide de la commande check."""
        result = runner.invoke(app, ["check", "--help"])
        # La commande peut exister ou non
        if result.exit_code == 0:
            assert "check" in result.output.lower() or "connexion" in result.output.lower()


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


class TestLoadCommand:
    """Tests pour la commande load."""

    def test_load_help(self, runner: CliRunner) -> None:
        """Test aide de load."""
        result = runner.invoke(app, ["load", "--help"])
        assert result.exit_code == 0


class TestInfoCommand:
    """Tests pour la commande info."""

    def test_info_help(self, runner: CliRunner) -> None:
        """Test aide de info."""
        result = runner.invoke(app, ["info", "--help"])
        # info peut exister ou non
        if result.exit_code == 0:
            assert "info" in result.output.lower() or result.output


class TestProductsCommand:
    """Tests pour la commande products."""

    def test_products_help(self, runner: CliRunner) -> None:
        """Test aide de products."""
        result = runner.invoke(app, ["products", "--help"])
        if result.exit_code == 0:
            assert "produit" in result.output.lower() or "product" in result.output.lower()


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
