"""CLI commands for data loading.

This module provides the enhanced load command with:
- Configuration display and multiple selection
- --all option to import without confirmation
- --product option to import a single product
- check subcommand to verify download URLs
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:
    from pgboundary.products.catalog import FileFormat, IGNProduct

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from pgboundary.config import Settings
from pgboundary.schema_config import load_config

logger = logging.getLogger(__name__)

console = Console()


def _get_enabled_layers_count(prod_config: dict[str, Any]) -> tuple[int, int]:
    """Count enabled layers in a product configuration.

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


def _get_enabled_layer_names(prod_config: dict[str, Any]) -> list[str]:
    """Return the names of enabled layers.

    Args:
        prod_config: Product configuration.

    Returns:
        List of enabled layer names.
    """
    layers = prod_config.get("layers", {})
    if isinstance(layers, dict):
        return [name for name, cfg in layers.items() if cfg.get("enabled", True)]
    # Legacy structure (list)
    return list(layers) if layers else []


def show_import_selection(
    imports: dict[str, dict[str, Any]],
) -> list[str]:
    """Display imports and allow selection.

    Args:
        imports: Import configuration.

    Returns:
        List of selected product_ids.
    """
    from pgboundary.cli_widgets import ToggleItem, select_toggle_list
    from pgboundary.products import get_default_catalog

    if not imports:
        console.print("[yellow]Aucun produit configuré pour l'import.[/yellow]")
        console.print("Utilisez [bold]pgboundary config add-data[/bold] pour ajouter des produits.")
        return []

    catalog = get_default_catalog()

    # Build items for the widget
    products_list = list(imports.items())
    toggle_items = []

    for product_id, config in products_list:
        enabled_count, total_count = _get_enabled_layers_count(config)
        initial_selected = enabled_count > 0

        # Build the description
        years = ", ".join(config.get("years", []))
        hist = config.get("historization", {})
        hist_str = hist.get("method", "combined") if hist.get("enabled", False) else "non"
        layers_info = f"{enabled_count}/{total_count}" if total_count > 0 else "aucune"

        product = catalog.get(product_id)
        size_str = product.get_size_formatted() if product else "?"
        description = f"{layers_info} couches, {years}, ~{size_str}, hist: {hist_str}"

        toggle_items.append(
            ToggleItem(
                label=product_id,
                value=product_id,
                enabled=initial_selected,
                description=description,
            )
        )

    # Display the interactive widget
    result = select_toggle_list(toggle_items, title="Produits à importer")

    if result.cancelled:
        return []

    return result.enabled_values


def _get_effective_layer_config(
    prod_config: dict[str, Any],
    layer_name: str,
) -> dict[str, Any]:
    """Return the effective configuration of a layer (with inheritance).

    Args:
        prod_config: Product configuration.
        layer_name: Layer name.

    Returns:
        Effective layer configuration.
    """
    layers = prod_config.get("layers", {})
    layer_config = layers.get(layer_name, {}) if isinstance(layers, dict) else {}

    return {
        "enabled": layer_config.get("enabled", True),
        "table_name": layer_config.get("table_name"),
        "territory": layer_config.get("territory") or prod_config.get("territory", "FRA"),
        "format": layer_config.get("format") or prod_config.get("format", "shp"),
        "years": layer_config.get("years") or prod_config.get("years", ["2024"]),
        "historization": layer_config.get("historization") or prod_config.get("historization", {}),
    }


