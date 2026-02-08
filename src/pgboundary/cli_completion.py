"""Commandes CLI pour la gestion de la complétion shell."""

from __future__ import annotations

import os
import subprocess
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


class Shell(StrEnum):
    """Shells supportés pour la complétion."""

    BASH = "bash"
    ZSH = "zsh"
    FISH = "fish"
    POWERSHELL = "powershell"


# Fichiers de configuration par shell
SHELL_CONFIG_FILES: dict[Shell, list[str]] = {
    Shell.BASH: ["~/.bashrc", "~/.bash_profile"],
    Shell.ZSH: ["~/.zshrc"],
    Shell.FISH: ["~/.config/fish/completions/pgboundary.fish"],
    Shell.POWERSHELL: ["$PROFILE"],
}

# Instructions d'installation par shell (Typer 0.21+)
INSTALL_INSTRUCTIONS: dict[Shell, str] = {
    Shell.BASH: 'eval "$(pgboundary --show-completion bash)"',
    Shell.ZSH: 'eval "$(pgboundary --show-completion zsh)"',
    Shell.FISH: "pgboundary --show-completion fish | source",
    Shell.POWERSHELL: "pgboundary --show-completion powershell | Invoke-Expression",
}

completion_app = typer.Typer(
    name="completion",
    help="Gestion de la complétion automatique pour le shell.",
    no_args_is_help=True,
)


def _detect_shell() -> Shell | None:
    """Détecte le shell actuel."""
    import os

    shell_path = os.environ.get("SHELL", "")
    shell_name = Path(shell_path).name.lower()

    if "zsh" in shell_name:
        return Shell.ZSH
    elif "bash" in shell_name:
        return Shell.BASH
    elif "fish" in shell_name:
        return Shell.FISH
    elif "pwsh" in shell_name or "powershell" in shell_name:
        return Shell.POWERSHELL

    # Fallback pour Windows
    if sys.platform == "win32":
        return Shell.POWERSHELL

    return None


def _get_completion_script(shell: Shell) -> str:
    """Génère le script de complétion pour un shell."""
    env_var_name = "_PGBOUNDARY_COMPLETE"
    env_var_value = f"{shell.value}_source"
    try:
        result = subprocess.run(
            ["pgboundary"],
            env={**os.environ, env_var_name: env_var_value},
            capture_output=True,
            text=True,
            check=False,
        )
        return str(result.stdout)
    except Exception:
        return INSTALL_INSTRUCTIONS[shell]


@completion_app.command("show")
def completion_show(
    shell: Annotated[
        Shell | None,
        typer.Argument(
            help="Shell cible (bash, zsh, fish, powershell). Auto-détecté si non spécifié."
        ),
    ] = None,
) -> None:
    """Affiche le script de complétion pour le shell spécifié."""
    if shell is None:
        shell = _detect_shell()
        if shell is None:
            console.print(
                "[red]Impossible de détecter le shell. "
                "Spécifiez-le explicitement : bash, zsh, fish, powershell[/red]"
            )
            raise typer.Exit(1)
        console.print(f"[dim]Shell détecté : {shell.value}[/dim]\n")

    instruction = INSTALL_INSTRUCTIONS[shell]

    console.print(
        Panel(
            f"[green]{instruction}[/green]",
            title=f"Script de complétion pour {shell.value}",
            subtitle="Ajoutez cette ligne à votre fichier de configuration",
        )
    )

    console.print("\n[dim]Fichiers de configuration suggérés :[/dim]")
    for config_file in SHELL_CONFIG_FILES[shell]:
        console.print(f"  • {config_file}")


@completion_app.command("install")
def completion_install(
    shell: Annotated[
        Shell | None,
        typer.Argument(
            help="Shell cible (bash, zsh, fish, powershell). Auto-détecté si non spécifié."
        ),
    ] = None,
) -> None:
    """Installe la complétion automatique pour le shell spécifié."""
    if shell is None:
        shell = _detect_shell()
        if shell is None:
            console.print(
                "[red]Impossible de détecter le shell. "
                "Spécifiez-le explicitement : bash, zsh, fish, powershell[/red]"
            )
            raise typer.Exit(1)
        console.print(f"[dim]Shell détecté : {shell.value}[/dim]")

    instruction = INSTALL_INSTRUCTIONS[shell]
    config_files = SHELL_CONFIG_FILES[shell]

    # Trouver le fichier de configuration existant
    target_file: Path | None = None
    for config_file in config_files:
        expanded = Path(config_file).expanduser()
        if expanded.exists():
            target_file = expanded
            break

    if target_file is None:
        # Utiliser le premier fichier par défaut
        target_file = Path(config_files[0]).expanduser()

    # Vérifier si déjà installé
    if target_file.exists():
        content = target_file.read_text()
        if "_PGBOUNDARY_COMPLETE" in content:
            console.print(f"[yellow]La complétion est déjà configurée dans {target_file}[/yellow]")
            raise typer.Exit(0)

    # Installer
    console.print(f"Installation de la complétion dans [bold]{target_file}[/bold]...")

    # Créer le répertoire parent si nécessaire (pour fish)
    target_file.parent.mkdir(parents=True, exist_ok=True)

    # Ajouter le script
    with target_file.open("a") as f:
        f.write(f"\n# pgboundary shell completion\n{instruction}\n")

    console.print("[green]✓[/green] Complétion installée avec succès !")
    console.print("\n[dim]Rechargez votre shell ou exécutez :[/dim]")
    console.print(f"  source {target_file}")


@completion_app.command("status")
def completion_status() -> None:
    """Affiche le statut de la complétion pour tous les shells."""
    table = Table(title="Statut de la complétion shell")
    table.add_column("Shell", style="cyan")
    table.add_column("Fichier config", style="dim")
    table.add_column("Statut", justify="center")

    for shell in Shell:
        config_files = SHELL_CONFIG_FILES[shell]
        installed = False
        found_file = "-"

        for config_file in config_files:
            expanded = Path(config_file).expanduser()
            if expanded.exists():
                found_file = str(expanded)
                content = expanded.read_text()
                if "_PGBOUNDARY_COMPLETE" in content:
                    installed = True
                break

        status = "[green]✓ Installé[/green]" if installed else "[dim]Non installé[/dim]"
        table.add_row(shell.value, found_file, status)

    console.print(table)

    # Détecter le shell actuel
    current_shell = _detect_shell()
    if current_shell:
        console.print(f"\n[dim]Shell actuel détecté : {current_shell.value}[/dim]")
