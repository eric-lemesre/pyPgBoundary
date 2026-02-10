"""Tests pour le module CLI de complétion (cli_completion.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

from pgboundary.cli_completion import (
    Shell,
    _detect_shell,
    _get_completion_script,
    completion_app,
)


@pytest.fixture
def runner() -> CliRunner:
    """Fixture pour le CliRunner."""
    return CliRunner()


# =============================================================================
# Tests de _detect_shell
# =============================================================================


class TestDetectShell:
    """Tests pour _detect_shell."""

    def test_detect_bash(self) -> None:
        """Test détection de bash."""
        with patch.dict("os.environ", {"SHELL": "/bin/bash"}):
            assert _detect_shell() == Shell.BASH

    def test_detect_zsh(self) -> None:
        """Test détection de zsh."""
        with patch.dict("os.environ", {"SHELL": "/bin/zsh"}):
            assert _detect_shell() == Shell.ZSH

    def test_detect_fish(self) -> None:
        """Test détection de fish."""
        with patch.dict("os.environ", {"SHELL": "/usr/bin/fish"}):
            assert _detect_shell() == Shell.FISH

    def test_detect_unknown_linux(self) -> None:
        """Test avec un shell inconnu sur Linux."""
        with (
            patch.dict("os.environ", {"SHELL": "/bin/sh"}),
            patch("pgboundary.cli_completion.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            assert _detect_shell() is None

    def test_detect_no_shell_env(self) -> None:
        """Test sans variable SHELL."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("pgboundary.cli_completion.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            assert _detect_shell() is None

    def test_detect_windows_fallback(self) -> None:
        """Test fallback sur Windows."""
        with (
            patch.dict("os.environ", {"SHELL": ""}),
            patch("pgboundary.cli_completion.sys") as mock_sys,
        ):
            mock_sys.platform = "win32"
            assert _detect_shell() == Shell.POWERSHELL

    def test_detect_powershell(self) -> None:
        """Test détection de PowerShell."""
        with patch.dict("os.environ", {"SHELL": "/usr/bin/pwsh"}):
            assert _detect_shell() == Shell.POWERSHELL


# =============================================================================
# Tests de _get_completion_script
# =============================================================================


class TestGetCompletionScript:
    """Tests pour _get_completion_script."""

    def test_bash_script(self) -> None:
        """Test génération script bash."""
        with patch("pgboundary.cli_completion.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="# bash completion script")
            result = _get_completion_script(Shell.BASH)
            assert isinstance(result, str)

    def test_zsh_script(self) -> None:
        """Test génération script zsh."""
        with patch("pgboundary.cli_completion.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="# zsh completion script")
            result = _get_completion_script(Shell.ZSH)
            assert isinstance(result, str)

    def test_script_fallback_on_error(self) -> None:
        """Test fallback quand subprocess échoue."""
        with patch(
            "pgboundary.cli_completion.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = _get_completion_script(Shell.BASH)
            assert "pgboundary" in result


# =============================================================================
# Tests de completion_show
# =============================================================================


class TestCompletionShow:
    """Tests pour completion_show."""

    def test_show_help(self, runner: CliRunner) -> None:
        """Test aide de completion show."""
        result = runner.invoke(completion_app, ["show", "--help"])
        assert result.exit_code == 0

    def test_show_with_shell_arg(self, runner: CliRunner) -> None:
        """Test show avec argument shell."""
        result = runner.invoke(completion_app, ["show", "bash"])
        assert result.exit_code == 0
        assert "bash" in result.output.lower()

    def test_show_auto_detect(self, runner: CliRunner) -> None:
        """Test show avec auto-détection."""
        with patch(
            "pgboundary.cli_completion._detect_shell",
            return_value=Shell.BASH,
        ):
            result = runner.invoke(completion_app, ["show"])
            assert result.exit_code == 0

    def test_show_no_shell_detected(self, runner: CliRunner) -> None:
        """Test show quand aucun shell n'est détecté."""
        with patch(
            "pgboundary.cli_completion._detect_shell",
            return_value=None,
        ):
            result = runner.invoke(completion_app, ["show"])
            assert result.exit_code == 1


# =============================================================================
# Tests de completion_install
# =============================================================================


class TestCompletionInstall:
    """Tests pour completion_install."""

    def test_install_help(self, runner: CliRunner) -> None:
        """Test aide de completion install."""
        result = runner.invoke(completion_app, ["install", "--help"])
        assert result.exit_code == 0

    def test_install_no_shell_detected(self, runner: CliRunner) -> None:
        """Test install sans détection de shell."""
        with patch(
            "pgboundary.cli_completion._detect_shell",
            return_value=None,
        ):
            result = runner.invoke(completion_app, ["install"])
            assert result.exit_code == 1

    def test_install_already_installed(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test install quand déjà installé."""
        # Créer un fichier bashrc avec la complétion
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("# existing config\n_PGBOUNDARY_COMPLETE=bash_source\n")

        with (
            patch(
                "pgboundary.cli_completion.SHELL_CONFIG_FILES",
                {Shell.BASH: [str(bashrc)]},
            ),
        ):
            result = runner.invoke(completion_app, ["install", "bash"])
            assert result.exit_code == 0
            assert "déjà configurée" in result.output

    def test_install_fresh(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test installation fraîche."""
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("# existing config\n")

        with patch(
            "pgboundary.cli_completion.SHELL_CONFIG_FILES",
            {Shell.BASH: [str(bashrc)]},
        ):
            result = runner.invoke(completion_app, ["install", "bash"])
            assert result.exit_code == 0
            assert "succès" in result.output

            # Vérifier que le script a été ajouté
            content = bashrc.read_text()
            assert "pgboundary" in content

    def test_install_creates_parent_dir(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test que l'installation crée les répertoires parents."""
        config_file = tmp_path / "subdir" / "completions" / "pgboundary.fish"

        with patch(
            "pgboundary.cli_completion.SHELL_CONFIG_FILES",
            {Shell.FISH: [str(config_file)]},
        ):
            result = runner.invoke(completion_app, ["install", "fish"])
            assert result.exit_code == 0
            assert config_file.parent.exists()


# =============================================================================
# Tests de completion_status
# =============================================================================


class TestCompletionStatus:
    """Tests pour completion_status."""

    def test_status_help(self, runner: CliRunner) -> None:
        """Test aide de completion status."""
        result = runner.invoke(completion_app, ["status", "--help"])
        assert result.exit_code == 0

    def test_status_display(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test affichage du statut."""
        # Créer des fichiers de config simulés
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("# nothing\n")

        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("# has completion\n_PGBOUNDARY_COMPLETE=zsh_source\n")

        with (
            patch(
                "pgboundary.cli_completion.SHELL_CONFIG_FILES",
                {
                    Shell.BASH: [str(bashrc)],
                    Shell.ZSH: [str(zshrc)],
                    Shell.FISH: [str(tmp_path / ".config" / "fish" / "pgboundary.fish")],
                    Shell.POWERSHELL: [str(tmp_path / "profile.ps1")],
                },
            ),
            patch(
                "pgboundary.cli_completion._detect_shell",
                return_value=Shell.ZSH,
            ),
        ):
            result = runner.invoke(completion_app, ["status"])
            assert result.exit_code == 0
            # La table devrait être affichée
            assert "bash" in result.output.lower() or "Shell" in result.output