def run_import(
    product_ids: list[str],
    imports: dict[str, dict[str, Any]],
    settings: Settings,
    verbose: bool = False,
) -> dict[str, int]:
    """Execute the import of selected products.

    Iterates over the enabled layers of each product and uses
    the effective configuration (with inheritance) of each layer.

    Args:
        product_ids: List of product IDs to import.
        imports: Import configuration.
        settings: Application settings.
        verbose: Verbose mode.

    Returns:
        Dictionary {product_id: count} of imported records.
    """
    from pgboundary.loaders.product_loader import ProductLoader
    from pgboundary.products import FileFormat, get_default_catalog

    results: dict[str, int] = {}
    catalog = get_default_catalog()

    for product_id in product_ids:
        config = imports.get(product_id, {})
        product = catalog.get(product_id)

        if product is None:
            console.print(f"[yellow]Produit inconnu: {product_id}[/yellow]")
            continue

        # Get enabled layers
        enabled_layers = _get_enabled_layer_names(config)
        if not enabled_layers:
            console.print(f"[yellow]Aucune couche activée pour {product_id}[/yellow]")
            continue

        console.print(f"\n[bold blue]Import de {product.name}...[/bold blue]")
        console.print(f"  Couches: {', '.join(enabled_layers)}")

        try:
            # Create the loader
            loader = ProductLoader(
                product=product,
                catalog=catalog,
                settings=settings,
            )

            total = 0

            # Import each enabled layer
            for layer_name in enabled_layers:
                layer_config = _get_effective_layer_config(config, layer_name)

                console.print(f"\n  [cyan]{layer_name}[/cyan]")
                table_name = layer_config.get("table_name")
                if table_name:
                    console.print(f"    Table: {table_name}")

                file_format = FileFormat(layer_config["format"])
                territory = layer_config["territory"]
                years = layer_config["years"]

                # Import each year for this layer
                for year in years:
                    console.print(f"    Année {year}...")

                    # Determine the import mode
                    hist_config = layer_config.get("historization", {})
                    if_exists = "append" if hist_config.get("enabled", False) else "replace"

                    count = loader.load(
                        file_format=file_format,
                        territory=territory,
                        year=year,
                        layers=[layer_name],  # One layer at a time
                        if_exists=if_exists,  # type: ignore[arg-type]
                    )
                    total += count
                    console.print(f"      [green]{count} enregistrements[/green]")

            results[product_id] = total
            console.print(f"[green]✓ {product.name}: {total} enregistrements[/green]")

        except Exception as e:
            console.print(f"[red]✗ Erreur: {e}[/red]")
            if verbose:
                console.print_exception()
            results[product_id] = 0

    return results


def load_command(
    all_products: Annotated[
        bool,
        typer.Option("--all", "-a", help="Importe tous les produits activés sans validation."),
    ] = False,
    product: Annotated[
        str | None,
        typer.Option("--product", "-p", help="ID du produit à importer."),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Fichier de configuration."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Mode verbeux."),
    ] = False,
) -> None:
    """Load data according to the configuration.

    Without options: displays the configuration and asks for confirmation.
    With --all: imports without confirmation.
    With --product: imports a single product.
    """
    # Load the configuration
    config_path = config_file or (Path.cwd() / "pgboundary.yml")

    if not config_path.exists():
        console.print(f"[red]Configuration non trouvée: {config_path}[/red]")
        console.print("Utilisez [bold]pgboundary config init[/bold] pour créer la configuration.")
        raise typer.Exit(1)

    schema_config = load_config(config_path)
    imports = schema_config.imports

    if not imports:
        console.print("[yellow]Aucun produit configuré pour l'import.[/yellow]")
        console.print("Utilisez [bold]pgboundary config add-data[/bold] pour ajouter des produits.")
        raise typer.Exit(1)

    # Determine which products to import
    if product:
        # Single product
        if product not in imports:
            console.print(f"[red]Produit non configuré: {product}[/red]")
            console.print(f"Produits disponibles: {', '.join(imports.keys())}")
            raise typer.Exit(1)
        selected_products = [product]
    elif all_products:
        # All products with at least one enabled layer
        selected_products = [
            pid for pid, cfg in imports.items() if _get_enabled_layers_count(cfg)[0] > 0
        ]
    else:
        # Interactive selection
        selected_products = show_import_selection(imports)

    if not selected_products:
        console.print("[yellow]Aucun produit sélectionné.[/yellow]")
        raise typer.Exit(0)

    # Confirm if not --all
    if not all_products and not product:
        console.print(f"\n[bold]Produits à importer: {len(selected_products)}[/bold]")
        if not Confirm.ask("Lancer l'import ?"):
            raise typer.Exit(0)

    # Execute the import
    settings = Settings()
    results = run_import(selected_products, imports, settings, verbose)

    # Summary
    console.print()
    console.print(Panel.fit("[bold blue]Résumé de l'import[/bold blue]"))

    table = Table()
    table.add_column("Produit", style="cyan")
    table.add_column("Enregistrements", justify="right")

    total = 0
    for pid, count in results.items():
        table.add_row(pid, str(count))
        total += count

    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")
    console.print(table)


