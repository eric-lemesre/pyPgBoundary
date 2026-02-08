"""Widgets CLI interactifs pour pgBoundary.

Ce module fournit des composants d'interface utilisateur réutilisables :
- checkbox_select : sélection multiple avec cases à cocher
- select_single : sélection unique dans une liste
- select_layers : sélection des couches
- select_years : sélection des millésimes
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


def _is_escape_key(key: str) -> bool:
    """Vérifie si la touche est Échap (compatible multi-plateforme).

    La touche Échap génère le caractère ASCII 0x1B (27).
    Note: readchar.key.ESCAPE n'existe pas dans toutes les versions.
    """
    # ESC est le caractère ASCII 27 (0x1B)
    return key == "\x1b"


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
            elif _is_escape_key(key):
                cancelled = True
                break

            live.update(render())

    return CheckboxResult(items, cancelled)


@dataclass
class SelectItem:
    """Un élément de la liste de sélection unique."""

    label: str
    value: str
    description: str | None = None


class SelectResult:
    """Résultat de la sélection unique."""

    def __init__(self, item: SelectItem | None = None, cancelled: bool = False) -> None:
        self.item = item
        self.cancelled = cancelled

    @property
    def value(self) -> str | None:
        """Retourne la valeur sélectionnée."""
        return self.item.value if self.item else None

    @property
    def label(self) -> str | None:
        """Retourne le label sélectionné."""
        return self.item.label if self.item else None

    def __bool__(self) -> bool:
        """True si un élément est sélectionné et non annulé."""
        return not self.cancelled and self.item is not None


def select_single(
    items: list[SelectItem],
    title: str = "Sélection",
    default_index: int = 0,
    show_help: bool = True,
) -> SelectResult:
    """Affiche une liste de sélection unique interactive.

    Args:
        items: Liste des éléments à afficher
        title: Titre du panneau
        default_index: Index de l'élément sélectionné par défaut
        show_help: Afficher l'aide en bas

    Returns:
        SelectResult avec l'élément sélectionné

    Controls:
        ↑/↓ ou k/j : Naviguer
        Entrée : Valider
        Échap : Annuler et retour
    """
    if not items:
        return SelectResult(cancelled=True)

    cursor_pos = min(default_index, len(items) - 1)
    cancelled = False

    def render() -> Panel:
        """Génère le rendu du composant."""
        lines = []

        for i, item in enumerate(items):
            # Curseur et indicateur
            if i == cursor_pos:
                cursor = ">"
                indicator = "[green]●[/green]"
                label = f"[bold cyan]{item.label}[/bold cyan]"
            else:
                cursor = " "
                indicator = "[dim]○[/dim]"
                label = item.label

            line = f" {cursor} {indicator} {label}"

            # Description si présente
            if item.description:
                line += f" [dim]- {item.description}[/dim]"

            lines.append(line)

        content = "\n".join(lines)

        if show_help:
            help_text = "\n\n[dim]↑↓ naviguer │ entrée valider │ échap retour[/dim]"
            content += help_text

        return Panel(
            Text.from_markup(content),
            title=f"[bold]{title}[/bold]",
            border_style="blue",
        )

    with Live(render(), console=console, refresh_per_second=10, transient=True) as live:
        while True:
            key = readchar.readkey()

            if key == readchar.key.UP or key == "k":
                cursor_pos = (cursor_pos - 1) % len(items)
            elif key == readchar.key.DOWN or key == "j":
                cursor_pos = (cursor_pos + 1) % len(items)
            elif key == readchar.key.ENTER or key == "\r" or key == "\n":
                break
            elif _is_escape_key(key):
                cancelled = True
                break

            live.update(render())

    if cancelled:
        return SelectResult(cancelled=True)
    return SelectResult(items[cursor_pos])


def select_territory(
    territories: list[str],
    default: str = "FRA",
) -> SelectResult:
    """Sélection interactive du territoire.

    Args:
        territories: Liste des codes territoires disponibles
        default: Territoire par défaut

    Returns:
        SelectResult avec le territoire sélectionné
    """
    territory_names = {
        "FRA": "France entière",
        "FXX": "France métropolitaine",
        "GLP": "Guadeloupe",
        "MTQ": "Martinique",
        "GUF": "Guyane française",
        "REU": "La Réunion",
        "MYT": "Mayotte",
    }

    items = [
        SelectItem(
            label=code,
            value=code,
            description=territory_names.get(code, ""),
        )
        for code in territories
    ]

    default_index = 0
    for i, t in enumerate(territories):
        if t == default:
            default_index = i
            break

    return select_single(items, title="Territoire", default_index=default_index)


def select_format(
    formats: list[str],
    default: str = "shp",
) -> SelectResult:
    """Sélection interactive du format.

    Args:
        formats: Liste des formats disponibles
        default: Format par défaut

    Returns:
        SelectResult avec le format sélectionné
    """
    format_names = {
        "shp": "Shapefile (.shp)",
        "gpkg": "GeoPackage (.gpkg)",
        "geojson": "GeoJSON (.geojson)",
    }

    items = [
        SelectItem(
            label=fmt.upper(),
            value=fmt,
            description=format_names.get(fmt, ""),
        )
        for fmt in formats
    ]

    default_index = 0
    for i, f in enumerate(formats):
        if f == default:
            default_index = i
            break

    return select_single(items, title="Format", default_index=default_index)


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
