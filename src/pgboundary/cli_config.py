"""CLI commands for pgBoundary configuration.

This module provides the configuration subcommands:
- config: configuration summary
- config info: full formatted display
- config init: interactive creation
- config update: interactive modification
- config db: database connection configuration
- config data: interactive product management (tree view)
- config data update: interactive modification via tree view (default)
- config data add: add products to import
- config data remove: remove products
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from pgboundary.config import (
    Settings,
    build_database_url,
    has_database_url_configured,
    save_data_dir_to_env,
    save_database_url_to_env,
)
from pgboundary.products import get_default_catalog
from pgboundary.schema_config import (
    DEFAULT_CONFIG_FILENAME,
    SchemaConfig,
    StorageConfig,
    StorageMode,
    load_config,
    save_config,
)

if TYPE_CHECKING:
    from pgboundary.products.catalog import IGNProduct


def _get_product_years(product: IGNProduct | None) -> list[str] | None:
    """Return a product's available_dates for selection.

    Returns the full dates (YYYY or YYYY-MM-DD) as they appear in the
    catalog, without truncation. This ensures the URL builder receives
    the exact date needed (e.g. '2025-09-15' instead of '2025').
    """
    if not product or not product.available_dates:
        return None
    return list(product.available_dates) or None


console = Console()
config_app = typer.Typer(help="Gestion de la configuration pgBoundary")
data_app = typer.Typer(help="Gestion des produits à importer")
config_app.add_typer(data_app, name="data")


@data_app.callback(invoke_without_command=True)
def data_main(ctx: typer.Context) -> None:
    """Interactive product management (default action: update)."""
    if ctx.invoked_subcommand is not None:
        return
    # By default, launch data update
    data_update()


def _get_config_path() -> Path:
    """Return the path to the configuration file."""
    return Path.cwd() / DEFAULT_CONFIG_FILENAME


def _mask_password(url: str) -> str:
    """Mask the password in a database URL."""
    import re

    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)


@config_app.callback(invoke_without_command=True)
def config_main(ctx: typer.Context) -> None:
    """Display a configuration summary (when no subcommand is given)."""
    if ctx.invoked_subcommand is not None:
        return

    config_path = _get_config_path()

    if not config_path.exists():
        console.print(f"[yellow]Fichier de configuration non trouvé: {config_path}[/yellow]")
        console.print("Utilisez [bold]pgboundary config init[/bold] pour créer la configuration.")
        return

    config = load_config(config_path)

    # Compact summary
    console.print(Panel.fit("[bold blue]Configuration pgBoundary[/bold blue]"))

    # Database
    from pgboundary.config import Settings

    try:
        settings = Settings()
        db_url = _mask_password(str(settings.database_url))
    except Exception:
        db_url = "[non configurée]"

    console.print(f"[bold]Base de données:[/bold] {db_url}")

    # Storage directory
    try:
        data_dir = str(settings.data_dir)
    except Exception:
        data_dir = str(Settings.model_fields["data_dir"].default)
    console.print(f"[bold]Données:[/bold] {data_dir}")

    # Storage mode
    if config.storage.mode == StorageMode.SCHEMA:
        console.print(f"[bold]Stockage:[/bold] schéma [cyan]{config.storage.schema_name}[/cyan]")
    else:
        console.print(f"[bold]Stockage:[/bold] préfixe [cyan]{config.storage.table_prefix}[/cyan]")

    # Imports status
    enabled, total = config.count_imports()
    if total == 0:
        console.print("[bold]Imports:[/bold] [yellow]aucun produit configuré[/yellow]")
    else:
        console.print(f"[bold]Imports:[/bold] {enabled}/{total} produits activés")

    console.print()
    console.print("[dim]Utilisez 'pgboundary config info' pour plus de détails[/dim]")


@config_app.command(name="info")
def config_info() -> None:
    """Display the full configuration formatted with Rich."""
    config_path = _get_config_path()

    if not config_path.exists():
        console.print(f"[red]Fichier de configuration non trouvé: {config_path}[/red]")
        raise typer.Exit(1)

    # Read the raw YAML file for display
    content = config_path.read_text(encoding="utf-8")

    console.print(Panel.fit(f"[bold blue]Configuration: {config_path}[/bold blue]"))
    console.print()

    syntax = Syntax(content, "yaml", theme="monokai", line_numbers=True)
    console.print(syntax)


@config_app.command(name="db")
def config_db() -> None:
    """Configure la connexion à la base de données de manière interactive."""
    if has_database_url_configured():
        settings = Settings()
        display_url = _mask_password(str(settings.database_url))
        console.print(f"[yellow]Configuration existante:[/yellow] {display_url}")
        if not Confirm.ask("Voulez-vous la modifier ?"):
            raise typer.Exit()

    console.print(Panel("[bold]Configuration de la connexion PostgreSQL[/bold]"))

    host = Prompt.ask("Hôte PostgreSQL", default="localhost")
    port = int(Prompt.ask("Port", default="5432"))
    database = Prompt.ask("Nom de la base de données", default="boundaries")
    user = Prompt.ask("Utilisateur", default="postgres")
    password = Prompt.ask("Mot de passe", password=True, default="")

    database_url = build_database_url(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    # Display the URL (without the password)
    display_url = database_url
    if password:
        display_url = database_url.replace(f":{password}@", ":****@")
    console.print(f"\n[cyan]URL de connexion:[/cyan] {display_url}")

    if Confirm.ask("\nSauvegarder dans le fichier .env ?", default=True):
        save_database_url_to_env(database_url)
        console.print("[green]✓ Configuration sauvegardée dans .env[/green]")


@config_app.command(name="init")
def config_init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Écrase le fichier existant"),
    ] = False,
) -> None:
    """Crée la configuration de manière interactive."""
    config_path = _get_config_path()

    if config_path.exists() and not force:
        console.print(f"[yellow]Le fichier {config_path} existe déjà.[/yellow]")
        if not Confirm.ask("Voulez-vous le modifier ?"):
            raise typer.Exit(0)
        # Load existing config as default values
        existing_config = load_config(config_path)
    else:
        existing_config = SchemaConfig()

    console.print(Panel.fit("[bold blue]Configuration pgBoundary[/bold blue]"))
    console.print()

    # 1. Storage mode
    console.print("[bold]1. Mode de stockage des tables[/bold]")
    console.print("  [cyan]schema[/cyan] : Tables dans un schéma dédié (recommandé)")
    console.print("  [cyan]prefix[/cyan] : Tables dans public avec préfixe")
    console.print()

    mode_choices = ["schema", "prefix"]
    default_mode = existing_config.storage.mode.value
    mode = Prompt.ask(
        "Mode de stockage",
        choices=mode_choices,
        default=default_mode,
    )

    storage = StorageConfig(mode=StorageMode(mode))

    if mode == "schema":
        storage.schema_name = Prompt.ask(
            "Nom du schéma",
            default=existing_config.storage.schema_name,
        )
    else:
        storage.table_prefix = Prompt.ask(
            "Préfixe des tables",
            default=existing_config.storage.table_prefix,
        )

    # 2. SRID (Coordinate Reference System)
    console.print()
    console.print("[bold]2. Système de coordonnées[/bold]")
    console.print("  [cyan]4326[/cyan] : WGS84 (standard international)")
    console.print("  [cyan]2154[/cyan] : Lambert 93 (France métropolitaine)")
    console.print()

    srid = Prompt.ask(
        "SRID",
        default=str(existing_config.srid),
    )

    # 3. Data directory
    console.print()
    console.print("[bold]3. Répertoire de stockage des données[/bold]")
    console.print("  Les archives téléchargées seront stockées dans ce répertoire.")
    console.print()

    default_data_dir = str(Path.home() / ".pgboundary" / "data")
    try:
        current_settings = Settings()
        default_data_dir = str(current_settings.data_dir)
    except Exception:
        pass

    data_dir = Prompt.ask("Répertoire de données", default=default_data_dir)
    resolved_data_dir = Path(data_dir).expanduser().resolve()

    if str(resolved_data_dir) != str(Path(default_data_dir).expanduser().resolve()):
        save_data_dir_to_env(str(resolved_data_dir))
        console.print(f"[green]✓ Répertoire configuré: {resolved_data_dir}[/green]")

    # Create the configuration
    config = SchemaConfig(
        storage=storage,
        field_prefixes=existing_config.field_prefixes,
        table_names=existing_config.table_names,
        table_overrides=existing_config.table_overrides,
        srid=int(srid),
        imports=existing_config.imports,
    )

    # 4. Add products?
    console.print()
    if Confirm.ask("Voulez-vous configurer des produits à importer ?"):
        _add_products_interactive(config, config_path)

    # Save
    save_config(config, config_path)
    console.print()
    console.print(f"[green]Configuration sauvegardée: {config_path}[/green]")


@config_app.command(name="update")
def config_update() -> None:
    """Modifie la configuration de manière interactive."""
    config_path = _get_config_path()

    if not config_path.exists():
        console.print(f"[red]Fichier de configuration non trouvé: {config_path}[/red]")
        console.print("Utilisez [bold]pgboundary config init[/bold] pour créer la configuration.")
        raise typer.Exit(1)

    config = load_config(config_path)

    from pgboundary.cli_widgets import MenuOption, select_menu

    while True:
        options = [
            MenuOption("1", "Mode de stockage", "schema ou préfixe"),
            MenuOption("2", "SRID", "système de projection"),
            MenuOption("3", "Produits à importer", "IGN Admin Express, etc."),
            MenuOption("4", "Préfixes des colonnes", "cd_, lb_, dt_"),
            MenuOption("5", "Répertoire de données", "emplacement des téléchargements"),
        ]
        result = select_menu(
            options,
            title="Modification de la configuration",
            cancel_key="q",
            cancel_label="Quitter et sauvegarder",
        )

        if result.cancelled:
            break
        elif result.key == "1":
            _update_storage(config)
        elif result.key == "2":
            _update_srid(config)
        elif result.key == "3":
            _update_imports(config)
        elif result.key == "4":
            _update_prefixes(config)
        elif result.key == "5":
            _update_data_dir()

    save_config(config, config_path)
    console.print(f"[green]Configuration sauvegardée: {config_path}[/green]")


def _update_storage(config: SchemaConfig) -> None:
    """Update the storage mode."""
    console.print()
    mode = Prompt.ask(
        "Mode de stockage",
        choices=["schema", "prefix"],
        default=config.storage.mode.value,
    )
    config.storage.mode = StorageMode(mode)

    if mode == "schema":
        config.storage.schema_name = Prompt.ask(
            "Nom du schéma",
            default=config.storage.schema_name,
        )
    else:
        config.storage.table_prefix = Prompt.ask(
            "Préfixe des tables",
            default=config.storage.table_prefix,
        )


def _update_srid(config: SchemaConfig) -> None:
    """Update the SRID."""
    console.print()
    srid = Prompt.ask("SRID", default=str(config.srid))
    config.srid = int(srid)


def _update_prefixes(config: SchemaConfig) -> None:
    """Update the column prefixes."""
    console.print()
    config.field_prefixes.code = Prompt.ask(
        "Préfixe des codes",
        default=config.field_prefixes.code,
    )
    config.field_prefixes.label = Prompt.ask(
        "Préfixe des libellés",
        default=config.field_prefixes.label,
    )
    config.field_prefixes.date = Prompt.ask(
        "Préfixe des dates",
        default=config.field_prefixes.date,
    )


def _update_data_dir() -> None:
    """Update the data storage directory."""
    console.print()

    try:
        settings = Settings()
        current_dir = str(settings.data_dir)
    except Exception:
        current_dir = str(Path.home() / ".pgboundary" / "data")

    console.print(f"[bold]Répertoire actuel:[/bold] {current_dir}")
    console.print("[dim]Les données téléchargées (archives IGN, etc.) sont stockées ici.[/dim]")
    console.print()

    new_dir = Prompt.ask("Nouveau répertoire", default=current_dir)

    # Resolve the path (expand ~ etc.)
    resolved = Path(new_dir).expanduser().resolve()

    if str(resolved) != str(Path(current_dir).expanduser().resolve()):
        console.print(f"[cyan]Répertoire:[/cyan] {resolved}")
        if Confirm.ask("Sauvegarder dans le fichier .env ?", default=True):
            save_data_dir_to_env(str(resolved))
            console.print("[green]✓ Répertoire de données mis à jour[/green]")
    else:
        console.print("[dim]Aucune modification[/dim]")


def _get_enabled_layers_count(prod_config: dict[str, Any]) -> tuple[int, int]:
    """Count the enabled layers in a product configuration.

    Args:
        prod_config: Product configuration.

    Returns:
        Tuple (enabled count, total count).
    """
    layers = prod_config.get("layers", {})
    if isinstance(layers, dict):
        total = len(layers)
        enabled = sum(1 for layer in layers.values() if layer.get("enabled", True))
        return enabled, total
    # Legacy structure (list)
    return len(layers), len(layers) if layers else 0


def _update_imports(config: SchemaConfig) -> None:
    """Update the imports configuration."""
    from pgboundary.cli_widgets import MenuOption, SelectItem, select_menu, select_single

    console.print()

    if not config.imports:
        console.print("[yellow]Aucun produit configuré.[/yellow]")
        if Confirm.ask("Ajouter des produits ?"):
            _add_products_interactive(config)
        return

    # Display existing products
    table = Table(title="Produits configurés")
    table.add_column("#", style="dim")
    table.add_column("Produit", style="cyan")
    table.add_column("Couches")
    table.add_column("Années")
    table.add_column("Territoire")

    products_list = list(config.imports.items())
    for i, (product_id, prod_config) in enumerate(products_list, 1):
        enabled_count, total_count = _get_enabled_layers_count(prod_config)
        if total_count > 0:
            layers_str = f"{enabled_count}/{total_count} activées"
            if enabled_count == 0:
                layers_str = f"[red]{layers_str}[/red]"
            elif enabled_count == total_count:
                layers_str = f"[green]{layers_str}[/green]"
        else:
            layers_str = "[dim]aucune[/dim]"

        years = ", ".join(prod_config.get("years", []))
        territory = prod_config.get("territory", "FRA")
        table.add_row(str(i), product_id, layers_str, years, territory)

    console.print(table)
    console.print()

    # Actions menu
    options = [
        MenuOption("a", "Ajouter un produit"),
        MenuOption("s", "Supprimer un produit"),
        MenuOption("m", "Modifier un produit"),
    ]
    result = select_menu(options, title="Actions", cancel_key="q", cancel_label="Retour")

    if result.cancelled:
        return
    elif result.key == "a":
        _add_products_interactive(config)
    elif result.key == "s" and products_list:
        # Select the product to remove
        product_items = [
            SelectItem(label=pid, value=pid, description=f"{len(cfg.get('layers', {}))} couches")
            for pid, cfg in products_list
        ]
        sel_result = select_single(product_items, title="Produit à supprimer")
        if sel_result and sel_result.value:
            del config.imports[sel_result.value]
            console.print(f"[green]Produit {sel_result.value} supprimé[/green]")
    elif result.key == "m" and products_list:
        # Select the product to modify
        product_items = [
            SelectItem(label=pid, value=pid, description=f"{len(cfg.get('layers', {}))} couches")
            for pid, cfg in products_list
        ]
        sel_result = select_single(product_items, title="Produit à modifier")
        if sel_result and sel_result.value:
            _modify_product_config(config, sel_result.value)


def _modify_product_config(config: SchemaConfig, product_id: str) -> None:
    """Modify a product's configuration (new layer-based structure)."""
    from pgboundary.cli_widgets import MenuOption, select_menu

    prod_config = config.imports[product_id]
    catalog = get_default_catalog()
    product = catalog.get(product_id)

    while True:
        options = [
            MenuOption("1", "Paramètres par défaut", "territoire, format, années"),
            MenuOption("2", "Historisation"),
            MenuOption("3", "Activer/désactiver des couches"),
            MenuOption("4", "Configurer une couche spécifique"),
        ]

        result = select_menu(
            options,
            title=f"Modification de {product_id}",
            cancel_key="q",
            cancel_label="Terminer",
        )

        if result.cancelled:
            break
        elif result.key == "1":
            _modify_product_defaults(prod_config, product)
        elif result.key == "2":
            _modify_product_historization(prod_config)
        elif result.key == "3":
            _toggle_product_layers(prod_config, product)
        elif result.key == "4":
            _modify_layer_config(prod_config, product)

    console.print(f"[green]Configuration de {product_id} mise à jour[/green]")


