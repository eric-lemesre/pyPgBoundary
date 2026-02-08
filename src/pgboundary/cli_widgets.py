"""Widgets CLI interactifs pour pgBoundary.

Ce module fournit des composants d'interface utilisateur réutilisables :
- CheckboxSelect : sélection multiple avec cases à cocher
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

import readchar
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

console = Console()

T = TypeVar("T")


@dataclass
class CheckboxItem:
    """Un élément de la liste de sélection."""

    label: str
    value: str
    selected: bool = False
    description: str | None = None


class CheckboxResult:
    """Résultat de la sélection checkbox."""

    def __init__(self, items: list[CheckboxItem], cancelled: bool = False) -> None:
        self.items = items
        self.cancelled = cancelled

    @property
    def selected_values(self) -> list[str]:
        """Retourne les valeurs sélectionnées."""
        return [item.value for item in self.items if item.selected]

    @property
    def selected_labels(self) -> list[str]:
        """Retourne les labels sélectionnés."""
        return [item.label for item in self.items if item.selected]

    def __bool__(self) -> bool:
        """True si au moins un élément est sélectionné et non annulé."""
        return not self.cancelled and len(self.selected_values) > 0


def checkbox_select(
    items: list[CheckboxItem],
    title: str = "Sélection",
    min_selected: int = 0,
    show_help: bool = True,
) -> CheckboxResult:
    """Affiche une liste de cases à cocher interactive.

    Args:
        items: Liste des éléments à afficher
        title: Titre du panneau
        min_selected: Nombre minimum d'éléments à sélectionner (0 = optionnel)
        show_help: Afficher l'aide en bas

    Returns:
        CheckboxResult avec les éléments sélectionnés

    Controls:
        ↑/↓ ou k/j : Naviguer
        Espace : Cocher/décocher
        a : Tout sélectionner
        n : Tout désélectionner
        Entrée : Valider
        Échap : Annuler et retour
    """
    cursor_pos = 0
    cancelled = False

    def render() -> Panel:
        """Génère le rendu du composant."""
        lines = []

        for i, item in enumerate(items):
            # Curseur et checkbox
            cursor = ">" if i == cursor_pos else " "
            checkbox = "[green]✓[/green]" if item.selected else "[dim]○[/dim]"

            # Label avec highlight si curseur
            label = f"[bold cyan]{item.label}[/bold cyan]" if i == cursor_pos else item.label

            line = f" {cursor} {checkbox} {label}"

            # Description si présente
            if item.description:
                line += f" [dim]- {item.description}[/dim]"

            lines.append(line)

        content = "\n".join(lines)

        if show_help:
            help_text = (
                "\n\n[dim]↑↓ naviguer │ espace cocher │ "
                "a tout │ n rien │ entrée valider │ échap retour[/dim]"
            )
            content += help_text

        # Compteur de sélection
        selected_count = sum(1 for item in items if item.selected)
        subtitle = f"{selected_count}/{len(items)} sélectionné(s)"

        return Panel(
            Text.from_markup(content),
            title=f"[bold]{title}[/bold]",
            subtitle=subtitle,
            border_style="blue",
        )

    with Live(render(), console=console, refresh_per_second=10, transient=True) as live:
        while True:
            key = readchar.readkey()

            if key == readchar.key.UP or key == "k":
                cursor_pos = (cursor_pos - 1) % len(items)
            elif key == readchar.key.DOWN or key == "j":
                cursor_pos = (cursor_pos + 1) % len(items)
            elif key == " ":
                items[cursor_pos].selected = not items[cursor_pos].selected
            elif key == "a":
                for item in items:
                    item.selected = True
            elif key == "n":
                for item in items:
                    item.selected = False
            elif key == readchar.key.ENTER or key == "\r" or key == "\n":
                selected_count = sum(1 for item in items if item.selected)
                if selected_count >= min_selected:
                    break
                # Si pas assez sélectionné, afficher un message
                console.print(
                    f"[yellow]Veuillez sélectionner au moins {min_selected} élément(s)[/yellow]"
                )
            elif key == readchar.key.ESCAPE or key == "\x1b":
                cancelled = True
                break

            live.update(render())

    return CheckboxResult(items, cancelled)


def select_layers(
    layers: list[tuple[str, str]],
    preselected: list[str] | None = None,
) -> CheckboxResult:
    """Sélection interactive des couches.

    Args:
        layers: Liste de tuples (nom_couche, description)
        preselected: Liste des couches pré-sélectionnées (None = toutes)

    Returns:
        CheckboxResult avec les couches sélectionnées
    """
    if preselected is None:
        # Par défaut, tout est sélectionné
        preselected = [layer[0] for layer in layers]

    items = [
        CheckboxItem(
            label=name,
            value=name,
            selected=name in preselected,
            description=desc,
        )
        for name, desc in layers
    ]

    return checkbox_select(items, title="Couches à importer", min_selected=1)


def select_years(
    available_years: list[str] | None = None,
    preselected: list[str] | None = None,
) -> CheckboxResult:
    """Sélection interactive des millésimes.

    Args:
        available_years: Liste des années disponibles (défaut: 5 dernières)
        preselected: Liste des années pré-sélectionnées

    Returns:
        CheckboxResult avec les années sélectionnées
    """
    from datetime import datetime

    if available_years is None:
        current_year = datetime.now().year
        available_years = [str(year) for year in range(current_year, current_year - 5, -1)]

    if preselected is None:
        preselected = [available_years[0]] if available_years else []

    items = [
        CheckboxItem(
            label=year,
            value=year,
            selected=year in preselected,
            description="dernière version" if i == 0 else None,
        )
        for i, year in enumerate(available_years)
    ]

    return checkbox_select(items, title="Millésimes à importer", min_selected=1)