def _try_sqlite_url(
    product: IGNProduct,
    file_format: FileFormat,
    territory: str,
    date: str | None = None,
) -> str | None:
    """Attempt to resolve a download URL from the SQLite database.

    Args:
        product: IGN product with api_product.
        file_format: File format.
        territory: Territory code.
        date: Specific date (optional).

    Returns:
        URL from SQLite or None.
    """
    if not product.api_product:
        return None

    try:
        from pgboundary.config import Settings
        from pgboundary.products.catalog_db import CatalogDatabase

        settings = Settings()
        if not settings.catalog_db.exists():
            return None

        format_str = file_format.value.upper()
        with CatalogDatabase(settings.catalog_db) as db:
            return db.get_download_url(
                product.api_product,
                format_str,
                territory,
                date,
            )
    except Exception:
        return None


def _check_url(client: httpx.Client, url: str) -> tuple[int | None, str]:
    """Check the accessibility of a URL via HEAD request.

    Args:
        client: HTTP client.
        url: URL to check.

    Returns:
        Tuple (HTTP status code or None, message).
    """
    try:
        response = client.head(url)
        if response.status_code < 400:
            return response.status_code, "OK"
        return response.status_code, "Erreur"
    except httpx.RequestError as e:
        logger.debug("Erreur de requête pour %s: %s", url, e)
        return None, str(e)