def _modify_product_defaults(
    prod_config: dict[str, Any],
    product: IGNProduct | None,
) -> None:
    """Modify the default parameters of a product."""
    from pgboundary.cli_widgets import (
        select_format,
        select_territory,
        select_years,
    )

    console.print("\n[bold]Modification des valeurs par défaut[/bold]")

    # Years
    product_years = _get_product_years(product)
    if product_years:
        current_years = prod_config.get("years", [])
        years_result = select_years(available_years=product_years, preselected=current_years)
        if years_result.cancelled:
            console.print("[yellow]Modification annulée[/yellow]")
            return
        prod_config["years"] = years_result.selected_values

    # Territory
    if product:
        territories = [t.value for t in product.territories]
    else:
        territories = ["FRA", "FXX", "GLP", "MTQ", "GUF", "REU", "MYT"]
    current_territory = prod_config.get("territory", "FRA")
    territory_result = select_territory(territories, default=current_territory)
    if territory_result.cancelled:
        console.print("[yellow]Modification annulée[/yellow]")
        return
    prod_config["territory"] = territory_result.value or current_territory

    # File format
    formats = [f.value for f in product.formats] if product else ["shp", "gpkg"]
    current_format = prod_config.get("format", "shp")
    format_result = select_format(formats, default=current_format)
    if format_result.cancelled:
        console.print("[yellow]Modification annulée[/yellow]")
        return
    prod_config["format"] = format_result.value or current_format

    console.print("[green]Paramètres par défaut mis à jour[/green]")


