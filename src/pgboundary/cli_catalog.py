"""Commandes CLI pour le catalogue des produits IGN.

Sous-groupe `pgboundary catalog` :
- catalog update : scrape l'API Atom, met à jour SQLite
- catalog list   : liste les produits connus
- catalog show   : détails d'un produit
"""

from __future__ import annotations

from typing import Annotated, Any

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from pgboundary.config import Settings

catalog_app = typer.Typer(
    name="catalog",
    help="Gestion du catalogue des produits IGN (API Atom).",
)

console = Console()


@catalog_app.command(name="update")
def catalog_update(
    product: Annotated[
        str | None,
        typer.Option("--product", "-p", help="Nom API d'un produit spécifique."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force le scan même si les données sont fraîches."),
    ] = False,
) -> None:
    """Scrape l'API Atom IGN et met à jour la base SQLite locale."""
    from pgboundary.sources.explorer import CatalogExplorer

    settings = Settings()
    explorer = CatalogExplorer(db_path=settings.catalog_db)

    if product:
        console.print(f"[bold blue]Scan du produit {product}...[/bold blue]")
        result = explorer.scan_product(product, force=force)
    else:
        console.print("[bold blue]Scan complet de l'API Atom IGN...[/bold blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Scan des produits", total=None)

            def on_progress(name: str, current: int, total: int) -> None:
                progress.update(task, total=total, completed=current, description=name or "Terminé")

            result = explorer.scan_all(force=force, progress_callback=on_progress)

    # Afficher le résultat
    console.print()
    table = Table(title="Résultat du scan")
    table.add_column("Métrique", style="cyan")
    table.add_column("Valeur", justify="right")

    table.add_row("Produits scannés", str(result.products_scanned))
    table.add_row("Éditions découvertes", str(result.editions_discovered))
    table.add_row("Éditions insérées/mises à jour", str(result.editions_new))
    table.add_row("Durée", f"{result.duration:.1f}s")
    table.add_row("Erreurs", str(len(result.errors)))

    console.print(table)

    if result.errors:
        console.print("\n[bold yellow]Erreurs :[/bold yellow]")
        for err in result.errors:
            console.print(f"  [red]• {err}[/red]")

    console.print(f"\n[dim]Base SQLite : {settings.catalog_db}[/dim]")


@catalog_app.command(name="list")
def catalog_list(
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filtrer par catégorie."),
    ] = None,
) -> None:
    """Liste les produits connus (SQLite + YAML)."""
    from pgboundary.products import get_default_catalog
    from pgboundary.products.catalog_db import CatalogDatabase

    settings = Settings()
    catalog = get_default_catalog()

    # Produits YAML
    yaml_products = catalog.list_all()
    if category:
        yaml_products = [p for p in yaml_products if p.category.value == category]

    # Produits SQLite (pour info supplémentaire)
    db_products: dict[str, dict[str, Any]] = {}
    if settings.catalog_db.exists():
        try:
            with CatalogDatabase(settings.catalog_db) as db:
                for p in db.list_products():
                    db_products[p["name"]] = p
        except Exception:
            pass

    table = Table(title="Catalogue des produits")
    table.add_column("ID", style="cyan")
    table.add_column("Nom", style="bold")
    table.add_column("Fournisseur")
    table.add_column("API", style="green")
    table.add_column("Catégorie")
    table.add_column("Éditions", justify="right")
    table.add_column("Dernière date")

    for product in yaml_products:
        api_name = product.api_product or ""
        editions_count = ""
        last_date = product.last_date or ""

        if api_name and settings.catalog_db.exists():
            try:
                with CatalogDatabase(settings.catalog_db) as db:
                    count = db.get_edition_count(api_name)
                    if count:
                        editions_count = str(count)
                    latest = db.get_latest_date(api_name)
                    if latest:
                        last_date = latest
            except Exception:
                pass

        table.add_row(
            product.id,
            product.name,
            product.provider,
            api_name,
            product.category.value,
            editions_count,
            last_date,
        )

    # Ajouter les produits SQLite non présents dans les YAML
    yaml_api_names = {p.api_product for p in catalog.list_all() if p.api_product}
    for name, info in db_products.items():
        if name not in yaml_api_names:
            try:
                with CatalogDatabase(settings.catalog_db) as db:
                    count = db.get_edition_count(name)
                    latest = db.get_latest_date(name) or ""
            except Exception:
                count = 0
                latest = ""

            table.add_row(
                "[dim]-[/dim]",
                info.get("title", name),
                "IGN",
                name,
                "[dim]non classé[/dim]",
                str(count) if count else "",
                latest,
            )

    console.print(table)

    if settings.catalog_db.exists():
        try:
            with CatalogDatabase(settings.catalog_db) as db:
                stats = db.get_stats()
            size_kb = stats["file_size"] / 1024
            console.print(
                f"\n[dim]SQLite : {stats['products']} produits, "
                f"{stats['editions']} éditions, {size_kb:.0f} Ko[/dim]"
            )
        except Exception:
            pass


