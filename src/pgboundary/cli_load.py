"""Commandes CLI pour le chargement des données.

Ce module fournit la commande load améliorée avec :
- Affichage de la configuration et choix multiple
- Option --all pour import sans validation
- Option --product pour import d'un seul produit
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from pgboundary.config import Settings
from pgboundary.schema_config import load_config

console = Console()


def show_import_selection(
    imports: dict[str, dict[str, Any]],
) -> list[str]:
    """Affiche les imports et permet la sélection.

    Args:
        imports: Configuration des imports.

    Returns:
        Liste des product_ids sélectionnés.
    """
    if not imports:
        console.print("[yellow]Aucun produit configuré pour l'import.[/yellow]")
        console.print("Utilisez [bold]pgboundary config add-data[/bold] pour ajouter des produits.")
        return []

    # État de sélection (initialisé avec enabled)
    selection: dict[str, bool] = {}
    products_list = list(imports.items())

    for product_id, config in products_list:
        selection[product_id] = config.get("enabled", True)

    while True:
        console.print()
        console.print(Panel.fit("[bold blue]Produits à importer[/bold blue]"))
        console.print()

        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=3)
        table.add_column("", width=3)  # Checkbox
        table.add_column("Produit", style="cyan")
        table.add_column("Couches")
        table.add_column("Années")
        table.add_column("Historisation")

        for i, (product_id, config) in enumerate(products_list, 1):
            checkbox = "[green]✓[/green]" if selection[product_id] else "[ ]"
            layers = ", ".join(config.get("layers", [])) or "toutes"
            years = ", ".join(config.get("years", []))
            hist = config.get("historization", {})
            hist_str = (
                f"{hist.get('method', 'jaccard')}"
                if hist.get("enabled", False)
                else "[dim]non[/dim]"
            )
            table.add_row(str(i), checkbox, product_id, layers, years, hist_str)

        console.print(table)
        console.print()

        # Instructions
        console.print("[bold]Actions :[/bold]")
        console.print("  [cyan]1-N[/cyan]  : Basculer la sélection d'un produit")
        console.print("  [cyan]t[/cyan]    : Tout sélectionner")
        console.print("  [cyan]n[/cyan]    : Tout désélectionner")
        console.print("  [cyan]v[/cyan]    : Valider et lancer l'import")
        console.print("  [cyan]a[/cyan]    : Annuler")
        console.print()

        choice = Prompt.ask("Choix", default="v")

        if choice.lower() == "a":
            return []
        elif choice.lower() == "v":
            return [pid for pid, selected in selection.items() if selected]
        elif choice.lower() == "t":
            for pid in selection:
                selection[pid] = True
        elif choice.lower() == "n":
            for pid in selection:
                selection[pid] = False
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(products_list):
                    product_id = products_list[idx][0]
                    selection[product_id] = not selection[product_id]
            except ValueError:
                pass


def run_import(
    product_ids: list[str],
    imports: dict[str, dict[str, Any]],
    settings: Settings,
    verbose: bool = False,
) -> dict[str, int]:
    """Exécute l'import des produits sélectionnés.

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

        console.print(f"\n[bold blue]Import de {product.name}...[/bold blue]")

        try:
            # Créer le loader
            loader = ProductLoader(
                product=product,
                catalog=catalog,
                settings=settings,
            )

            # Paramètres d'import
            file_format = FileFormat(config.get("format", "shp"))
            territory = config.get("territory", "FRA")
            years = config.get("years", ["2024"])
            layers = config.get("layers", None) or None

            # Importer chaque année
            total = 0
            for year in years:
                console.print(f"  Année {year}...")

                # Déterminer le mode d'import
                hist_config = config.get("historization", {})
                if_exists = "append" if hist_config.get("enabled", False) else "replace"

                count = loader.load(
                    file_format=file_format,
                    territory=territory,
                    year=year,
                    layers=layers,
                    if_exists=if_exists,  # type: ignore[arg-type]
                )
                total += count
                console.print(f"    [green]{count} enregistrements[/green]")

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
        # Tous les produits activés
        selected_products = [pid for pid, cfg in imports.items() if cfg.get("enabled", True)]
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