def _modify_product_historization(prod_config: dict[str, Any]) -> None:
    """Modify the historization configuration of a product."""
    console.print("\n[bold]Configuration de l'historisation[/bold]")

    if Confirm.ask(
        "Activer l'historisation ?",
        default=prod_config.get("historization", {}).get("enabled", False),
    ):
        hist = prod_config.setdefault("historization", {})
        hist["enabled"] = True
        hist["method"] = Prompt.ask(
            "Méthode de comparaison",
            choices=["md5", "jaccard", "hausdorff", "combined"],
            default=hist.get("method", "combined"),
        )
        if hist["method"] != "md5":
            thresholds = hist.setdefault("thresholds", {})
            thresholds["identical_min"] = float(
                Prompt.ask(
                    "Seuil identique (IoU min)",
                    default=str(thresholds.get("identical_min", 0.95)),
                )
            )
            thresholds["likely_match_min"] = float(
                Prompt.ask(
                    "Seuil correspondance probable (IoU min)",
                    default=str(thresholds.get("likely_match_min", 0.80)),
                )
            )
        hist["key_field"] = Prompt.ask(
            "Champ clé",
            default=hist.get("key_field", "cd_insee"),
        )
    else:
        prod_config["historization"] = {"enabled": False}

    console.print("[green]Historisation mise à jour[/green]")