def check_urls_command(
    all_products: Annotated[
        bool,
        typer.Option("--all", "-a", help="Vérifie tous les produits du catalogue."),
    ] = False,
    product_id: Annotated[
        str | None,
        typer.Option("--product", "-p", help="ID d'un produit spécifique à vérifier."),
    ] = None,
    date: Annotated[
        str | None,
        typer.Option(
            "--date",
            "-d",
            help="Date pour les URL (YYYY ou YYYY-MM-DD). Défaut: année précédente.",
        ),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Fichier de configuration."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Affiche les URL complètes."),
    ] = False,
    department: str | None = None,
) -> None:
    """Check the accessibility of download URLs.

    Without options: checks URLs of configured products.
    With --all: checks URLs of all products in the catalog.
    With --product: checks URLs of a specific product (all territories and formats).
    With --date: uses a specific date (e.g., 2025, 2025-09-15).
    With --department: checks URLs by department (requires --product).
    """
    from pgboundary.products import FileFormat, get_default_catalog
    from pgboundary.products.catalog import FRENCH_DEPARTMENTS, validate_department_code
    from pgboundary.sources.ign import IGNDataSource

    catalog = get_default_catalog()
    source = IGNDataSource()

    # Validate the --department parameter
    if department and not product_id:
        console.print("[red]L'option --department nécessite --product.[/red]")
        raise typer.Exit(1)

    # Current year data is typically not yet available, default to previous year
    default_year = str(datetime.now().year - 1)

    def _resolve_date(prod: IGNProduct) -> str:
        """Resolve the date to use: CLI option > product last_date > current year."""
        if date:
            return date
        if prod.last_date:
            return prod.last_date
        return default_year

    # Build the list of (label, url) to check
    urls_to_check: list[tuple[str, str]] = []

    if product_id:
        product = catalog.get(product_id)
        if product is None:
            console.print(f"[red]Produit inconnu: {product_id}[/red]")
            console.print("[dim]Produits disponibles: " + ", ".join(catalog.list_ids()) + "[/dim]")
            raise typer.Exit(1)
        if product.url_template.startswith("generated://"):
            console.print(f"[yellow]{product_id}: produit généré, pas d'URL à vérifier.[/yellow]")
            raise typer.Exit(0)

        # Handle download by department
        if department:
            if not product.supports_department_download:
                console.print(
                    f"[red]Le produit '{product_id}' ne supporte pas "
                    f"le téléchargement par département.[/red]"
                )
                raise typer.Exit(1)

            if department.lower() == "all":
                dept_codes = FRENCH_DEPARTMENTS
            else:
                if not validate_department_code(department):
                    console.print(f"[red]Code département invalide: '{department}'[/red]")
                    console.print("[dim]Codes valides: 01-19, 2A, 2B, 21-95, 971-976[/dim]")
                    raise typer.Exit(1)
                dept_codes = [department]

            for dept in dept_codes:
                url = source.build_department_url(product, dept)
                label = f"{product_id} (dept {dept})"
                urls_to_check.append((label, url))
        else:
            check_year = _resolve_date(product)
            for fmt in product.formats:
                for terr in product.territories:
                    url = _try_sqlite_url(product, fmt, terr.value, check_year) or ""
                    if not url:
                        try:
                            url = source.build_url(product, fmt, terr.value, check_year)
                        except (KeyError, IndexError):
                            url = product.url_template
                    label = f"{product_id} ({fmt.value}/{terr.value})"
                    urls_to_check.append((label, url))
    elif all_products:
        for prod in catalog.list_all():
            if prod.url_template.startswith("generated://"):
                continue
            fmt = prod.formats[0] if prod.formats else FileFormat.GPKG
            terr_str = prod.territories[0].value if prod.territories else "FRA"
            check_year = _resolve_date(prod)
            url = _try_sqlite_url(prod, fmt, terr_str, check_year) or ""
            if not url:
                try:
                    url = source.build_url(prod, fmt, terr_str, check_year)
                except (KeyError, IndexError):
                    url = prod.url_template
            urls_to_check.append((prod.id, url))
    else:
        config_path = config_file or (Path.cwd() / "pgboundary.yml")
        if not config_path.exists():
            console.print(f"[red]Configuration non trouvée: {config_path}[/red]")
            raise typer.Exit(1)

        schema_config = load_config(config_path)
        imports = schema_config.imports

        if not imports:
            console.print("[yellow]Aucun produit configuré.[/yellow]")
            raise typer.Exit(1)

        for pid, cfg in imports.items():
            configured_product = catalog.get(pid)
            if configured_product is None:
                urls_to_check.append((pid, ""))
                continue
            if configured_product.url_template.startswith("generated://"):
                continue

            terr_str = cfg.get("territory", "FRA")
            format_str = cfg.get("format", "gpkg")
            fmt = FileFormat(format_str)
            years = cfg.get("years", [_resolve_date(configured_product)])

            for year in years:
                url = _try_sqlite_url(configured_product, fmt, terr_str, year) or ""
                if not url:
                    try:
                        url = source.build_url(configured_product, fmt, terr_str, year)
                    except (KeyError, IndexError):
                        url = configured_product.url_template
                label = f"{pid} ({year})" if len(years) > 1 else pid
                urls_to_check.append((label, url))

    if not urls_to_check:
        console.print("[yellow]Aucune URL à vérifier.[/yellow]")
        raise typer.Exit(0)

    console.print(
        f"[bold blue]Vérification de {len(urls_to_check)} URL"
        + (f" (date: {date})" if date else "")
        + (f" (département: {department})" if department else "")
        + "...[/bold blue]\n"
    )

    table = Table(title="Vérification des URL", show_lines=verbose)
    table.add_column("Produit", style="cyan", no_wrap=True)
    if verbose:
        table.add_column("URL", overflow="fold")
    table.add_column("Statut", justify="right")
    table.add_column("Résultat")

    ok_count = 0
    ko_count = 0

    with httpx.Client(timeout=httpx.Timeout(15.0, connect=10.0), follow_redirects=True) as client:
        for product_label, url in urls_to_check:
            if not url:
                table.add_row(
                    product_label,
                    *([url] if verbose else []),
                    "-",
                    "[red]Produit inconnu[/red]",
                )
                ko_count += 1
                continue

            status_code, message = _check_url(client, url)

            if status_code is not None and status_code < 400:
                result_str = f"[green]{message}[/green]"
                ok_count += 1
            else:
                result_str = f"[red]{message}[/red]"
                ko_count += 1

            status_str = str(status_code) if status_code else "-"

            table.add_row(
                product_label,
                *([url] if verbose else []),
                status_str,
                result_str,
            )

    console.print(table)
    console.print()

    if ko_count == 0:
        console.print(f"[bold green]Toutes les {ok_count} URL sont accessibles.[/bold green]")
    else:
        console.print(f"[green]{ok_count} OK[/green], [red]{ko_count} en erreur[/red]")
        raise typer.Exit(1)