@catalog_app.command(name="show")
def catalog_show(
    product_name: Annotated[
        str,
        typer.Argument(help="Nom API du produit (ex: ADMIN-EXPRESS-COG) ou ID YAML."),
    ],
) -> None:
    """Affiche les détails d'un produit : éditions, dates, formats, zones."""
    from pgboundary.products import get_default_catalog
    from pgboundary.products.catalog_db import CatalogDatabase

    settings = Settings()
    catalog = get_default_catalog()

    # Résoudre le nom : soit un ID YAML, soit un nom API
    yaml_product = catalog.get(product_name)
    api_name = product_name.upper()
    if yaml_product:
        api_name = yaml_product.api_product or product_name.upper()

    # Afficher les infos YAML si disponibles
    if yaml_product:
        console.print(f"\n[bold]{yaml_product.name}[/bold] ({yaml_product.id})")
        console.print(f"  Fournisseur : {yaml_product.provider}")
        console.print(f"  Catégorie   : {yaml_product.category.value}")
        console.print(f"  API         : {api_name}")
        console.print(f"  Formats     : {', '.join(f.value for f in yaml_product.formats)}")
        console.print(f"  Territoires : {', '.join(t.value for t in yaml_product.territories)}")
        console.print(f"  Taille      : {yaml_product.get_size_formatted()}")
    else:
        console.print(f"\n[bold]{api_name}[/bold] [dim](pas de définition YAML)[/dim]")

    # Afficher les éditions SQLite
    if not settings.catalog_db.exists():
        console.print(
            "\n[yellow]Base SQLite non trouvée. "
            "Exécutez [bold]pgboundary catalog update[/bold] d'abord.[/yellow]"
        )
        return

    try:
        with CatalogDatabase(settings.catalog_db) as db:
            db_product = db.get_product(api_name)
            if not db_product:
                console.print(f"\n[yellow]Produit {api_name} non trouvé dans SQLite.[/yellow]")
                return

            editions = db.get_editions(api_name)
            if not editions:
                console.print(f"\n[yellow]Aucune édition trouvée pour {api_name}.[/yellow]")
                return

            # Résumé
            dates = db.get_available_dates(api_name)
            console.print(f"\n  [cyan]Dates disponibles[/cyan] : {', '.join(dates[:10])}")
            if len(dates) > 10:
                console.print(f"    ... et {len(dates) - 10} de plus")

            # Tableau des éditions
            console.print()
            table = Table(title=f"Éditions de {api_name} ({len(editions)} total)")
            table.add_column("Titre", style="cyan", overflow="fold")
            table.add_column("Date")
            table.add_column("Format")
            table.add_column("Zone")
            table.add_column("CRS")

            # Limiter l'affichage à 50 éditions
            display_editions = editions[:50]
            for ed in display_editions:
                table.add_row(
                    ed["title"],
                    ed["edition_date"],
                    ed["format"],
                    ed["zone"],
                    ed["crs"],
                )

            console.print(table)

            if len(editions) > 50:
                console.print(
                    f"[dim]... {len(editions) - 50} éditions supplémentaires non affichées[/dim]"
                )

    except Exception as e:
        console.print(f"[red]Erreur lors de la lecture SQLite : {e}[/red]")
        raise typer.Exit(1) from e