def _toggle_product_layers(
    prod_config: dict[str, Any],
    product: IGNProduct | None,
) -> None:
    """Enable/disable layers of a product."""
    from pgboundary.cli_widgets import ToggleItem, select_toggle_list

    layers = prod_config.setdefault("layers", {})

    # List all available layers
    all_layers = [layer.name for layer in product.layers] if product else list(layers.keys())

    if not all_layers:
        console.print("[yellow]Aucune couche disponible[/yellow]")
        return

    # Build items for the widget
    toggle_items = []
    for layer_name in all_layers:
        layer_cfg = layers.get(layer_name, {})
        enabled = layer_cfg.get("enabled", True)
        table_name = layer_cfg.get("table_name")
        description = f"→ {table_name}" if table_name else None
        toggle_items.append(
            ToggleItem(
                label=layer_name,
                value=layer_name,
                enabled=enabled,
                description=description,
            )
        )

    # Display the interactive widget
    result = select_toggle_list(toggle_items, title="Activation des couches")

    if result.cancelled:
        return

    # Apply changes
    for item in result.items:
        if item.value not in layers:
            layers[item.value] = {}
        layers[item.value]["enabled"] = item.enabled

    enabled_count = sum(1 for item in result.items if item.enabled)
    console.print(f"[green]{enabled_count}/{len(all_layers)} couches activées[/green]")


