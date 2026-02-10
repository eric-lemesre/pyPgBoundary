"""Interactive CLI widgets for pgBoundary.

This module provides reusable user interface components:
- checkbox_select: multiple selection with checkboxes
- select_single: single selection from a list
- select_layers: layer selection
- select_years: vintage/year selection
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


def _is_cancel_key(key: str) -> bool:
    """Check if the key is a cancel key (r or Escape).

    Uses 'r' as the primary key because Escape does not work
    correctly in some IDE terminals.

    Args:
        key: Key pressed.

    Returns:
        True if it is a cancel key.
    """
    # 'r' for return (works everywhere)
    # ESC (0x1B) as an alternative (does not work in all IDEs)
    return key == "r" or key == "\x1b"


@dataclass
class CheckboxItem:
    """An item in the selection list."""

    label: str
    value: str
    selected: bool = False
    description: str | None = None


class CheckboxResult:
    """Result of a checkbox selection."""

    def __init__(self, items: list[CheckboxItem], cancelled: bool = False) -> None:
        self.items = items
        self.cancelled = cancelled

    @property
    def selected_values(self) -> list[str]:
        """Return the selected values."""
        return [item.value for item in self.items if item.selected]

    @property
    def selected_labels(self) -> list[str]:
        """Return the selected labels."""
        return [item.label for item in self.items if item.selected]

    def __bool__(self) -> bool:
        """True if at least one item is selected and not cancelled."""
        return not self.cancelled and len(self.selected_values) > 0


def checkbox_select(
    items: list[CheckboxItem],
    title: str = "Sélection",
    min_selected: int = 0,
    show_help: bool = True,
) -> CheckboxResult:
    """Display an interactive checkbox list.

    Args:
        items: List of items to display.
        title: Panel title.
        min_selected: Minimum number of items to select (0 = optional).
        show_help: Show help at the bottom.

    Returns:
        CheckboxResult with the selected items.

    Controls:
        Up/Down or k/j: Navigate
        Space: Check/uncheck
        a: Select all
        n: Deselect all
        Enter: Confirm
        r: Cancel and go back
    """
    cursor_pos = 0
    cancelled = False

    def render() -> Panel:
        """Generate the component rendering."""
        lines = []

        for i, item in enumerate(items):
            # Cursor and checkbox
            cursor = ">" if i == cursor_pos else " "
            checkbox = "[green]✓[/green]" if item.selected else "[dim]○[/dim]"

            # Label with highlight if cursor
            label = f"[bold cyan]{item.label}[/bold cyan]" if i == cursor_pos else item.label

            line = f" {cursor} {checkbox} {label}"

            # Description if present
            if item.description:
                line += f" [dim]- {item.description}[/dim]"

            lines.append(line)

        content = "\n".join(lines)

        if show_help:
            help_text = (
                "\n\n[dim]↑↓ naviguer │ espace cocher │ "
                "a tout │ n rien │ entrée valider │ r retour[/dim]"
            )
            content += help_text

        # Selection counter
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
                # If not enough selected, show a message
                console.print(
                    f"[yellow]Veuillez sélectionner au moins {min_selected} élément(s)[/yellow]"
                )
            elif _is_cancel_key(key):
                cancelled = True
                break

            live.update(render())

    return CheckboxResult(items, cancelled)


@dataclass
class SelectItem:
    """An item in the single selection list."""

    label: str
    value: str
    description: str | None = None


class SelectResult:
    """Result of a single selection."""

    def __init__(self, item: SelectItem | None = None, cancelled: bool = False) -> None:
        self.item = item
        self.cancelled = cancelled

    @property
    def value(self) -> str | None:
        """Return the selected value."""
        return self.item.value if self.item else None

    @property
    def label(self) -> str | None:
        """Return the selected label."""
        return self.item.label if self.item else None

    def __bool__(self) -> bool:
        """True if an item is selected and not cancelled."""
        return not self.cancelled and self.item is not None


def select_single(
    items: list[SelectItem],
    title: str = "Sélection",
    default_index: int = 0,
    show_help: bool = True,
) -> SelectResult:
    """Display an interactive single selection list.

    Args:
        items: List of items to display.
        title: Panel title.
        default_index: Index of the default selected item.
        show_help: Show help at the bottom.

    Returns:
        SelectResult with the selected item.

    Controls:
        Up/Down or k/j: Navigate
        Enter: Confirm
        r: Cancel and go back
    """
    if not items:
        return SelectResult(cancelled=True)

    cursor_pos = min(default_index, len(items) - 1)
    cancelled = False

    def render() -> Panel:
        """Generate the component rendering."""
        lines = []

        for i, item in enumerate(items):
            # Cursor and indicator
            if i == cursor_pos:
                cursor = ">"
                indicator = "[green]●[/green]"
                label = f"[bold cyan]{item.label}[/bold cyan]"
            else:
                cursor = " "
                indicator = "[dim]○[/dim]"
                label = item.label

            line = f" {cursor} {indicator} {label}"

            # Description if present
            if item.description:
                line += f" [dim]- {item.description}[/dim]"

            lines.append(line)

        content = "\n".join(lines)

        if show_help:
            help_text = "\n\n[dim]↑↓ naviguer │ entrée valider │ r retour[/dim]"
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
            elif _is_cancel_key(key):
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
    """Interactive territory selection.

    Args:
        territories: List of available territory codes.
        default: Default territory.

    Returns:
        SelectResult with the selected territory.
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
    """Interactive format selection.

    Args:
        formats: List of available formats.
        default: Default format.

    Returns:
        SelectResult with the selected format.
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
    """Interactive layer selection.

    Args:
        layers: List of tuples (layer_name, description).
        preselected: List of preselected layers (None = all).

    Returns:
        CheckboxResult with the selected layers.
    """
    if preselected is None:
        # By default, everything is selected
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
    """Interactive vintage/year selection.

    Args:
        available_years: List of available years from the catalog.
        preselected: List of preselected years.

    Returns:
        CheckboxResult with the selected years (cancelled if none available).
    """
    if not available_years:
        console.print(
            "[yellow]Aucun millésime disponible pour ce produit dans le catalogue.[/yellow]"
        )
        return CheckboxResult([], cancelled=True)

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


# =============================================================================
# New widgets for menus and actions
# =============================================================================


@dataclass
class MenuOption:
    """A menu option."""

    key: str  # Key to select (1, 2, a, s, q, etc.)
    label: str  # Displayed text
    description: str | None = None  # Optional description


class MenuResult:
    """Result of a menu selection."""

    def __init__(self, key: str | None = None, cancelled: bool = False) -> None:
        self.key = key
        self.cancelled = cancelled

    def __bool__(self) -> bool:
        """True if an option is selected and not cancelled."""
        return not self.cancelled and self.key is not None


def select_menu(
    options: list[MenuOption],
    title: str = "Menu",
    cancel_key: str = "q",
    cancel_label: str = "Retour",
    show_help: bool = True,
) -> MenuResult:
    """Display an interactive menu with keyboard navigation.

    Args:
        options: List of menu options.
        title: Panel title.
        cancel_key: Key for cancel/go back.
        cancel_label: Label for the cancel option.
        show_help: Show help at the bottom.

    Returns:
        MenuResult with the selected key.

    Controls:
        Up/Down or k/j: Navigate
        Enter: Confirm current option
        Direct key: Select directly
        r: Cancel and go back
    """
    # Add the cancel option
    all_options = [*options, MenuOption(key=cancel_key, label=cancel_label)]
    valid_keys = {opt.key.lower() for opt in all_options}

    cursor_pos = 0
    cancelled = False
    selected_key: str | None = None

    def render() -> Panel:
        """Generate the component rendering."""
        lines = []

        for i, opt in enumerate(all_options):
            # Cursor
            cursor = ">" if i == cursor_pos else " "

            # Format the key
            key_display = f"[cyan]{opt.key}[/cyan]"

            # Label with highlight if cursor
            label = f"[bold]{opt.label}[/bold]" if i == cursor_pos else opt.label

            line = f" {cursor} {key_display} : {label}"

            # Description if present
            if opt.description:
                line += f" [dim]- {opt.description}[/dim]"

            lines.append(line)

        content = "\n".join(lines)

        if show_help:
            help_text = "\n\n[dim]↑↓ naviguer │ entrée valider │ touche directe │ r retour[/dim]"
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
                cursor_pos = (cursor_pos - 1) % len(all_options)
            elif key == readchar.key.DOWN or key == "j":
                cursor_pos = (cursor_pos + 1) % len(all_options)
            elif key == readchar.key.ENTER or key == "\r" or key == "\n":
                selected_key = all_options[cursor_pos].key
                if selected_key == cancel_key:
                    cancelled = True
                break
            elif _is_cancel_key(key):
                cancelled = True
                break
            elif key.lower() in valid_keys:
                # Direct selection by key
                selected_key = key.lower()
                if selected_key == cancel_key:
                    cancelled = True
                break

            live.update(render())

    if cancelled:
        return MenuResult(cancelled=True)
    return MenuResult(key=selected_key)


@dataclass
class ToggleItem:
    """An item with on/off state."""

    label: str
    value: str
    enabled: bool = True
    description: str | None = None


class ToggleListResult:
    """Result of a toggle list."""

    def __init__(
        self,
        items: list[ToggleItem],
        cancelled: bool = False,
        action: str | None = None,
    ) -> None:
        self.items = items
        self.cancelled = cancelled
        self.action = action  # 't' for all, 'n' for none, None otherwise

    @property
    def enabled_values(self) -> list[str]:
        """Return the enabled values."""
        return [item.value for item in self.items if item.enabled]

    def __bool__(self) -> bool:
        """True if not cancelled."""
        return not self.cancelled


def select_toggle_list(
    items: list[ToggleItem],
    title: str = "Activation",
    show_help: bool = True,
) -> ToggleListResult:
    """Display a list with interactive on/off toggle.

    Args:
        items: List of items to display.
        title: Panel title.
        show_help: Show help at the bottom.

    Returns:
        ToggleListResult with the modified items.

    Controls:
        Up/Down or k/j: Navigate
        Space or Enter: Toggle state
        t: Enable all
        n: Disable all
        1-9: Toggle by number
        q or r: Finish/go back
    """
    cursor_pos = 0
    cancelled = False
    action: str | None = None

    def render() -> Panel:
        """Generate the component rendering."""
        lines = []

        for i, item in enumerate(items):
            # Number and cursor
            num = str(i + 1) if i < 9 else " "
            cursor = ">" if i == cursor_pos else " "

            # On/off state
            status = "[green]✓ ON [/green]" if item.enabled else "[red]✗ OFF[/red]"

            # Label with highlight if cursor
            label = f"[bold cyan]{item.label}[/bold cyan]" if i == cursor_pos else item.label

            line = f" {cursor} [dim]{num}[/dim] {status} {label}"

            # Description if present
            if item.description:
                line += f" [dim]- {item.description}[/dim]"

            lines.append(line)

        content = "\n".join(lines)

        if show_help:
            help_text = (
                "\n\n[dim]↑↓ naviguer │ espace basculer │ "
                "t tout │ n rien │ 1-9 direct │ q terminer[/dim]"
            )
            content += help_text

        # Counter
        enabled_count = sum(1 for item in items if item.enabled)
        subtitle = f"{enabled_count}/{len(items)} activé(s)"

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
            elif key == " " or key == readchar.key.ENTER or key == "\r" or key == "\n":
                items[cursor_pos].enabled = not items[cursor_pos].enabled
            elif key == "t":
                for item in items:
                    item.enabled = True
                action = "t"
            elif key == "n":
                for item in items:
                    item.enabled = False
                action = "n"
            elif key == "q" or _is_cancel_key(key):
                break
            elif key.isdigit() and 1 <= int(key) <= len(items):
                idx = int(key) - 1
                items[idx].enabled = not items[idx].enabled
                cursor_pos = idx

            live.update(render())

    return ToggleListResult(items, cancelled=cancelled, action=action)


def select_option(
    options: list[str],
    title: str = "Sélection",
    default: str | None = None,
) -> SelectResult:
    """Quick selection from a list of simple options.

    Args:
        options: List of options (values = labels).
        title: Panel title.
        default: Default option.

    Returns:
        SelectResult with the selected option.
    """
    items = [SelectItem(label=opt, value=opt) for opt in options]

    default_index = 0
    if default:
        for i, opt in enumerate(options):
            if opt == default:
                default_index = i
                break

    return select_single(items, title=title, default_index=default_index)
