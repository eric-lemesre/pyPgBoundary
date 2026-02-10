"""Commandes CLI pour le chargement des données.

Ce module fournit la commande load améliorée avec :
- Affichage de la configuration et choix multiple
- Option --all pour import sans validation
- Option --product pour import d'un seul produit
- Sous-commande check pour vérifier les URL de téléchargement
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

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
    """Compte les couches activées dans une configuration de produit.

    Args:
        prod_config: Configuration du produit.

    Returns:
        Tuple (nombre activées, nombre total).
    """
    layers = prod_config.get("layers", {})
    if isinstance(layers, dict):
        total = len(layers)
        enabled = sum(1 for layer in layers.values() if layer.get("enabled", True))
        return enabled, total
    # Ancienne structure (liste)
    return len(layers), len(layers) if layers else 0


def _get_enabled_layer_names(prod_config: dict[str, Any]) -> list[str]:
    """Retourne les noms des couches activées.

    Args:
        prod_config: Configuration du produit.

    Returns:
        Liste des noms de couches activées.
    """
    layers = prod_config.get("layers", {})
    if isinstance(layers, dict):
        return [name for name, cfg in layers.items() if cfg.get("enabled", True)]
    # Ancienne structure (liste)
    return list(layers) if layers else []


def show_import_selection(
    imports: dict[str, dict[str, Any]],
) -> list[str]:
    """Affiche les imports et permet la sélection.

    Args:
        imports: Configuration des imports.

    Returns:
        Liste des product_ids sélectionnés.
    """
    from pgboundary.cli_widgets import ToggleItem, select_toggle_list
    from pgboundary.products import get_default_catalog

    if not imports:
        console.print("[yellow]Aucun produit configuré pour l'import.[/yellow]")
        console.print("Utilisez [bold]pgboundary config add-data[/bold] pour ajouter des produits.")
        return []

    catalog = get_default_catalog()

    # Construire les items pour le widget
    products_list = list(imports.items())
    toggle_items = []

    for product_id, config in products_list:
        enabled_count, total_count = _get_enabled_layers_count(config)
        initial_selected = enabled_count > 0

        # Construire la description
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

    # Afficher le widget interactif
    result = select_toggle_list(toggle_items, title="Produits à importer")

    if result.cancelled:
        return []

    return result.enabled_values


def _get_effective_layer_config(
    prod_config: dict[str, Any],
    layer_name: str,
) -> dict[str, Any]:
    """Retourne la configuration effective d'une couche (avec héritage).

    Args:
        prod_config: Configuration du produit.
        layer_name: Nom de la couche.

    Returns:
        Configuration effective de la couche.
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
    """Exécute l'import des produits sélectionnés.

    Itère sur les couches activées de chaque produit et utilise
    la configuration effective (avec héritage) de chaque couche.

    Args:
        product_ids: Liste des IDs de produits à importer.
        imports: Configuration des imports.
        settings: Paramètres de l'application.
        verbose: Mode verbeux.

    Returns:
        Dictionnaire {product_id: count} des enregistrements importés.
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

        # Obtenir les couches activées
        enabled_layers = _get_enabled_layer_names(config)
        if not enabled_layers:
            console.print(f"[yellow]Aucune couche activée pour {product_id}[/yellow]")
            continue

        console.print(f"\n[bold blue]Import de {product.name}...[/bold blue]")
        console.print(f"  Couches: {', '.join(enabled_layers)}")

        try:
            # Créer le loader
            loader = ProductLoader(
                product=product,
                catalog=catalog,
                settings=settings,
            )

            total = 0

            # Importer chaque couche activée
            for layer_name in enabled_layers:
                layer_config = _get_effective_layer_config(config, layer_name)

                console.print(f"\n  [cyan]{layer_name}[/cyan]")
                table_name = layer_config.get("table_name")
                if table_name:
                    console.print(f"    Table: {table_name}")

                file_format = FileFormat(layer_config["format"])
                territory = layer_config["territory"]
                years = layer_config["years"]

                # Importer chaque année pour cette couche
                for year in years:
                    console.print(f"    Année {year}...")

                    # Déterminer le mode d'import
                    hist_config = layer_config.get("historization", {})
                    if_exists = "append" if hist_config.get("enabled", False) else "replace"

                    count = loader.load(
                        file_format=file_format,
                        territory=territory,
                        year=year,
                        layers=[layer_name],  # Une seule couche à la fois
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
    """Charge les données selon la configuration.

    Sans option: affiche la configuration et demande validation.
    Avec --all: importe sans validation.
    Avec --product: importe un seul produit.
    """
    # Charger la configuration
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

    # Déterminer les produits à importer
    if product:
        # Un seul produit
        if product not in imports:
            console.print(f"[red]Produit non configuré: {product}[/red]")
            console.print(f"Produits disponibles: {', '.join(imports.keys())}")
            raise typer.Exit(1)
        selected_products = [product]
    elif all_products:
        # Tous les produits avec au moins une couche activée
        selected_products = [
            pid for pid, cfg in imports.items() if _get_enabled_layers_count(cfg)[0] > 0
        ]
    else:
        # Sélection interactive
        selected_products = show_import_selection(imports)

    if not selected_products:
        console.print("[yellow]Aucun produit sélectionné.[/yellow]")
        raise typer.Exit(0)

    # Confirmer si pas --all
    if not all_products and not product:
        console.print(f"\n[bold]Produits à importer: {len(selected_products)}[/bold]")
        if not Confirm.ask("Lancer l'import ?"):
            raise typer.Exit(0)

    # Exécuter l'import
    settings = Settings()
    results = run_import(selected_products, imports, settings, verbose)

    # Résumé
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


def _check_url(client: httpx.Client, url: str) -> tuple[int | None, str]:
    """Vérifie l'accessibilité d'une URL par requête HEAD.

    Args:
        client: Client HTTP.
        url: URL à vérifier.

    Returns:
        Tuple (code HTTP ou None, message).
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
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Fichier de configuration."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Affiche les URL complètes."),
    ] = False,
) -> None:
    """Vérifie l'accessibilité des URL de téléchargement.

    Sans option: vérifie les URL des produits configurés.
    Avec --all: vérifie les URL de tous les produits du catalogue.
    """
    from pgboundary.products import FileFormat, get_default_catalog
    from pgboundary.sources.ign import IGNDataSource

    catalog = get_default_catalog()
    source = IGNDataSource()

    # Construire la liste des (product_id, format, territory, year) à vérifier
    urls_to_check: list[tuple[str, str]] = []

    if all_products:
        current_year = str(datetime.now().year)
        for product in catalog.list_all():
            if product.url_template.startswith("generated://"):
                continue
            file_format = product.formats[0] if product.formats else FileFormat.GPKG
            territory = product.territories[0].value if product.territories else "FRA"
            try:
                url = source.build_url(product, file_format, territory, current_year)
            except (KeyError, IndexError):
                url = product.url_template
            urls_to_check.append((product.id, url))
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

        for product_id, config in imports.items():
            configured_product = catalog.get(product_id)
            if configured_product is None:
                urls_to_check.append((product_id, ""))
                continue
            if configured_product.url_template.startswith("generated://"):
                continue

            territory = config.get("territory", "FRA")
            format_str = config.get("format", "gpkg")
            file_format = FileFormat(format_str)
            years = config.get("years", [str(datetime.now().year)])

            for year in years:
                try:
                    url = source.build_url(configured_product, file_format, territory, year)
                except (KeyError, IndexError):
                    url = configured_product.url_template
                label = f"{product_id} ({year})" if len(years) > 1 else product_id
                urls_to_check.append((label, url))

    if not urls_to_check:
        console.print("[yellow]Aucune URL à vérifier.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold blue]Vérification de {len(urls_to_check)} URL...[/bold blue]\n")

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