def _modify_layer_config(
    prod_config: dict[str, Any],
    product: IGNProduct | None,
) -> None:
    """Modify the configuration of a specific layer."""
    from pgboundary.cli_widgets import (
        SelectItem,
        select_single,
        select_territory,
        select_years,
    )

    layers = prod_config.setdefault("layers", {})

    all_layers = [layer.name for layer in product.layers] if product else list(layers.keys())

    if not all_layers:
        console.print("[yellow]Aucune couche disponible[/yellow]")
        return

    while True:
        # Select the layer with the widget
        layer_items = []
        for layer_name in all_layers:
            layer_cfg = layers.get(layer_name, {})
            table_name = layer_cfg.get("table_name")
            description = f"→ {table_name}" if table_name else None
            layer_items.append(
                SelectItem(label=layer_name, value=layer_name, description=description)
            )

        result = select_single(layer_items, title="Sélectionner une couche")
        if result.cancelled or not result.value:
            return

        layer_name = result.value
        layer_cfg = layers.setdefault(layer_name, {})

        console.print(f"\n[bold]Configuration de la couche {layer_name}[/bold]")
        console.print("[dim]Laissez vide pour hériter des valeurs par défaut du produit[/dim]")
        console.print()

        # Table name
        current_table = layer_cfg.get("table_name")
        new_table = Prompt.ask(
            "Nom de la table",
            default=current_table or "",
        )
        if new_table:
            layer_cfg["table_name"] = new_table
        elif "table_name" in layer_cfg:
            del layer_cfg["table_name"]

        # Override years?
        product_years = _get_product_years(product)
        if product_years:
            if Confirm.ask(
                "Surcharger les années pour cette couche ?",
                default=bool(layer_cfg.get("years")),
            ):
                current_years = layer_cfg.get("years") or prod_config.get("years", [])
                years_result = select_years(
                    available_years=product_years, preselected=current_years
                )
                if not years_result.cancelled:
                    layer_cfg["years"] = years_result.selected_values
            elif "years" in layer_cfg:
                del layer_cfg["years"]

        # Override territory?
        if Confirm.ask(
            "Surcharger le territoire pour cette couche ?",
            default=bool(layer_cfg.get("territory")),
        ):
            if product:
                territories = [t.value for t in product.territories]
            else:
                territories = ["FRA", "FXX", "GLP", "MTQ", "GUF", "REU", "MYT"]
            current = layer_cfg.get("territory") or prod_config.get("territory", "FRA")
            territory_result = select_territory(territories, default=current)
            if not territory_result.cancelled and territory_result.value:
                layer_cfg["territory"] = territory_result.value
        elif "territory" in layer_cfg:
            del layer_cfg["territory"]

        console.print(f"[green]Couche {layer_name} configurée[/green]")


@data_app.command(name="add")
def data_add() -> None:
    """Ajoute des produits à importer via navigation arborescente."""
    config_path = _get_config_path()

    if not config_path.exists():
        console.print("[yellow]Fichier de configuration non trouvé.[/yellow]")
        console.print("Création d'une configuration par défaut...")
        config = SchemaConfig()
    else:
        config = load_config(config_path)

    _add_products_interactive(config, config_path)

    save_config(config, config_path)
    console.print(f"[green]Configuration sauvegardée: {config_path}[/green]")


@data_app.command(name="remove")
def data_remove(
    product_ids: Annotated[
        list[str] | None,
        typer.Argument(help="IDs des produits à supprimer (ex: admin-express-cog contours-iris)."),
    ] = None,
) -> None:
    """Remove products from the configuration.

    Without arguments: interactive mode to select products to remove.
    With arguments: directly remove the specified products.
    """
    config_path = _get_config_path()

    if not config_path.exists():
        console.print(f"[red]Fichier de configuration non trouvé: {config_path}[/red]")
        raise typer.Exit(1)

    config = load_config(config_path)

    if not config.imports:
        console.print("[yellow]Aucun produit configuré.[/yellow]")
        raise typer.Exit(0)

    if product_ids:
        # Direct mode: remove the specified products
        removed = []
        not_found = []
        for product_id in product_ids:
            if product_id in config.imports:
                del config.imports[product_id]
                removed.append(product_id)
            else:
                not_found.append(product_id)

        if removed:
            save_config(config, config_path)
            console.print(f"[green]Produits supprimés: {', '.join(removed)}[/green]")
        if not_found:
            console.print(f"[yellow]Produits non trouvés: {', '.join(not_found)}[/yellow]")
    else:
        # Interactive mode
        _remove_products_interactive(config)
        save_config(config, config_path)
        console.print(f"[green]Configuration sauvegardée: {config_path}[/green]")


@data_app.command(name="update")
def data_update() -> None:
    """Modify products via an interactive tree view.

    Displays all products by category with their status
    and allows enabling, disabling, configuring or removing.
    """
    config_path = _get_config_path()

    if not config_path.exists():
        console.print("[yellow]Fichier de configuration non trouvé.[/yellow]")
        console.print("Création d'une configuration par défaut...")
        config = SchemaConfig()
    else:
        config = load_config(config_path)

    catalog = get_default_catalog()

    while True:
        console.print()
        _display_products_tree(config, catalog)
        console.print()

        console.print("[bold]Actions disponibles :[/bold]")
        console.print("  [cyan]<num>[/cyan]  : Sélectionner un produit par numéro")
        console.print("  [cyan]a[/cyan]      : Ajouter un nouveau produit")
        console.print("  [cyan]q[/cyan]      : Quitter et sauvegarder")
        console.print()

        choice = Prompt.ask("Choix", default="q")

        if choice.lower() == "q":
            break
        elif choice.lower() == "a":
            _add_products_interactive(config, config_path)
        else:
            try:
                product_num = int(choice)
                _select_product_by_number(config, catalog, product_num)
            except ValueError:
                console.print("[red]Choix invalide[/red]")

    save_config(config, config_path)
    console.print(f"[green]Configuration sauvegardée: {config_path}[/green]")


def _display_products_tree(config: SchemaConfig, catalog: Any) -> None:
    """Display the product tree organized by category."""

    # Group by category
    categories: dict[str, list[IGNProduct]] = {}
    for product in catalog:
        cat = product.category.value
        categories.setdefault(cat, []).append(product)

    # Create the tree
    tree = Tree("[bold blue]Produits disponibles[/bold blue]")

    product_counter = 0
    for cat_name in sorted(categories.keys()):
        products = categories[cat_name]

        # Count configured products in this category
        configured_count = sum(1 for p in products if p.id in config.imports)
        cat_label = f"[bold]{cat_name}[/bold] ({configured_count}/{len(products)} configurés)"
        cat_branch = tree.add(cat_label)

        for product in products:
            product_counter += 1
            prod_config = config.imports.get(product.id)

            if prod_config:
                # Configured product - display the number of enabled layers
                enabled_count, total_count = _get_enabled_layers_count(prod_config)
                if enabled_count > 0:
                    status = f"[green]✓ {enabled_count}/{total_count} couches[/green]"
                else:
                    status = f"[yellow]○ {enabled_count}/{total_count} couches[/yellow]"

                # Additional info
                years = prod_config.get("years", [])
                years_str = f" ({', '.join(years)})" if years else ""

                injection = prod_config.get("injection", {})
                if injection.get("injected"):
                    count = injection.get("count", 0)
                    inject_str = f" [dim]→ {count:,} entités[/dim]"
                else:
                    inject_str = ""

                label = f"[cyan]{product_counter:2}[/cyan] {product.name} {status}{years_str}{inject_str}"
            else:
                # Unconfigured product
                size_str = _format_size(product.size_mb)
                label = f"[dim]{product_counter:2}[/dim] {product.name} [dim]({size_str})[/dim]"

            cat_branch.add(label)

    console.print(tree)


def _format_size(size_mb: int | float | None) -> str:
    """Format the size in the appropriate unit."""
    if size_mb is None:
        return "?"
    if size_mb >= 1024:
        return f"{size_mb / 1024:.1f} Go"
    return f"{size_mb} Mo"


def _select_product_by_number(config: SchemaConfig, catalog: Any, num: int) -> None:
    """Select a product by its number and display available actions."""

    # Find product by number
    categories: dict[str, list[IGNProduct]] = {}
    for product in catalog:
        cat = product.category.value
        categories.setdefault(cat, []).append(product)

    product_counter = 0
    target_product: IGNProduct | None = None

    for cat_name in sorted(categories.keys()):
        for product in categories[cat_name]:
            product_counter += 1
            if product_counter == num:
                target_product = product
                break
        if target_product:
            break

    if not target_product:
        console.print(f"[red]Produit #{num} non trouvé[/red]")
        return

    # Display product info
    console.print()
    console.print(Panel.fit(f"[bold blue]{target_product.name}[/bold blue]"))
    console.print(f"[dim]{target_product.description_fr}[/dim]")
    console.print()

    prod_config = config.imports.get(target_product.id)

    if prod_config:
        # Configured product - display status and actions
        enabled_count, total_count = _get_enabled_layers_count(prod_config)
        status = f"{enabled_count}/{total_count} couches activées"
        if enabled_count == 0:
            status = f"[yellow]{status}[/yellow]"
        elif enabled_count == total_count:
            status = f"[green]{status}[/green]"
        console.print(f"Couches: {status}")

        # Display layers
        layers = prod_config.get("layers", {})
        if isinstance(layers, dict):
            for layer_name, layer_cfg in layers.items():
                layer_enabled = layer_cfg.get("enabled", True)
                marker = "[green]✓[/green]" if layer_enabled else "[red]✗[/red]"
                table_name = layer_cfg.get("table_name", "[dim]défaut[/dim]")
                console.print(f"  {marker} {layer_name} → {table_name}")

        years = prod_config.get("years", [])
        if years:
            console.print(f"\nAnnées par défaut: {', '.join(years)}")

        territory = prod_config.get("territory", "FRA")
        console.print(f"Territoire par défaut: {territory}")

        console.print()

        from pgboundary.cli_widgets import MenuOption, select_menu

        options = [
            MenuOption("m", "Modifier la configuration"),
            MenuOption("s", "Supprimer de la configuration"),
        ]
        result = select_menu(options, title="Actions", cancel_key="q", cancel_label="Retour")

        if result.cancelled:
            pass
        elif result.key == "m":
            _modify_product_config(config, target_product.id)
        elif result.key == "s" and Confirm.ask(
            f"Supprimer [cyan]{target_product.id}[/cyan] de la configuration ?"
        ):
            del config.imports[target_product.id]
            console.print("[green]Produit supprimé[/green]")
    else:
        # Unconfigured product - offer to add
        size_str = _format_size(target_product.size_mb)
        console.print(f"Taille: {size_str}")
        console.print(f"Formats: {', '.join(f.value for f in target_product.formats)}")
        console.print(f"Territoires: {', '.join(t.value for t in target_product.territories)}")
        console.print()

        if Confirm.ask("Ajouter ce produit à la configuration ?", default=True):
            _configure_product(config, target_product)


@config_app.command(name="sync-product")
def config_sync_product(
    product_id: Annotated[
        str | None,
        typer.Argument(help="ID du produit à synchroniser (tous si non spécifié)."),
    ] = None,
) -> None:
    """Synchronize product injection status with the database.

    Checks which tables exist in the database and updates
    the injection status in the configuration.
    """
    from sqlalchemy import text

    from pgboundary.db.connection import DatabaseManager

    config_path = _get_config_path()

    if not config_path.exists():
        console.print(f"[red]Fichier de configuration non trouvé: {config_path}[/red]")
        raise typer.Exit(1)

    config = load_config(config_path)

    if not config.imports:
        console.print("[yellow]Aucun produit configuré.[/yellow]")
        raise typer.Exit(0)

    # Filter by product if specified
    products_to_check = (
        {product_id: config.imports[product_id]}
        if product_id and product_id in config.imports
        else config.imports
    )

    if product_id and product_id not in config.imports:
        console.print(f"[red]Produit non trouvé: {product_id}[/red]")
        raise typer.Exit(1)

    try:
        settings = Settings()
        db = DatabaseManager(settings)
        schema_name = config.get_schema_name() or "public"

        with db.session() as session:
            # Retrieve existing tables with their row counts
            tables_query = text("""
                SELECT
                    t.table_name,
                    (SELECT COUNT(*) FROM information_schema.columns c
                     WHERE c.table_schema = t.table_schema
                     AND c.table_name = t.table_name) as col_count
                FROM information_schema.tables t
                WHERE t.table_schema = :schema
                AND t.table_type = 'BASE TABLE'
            """)
            result = session.execute(tables_query, {"schema": schema_name})
            existing_tables = {row.table_name: row.col_count for row in result}

            # Table for display
            table = Table(title="Synchronisation des produits")
            table.add_column("Produit", style="cyan")
            table.add_column("Tables trouvées")
            table.add_column("Entités")
            table.add_column("Statut")

            catalog = get_default_catalog()

            for pid, prod_config in products_to_check.items():
                product = catalog.get(pid)
                if not product:
                    table.add_row(pid, "-", "-", "[yellow]Produit inconnu[/yellow]")
                    continue

                # Check the product's tables
                found_tables = []
                total_count = 0

                for layer in product.layers:
                    table_key = layer.table_key
                    table_name = config.get_full_table_name(table_key)

                    if table_name in existing_tables:
                        found_tables.append(table_name)
                        # Count rows
                        full_name = f"{schema_name}.{table_name}"
                        count_query = text(f"SELECT COUNT(*) FROM {full_name}")
                        count = session.execute(count_query).scalar()
                        total_count += count or 0

                if found_tables:
                    # Product injected
                    config.update_injection_status(
                        pid,
                        injected=True,
                        count=total_count,
                        year=prod_config.get("years", [""])[0]
                        if prod_config.get("years")
                        else None,
                        layers=list(found_tables),
                    )
                    status = "[green]✓ Injecté[/green]"
                else:
                    # Product not injected
                    config.update_injection_status(pid, injected=False)
                    status = "[dim]Non injecté[/dim]"

                table.add_row(
                    pid,
                    str(len(found_tables)),
                    f"{total_count:,}" if total_count > 0 else "-",
                    status,
                )

            console.print(table)

        # Save the updated configuration
        save_config(config, config_path)
        console.print(f"\n[green]Configuration synchronisée: {config_path}[/green]")

    except Exception as e:
        console.print(f"[bold red]Erreur: {e}[/bold red]")
        raise typer.Exit(1) from e


def _remove_products_interactive(config: SchemaConfig) -> None:
    """Remove products interactively."""
    from pgboundary.cli_widgets import SelectItem, select_single

    while True:
        if not config.imports:
            console.print("[yellow]Aucun produit configuré.[/yellow]")
            return

        # Build selection items
        products_list = list(config.imports.items())
        product_items = [
            SelectItem(
                label=product_id,
                value=product_id,
                description=", ".join(prod_config.get("years", [])),
            )
            for product_id, prod_config in products_list
        ]

        result = select_single(product_items, title="Produit à supprimer")

        if result.cancelled or not result.value:
            break

        if Confirm.ask(f"Supprimer le produit [cyan]{result.value}[/cyan] ?"):
            del config.imports[result.value]
            console.print(f"[green]Produit {result.value} supprimé[/green]")


def _add_products_interactive(config: SchemaConfig, config_path: Path | None = None) -> None:
    """Add products via interactive navigation.

    Args:
        config: Configuration to modify.
        config_path: Configuration file path for incremental saving.
    """
    from pgboundary.cli_widgets import SelectItem, select_single

    catalog = get_default_catalog()

    while True:
        # Group by category
        categories: dict[str, list[IGNProduct]] = {}
        for product in catalog:
            cat = product.category.value
            categories.setdefault(cat, []).append(product)

        # Build selection items
        cat_items = [
            SelectItem(
                label=cat,
                value=cat,
                description=f"{len(categories[cat])} produits",
            )
            for cat in sorted(categories.keys())
        ]

        result = select_single(cat_items, title="Catégories de produits")

        if result.cancelled or not result.value:
            break

        imports_before = dict(config.imports)
        _select_product_from_category(config, categories[result.value])

        # Incremental save if a product was added
        if config_path and config.imports != imports_before:
            save_config(config, config_path)


def _select_product_from_category(
    config: SchemaConfig,
    products: list[IGNProduct],
) -> None:
    """Select a product from a category."""
    from pgboundary.cli_widgets import SelectItem, select_single

    # Build selection items
    product_items = [
        SelectItem(
            label=f"{'✓ ' if product.id in config.imports else ''}{product.name}",
            value=product.id,
            description=product.description_fr[:50] + "..."
            if len(product.description_fr) > 50
            else product.description_fr,
        )
        for product in products
    ]

    result = select_single(product_items, title="Produits disponibles")

    if result.cancelled or not result.value:
        return

    # Find the corresponding product
    selected_product = next((p for p in products if p.id == result.value), None)
    if selected_product:
        _configure_product(config, selected_product)


def _configure_product(config: SchemaConfig, product: IGNProduct) -> None:
    """Configure a product for import (new layer-based structure)."""
    from pgboundary.cli_widgets import (
        select_format,
        select_layers,
        select_territory,
        select_years,
    )

    console.print()
    console.print(Panel.fit(f"[bold blue]{product.name}[/bold blue]"))
    console.print(f"[dim]{product.description_fr}[/dim]")
    console.print()

    # Select layers to enable (interactive checkbox)
    layers_data = [(layer.name, layer.description_fr or layer.name) for layer in product.layers]

    layers_result = select_layers(layers_data)
    if layers_result.cancelled:
        console.print("[yellow]Configuration annulée[/yellow]")
        return

    selected_layer_names = layers_result.selected_values

    # Select default vintages/years (interactive checkbox)
    product_years = _get_product_years(product)
    if product_years:
        years_result = select_years(available_years=product_years)
        if years_result.cancelled:
            console.print("[yellow]Configuration annulée[/yellow]")
            return
        years = years_result.selected_values
    else:
        years = []

    # Default territory (interactive selection)
    territories = [t.value for t in product.territories]
    default_territory = territories[0] if territories else "FRA"
    territory_result = select_territory(territories, default=default_territory)
    if territory_result.cancelled:
        console.print("[yellow]Configuration annulée[/yellow]")
        return
    territory = territory_result.value or default_territory

    # Default format (interactive selection)
    formats = [f.value for f in product.formats]
    default_format = formats[0] if formats else "shp"
    format_result = select_format(formats, default=default_format)
    if format_result.cancelled:
        console.print("[yellow]Configuration annulée[/yellow]")
        return
    file_format = format_result.value or default_format

    # Default historization
    hist_config: dict[str, Any] = {"enabled": False}
    if Confirm.ask("Activer l'historisation ?", default=False):
        hist_config["enabled"] = True
        hist_config["method"] = Prompt.ask(
            "Méthode de comparaison",
            choices=["md5", "jaccard", "hausdorff", "combined"],
            default="combined",
        )
        if hist_config["method"] != "md5":
            hist_config["thresholds"] = {
                "identical_min": float(Prompt.ask("Seuil identique (IoU min)", default="0.95")),
                "likely_match_min": float(
                    Prompt.ask("Seuil correspondance probable (IoU min)", default="0.80")
                ),
            }
        hist_config["key_field"] = Prompt.ask(
            "Champ clé d'identification",
            default="cd_insee",
        )

    # Build layer configuration
    layers_config: dict[str, dict[str, Any]] = {}

    for layer in product.layers:
        is_enabled = layer.name in selected_layer_names
        layers_config[layer.name] = {
            "enabled": is_enabled,
            "table_name": layer.table_key,  # Default table name
        }

    # Save with the new structure
    config.imports[product.id] = {
        "territory": territory,
        "format": file_format,
        "years": years,
        "historization": hist_config,
        "layers": layers_config,
    }

    console.print(f"[green]Produit {product.id} ajouté à la configuration[/green]")
