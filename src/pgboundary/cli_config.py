"""Commandes CLI pour la configuration de pgBoundary.

Ce module fournit les sous-commandes de configuration :
- config : résumé de la configuration
- config info : affichage complet formaté
- config init : création interactive
- config update : modification interactive
- config db : configuration de la connexion à la base de données
- config data add : ajout de produits à importer
- config data remove : suppression de produits
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

console = Console()
config_app = typer.Typer(help="Gestion de la configuration pgBoundary")
data_app = typer.Typer(help="Gestion des produits à importer")
config_app.add_typer(data_app, name="data")


def _get_config_path() -> Path:
    """Retourne le chemin du fichier de configuration."""
    return Path.cwd() / DEFAULT_CONFIG_FILENAME


def _mask_password(url: str) -> str:
    """Masque le mot de passe dans une URL de base de données."""
    import re

    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)


@config_app.callback(invoke_without_command=True)
def config_main(ctx: typer.Context) -> None:
    """Affiche un résumé de la configuration (sans sous-commande)."""
    if ctx.invoked_subcommand is not None:
        return

    config_path = _get_config_path()

    if not config_path.exists():
        console.print(f"[yellow]Fichier de configuration non trouvé: {config_path}[/yellow]")
        console.print("Utilisez [bold]pgboundary config init[/bold] pour créer la configuration.")
        return

    config = load_config(config_path)

    # Résumé compact
    console.print(Panel.fit("[bold blue]Configuration pgBoundary[/bold blue]"))

    # Base de données
    from pgboundary.config import Settings

    try:
        settings = Settings()
        db_url = _mask_password(str(settings.database_url))
    except Exception:
        db_url = "[non configurée]"

    console.print(f"[bold]Base de données:[/bold] {db_url}")

    # Mode de stockage
    if config.storage.mode == StorageMode.SCHEMA:
        console.print(f"[bold]Stockage:[/bold] schéma [cyan]{config.storage.schema_name}[/cyan]")
    else:
        console.print(f"[bold]Stockage:[/bold] préfixe [cyan]{config.storage.table_prefix}[/cyan]")

    # Imports
    enabled, total = config.count_imports()
    if total == 0:
        console.print("[bold]Imports:[/bold] [yellow]aucun produit configuré[/yellow]")
    else:
        console.print(f"[bold]Imports:[/bold] {enabled}/{total} produits activés")

    console.print()
    console.print("[dim]Utilisez 'pgboundary config info' pour plus de détails[/dim]")


@config_app.command(name="info")
def config_info() -> None:
    """Affiche la configuration complète formatée avec Rich."""
    config_path = _get_config_path()

    if not config_path.exists():
        console.print(f"[red]Fichier de configuration non trouvé: {config_path}[/red]")
        raise typer.Exit(1)

    # Lire le fichier YAML brut pour l'affichage
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

    # Afficher l'URL (sans le mot de passe)
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
        # Charger la config existante comme valeurs par défaut
        existing_config = load_config(config_path)
    else:
        existing_config = SchemaConfig()

    console.print(Panel.fit("[bold blue]Configuration pgBoundary[/bold blue]"))
    console.print()

    # 1. Mode de stockage
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

    # 2. SRID
    console.print()
    console.print("[bold]2. Système de coordonnées[/bold]")
    console.print("  [cyan]4326[/cyan] : WGS84 (standard international)")
    console.print("  [cyan]2154[/cyan] : Lambert 93 (France métropolitaine)")
    console.print()

    srid = Prompt.ask(
        "SRID",
        default=str(existing_config.srid),
    )

    # Créer la configuration
    config = SchemaConfig(
        storage=storage,
        field_prefixes=existing_config.field_prefixes,
        table_names=existing_config.table_names,
        srid=int(srid),
        imports=existing_config.imports,
    )

    # 3. Ajouter des produits ?
    console.print()
    if Confirm.ask("Voulez-vous configurer des produits à importer ?"):
        _add_products_interactive(config)

    # Sauvegarder
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

    console.print(Panel.fit("[bold blue]Modification de la configuration[/bold blue]"))
    console.print()

    while True:
        console.print("[bold]Que voulez-vous modifier ?[/bold]")
        console.print("  [cyan]1[/cyan] : Mode de stockage")
        console.print("  [cyan]2[/cyan] : SRID")
        console.print("  [cyan]3[/cyan] : Produits à importer")
        console.print("  [cyan]4[/cyan] : Préfixes des colonnes")
        console.print("  [cyan]q[/cyan] : Quitter et sauvegarder")
        console.print()

        choice = Prompt.ask("Choix", choices=["1", "2", "3", "4", "q"], default="q")

        if choice == "q":
            break
        elif choice == "1":
            _update_storage(config)
        elif choice == "2":
            _update_srid(config)
        elif choice == "3":
            _update_imports(config)
        elif choice == "4":
            _update_prefixes(config)

        console.print()

    save_config(config, config_path)
    console.print(f"[green]Configuration sauvegardée: {config_path}[/green]")


def _update_storage(config: SchemaConfig) -> None:
    """Met à jour le mode de stockage."""
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
    """Met à jour le SRID."""
    console.print()
    srid = Prompt.ask("SRID", default=str(config.srid))
    config.srid = int(srid)


def _update_prefixes(config: SchemaConfig) -> None:
    """Met à jour les préfixes de colonnes."""
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


def _update_imports(config: SchemaConfig) -> None:
    """Met à jour la configuration des imports."""
    console.print()

    if not config.imports:
        console.print("[yellow]Aucun produit configuré.[/yellow]")
        if Confirm.ask("Ajouter des produits ?"):
            _add_products_interactive(config)
        return

    # Afficher les produits existants
    table = Table(title="Produits configurés")
    table.add_column("#", style="dim")
    table.add_column("Produit", style="cyan")
    table.add_column("Activé")
    table.add_column("Couches")
    table.add_column("Années")

    products_list = list(config.imports.items())
    for i, (product_id, prod_config) in enumerate(products_list, 1):
        enabled = "[green]oui[/green]" if prod_config.get("enabled", True) else "[red]non[/red]"
        layers = ", ".join(prod_config.get("layers", [])) or "toutes"
        years = ", ".join(prod_config.get("years", []))
        table.add_row(str(i), product_id, enabled, layers, years)

    console.print(table)
    console.print()

    console.print("[bold]Actions :[/bold]")
    console.print("  [cyan]a[/cyan] : Ajouter un produit")
    console.print("  [cyan]s[/cyan] : Supprimer un produit")
    console.print("  [cyan]t[/cyan] : Activer/désactiver un produit")
    console.print("  [cyan]m[/cyan] : Modifier un produit")
    console.print("  [cyan]q[/cyan] : Retour")
    console.print()

    action = Prompt.ask("Action", choices=["a", "s", "t", "m", "q"], default="q")

    if action == "a":
        _add_products_interactive(config)
    elif action == "s" and products_list:
        num = Prompt.ask("Numéro du produit à supprimer", default="1")
        idx = int(num) - 1
        if 0 <= idx < len(products_list):
            product_id = products_list[idx][0]
            del config.imports[product_id]
            console.print(f"[green]Produit {product_id} supprimé[/green]")
    elif action == "t" and products_list:
        num = Prompt.ask("Numéro du produit à basculer", default="1")
        idx = int(num) - 1
        if 0 <= idx < len(products_list):
            product_id = products_list[idx][0]
            current = config.imports[product_id].get("enabled", True)
            config.imports[product_id]["enabled"] = not current
            status = "activé" if not current else "désactivé"
            console.print(f"[green]Produit {product_id} {status}[/green]")
    elif action == "m" and products_list:
        num = Prompt.ask("Numéro du produit à modifier", default="1")
        idx = int(num) - 1
        if 0 <= idx < len(products_list):
            product_id = products_list[idx][0]
            _modify_product_config(config, product_id)


def _modify_product_config(config: SchemaConfig, product_id: str) -> None:
    """Modifie la configuration d'un produit."""
    prod_config = config.imports[product_id]

    console.print(f"\n[bold]Modification de {product_id}[/bold]")

    # Années
    current_years = prod_config.get("years", ["2024"])
    years_str = Prompt.ask(
        "Années (séparées par des virgules)",
        default=",".join(current_years),
    )
    prod_config["years"] = [y.strip() for y in years_str.split(",")]

    # Territoire
    prod_config["territory"] = Prompt.ask(
        "Territoire",
        default=prod_config.get("territory", "FRA"),
    )

    # Format
    prod_config["format"] = Prompt.ask(
        "Format",
        choices=["shp", "gpkg"],
        default=prod_config.get("format", "shp"),
    )

    # Historisation
    if Confirm.ask(
        "Activer l'historisation ?",
        default=prod_config.get("historization", {}).get("enabled", False),
    ):
        hist = prod_config.setdefault("historization", {})
        hist["enabled"] = True
        hist["method"] = Prompt.ask(
            "Méthode de comparaison",
            choices=["md5", "jaccard", "hausdorff"],
            default=hist.get("method", "jaccard"),
        )
        if hist["method"] != "md5":
            threshold = Prompt.ask(
                "Seuil",
                default=str(hist.get("threshold", 0.95)),
            )
            hist["threshold"] = float(threshold)
        hist["key_field"] = Prompt.ask(
            "Champ clé",
            default=hist.get("key_field", "cd_insee"),
        )
    else:
        prod_config["historization"] = {"enabled": False}


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

    _add_products_interactive(config)

    save_config(config, config_path)
    console.print(f"[green]Configuration sauvegardée: {config_path}[/green]")


@data_app.command(name="remove")
def data_remove(
    product_ids: Annotated[
        list[str] | None,
        typer.Argument(help="IDs des produits à supprimer (ex: admin-express-cog contours-iris)."),
    ] = None,
) -> None:
    """Supprime des produits de la configuration.

    Sans argument: mode interactif pour sélectionner les produits à supprimer.
    Avec arguments: supprime les produits spécifiés directement.
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
        # Mode direct : supprimer les produits spécifiés
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
        # Mode interactif
        _remove_products_interactive(config)
        save_config(config, config_path)
        console.print(f"[green]Configuration sauvegardée: {config_path}[/green]")


@config_app.command(name="sync-product")
def config_sync_product(
    product_id: Annotated[
        str | None,
        typer.Argument(help="ID du produit à synchroniser (tous si non spécifié)."),
    ] = None,
) -> None:
    """Synchronise le statut d'injection des produits avec la base de données.

    Vérifie quelles tables existent dans la base de données et met à jour
    le statut d'injection dans la configuration.
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

    # Filtrer par produit si spécifié
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
            # Récupérer les tables existantes avec leur nombre de lignes
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

            # Table pour l'affichage
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

                # Vérifier les tables du produit
                found_tables = []
                total_count = 0

                for layer in product.layers:
                    table_key = layer.table_key
                    table_name = config.get_full_table_name(table_key)

                    if table_name in existing_tables:
                        found_tables.append(table_name)
                        # Compter les lignes
                        full_name = f"{schema_name}.{table_name}"
                        count_query = text(f"SELECT COUNT(*) FROM {full_name}")
                        count = session.execute(count_query).scalar()
                        total_count += count or 0

                if found_tables:
                    # Produit injecté
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
                    # Produit non injecté
                    config.update_injection_status(pid, injected=False)
                    status = "[dim]Non injecté[/dim]"

                table.add_row(
                    pid,
                    str(len(found_tables)),
                    f"{total_count:,}" if total_count > 0 else "-",
                    status,
                )

            console.print(table)

        # Sauvegarder la configuration mise à jour
        save_config(config, config_path)
        console.print(f"\n[green]Configuration synchronisée: {config_path}[/green]")

    except Exception as e:
        console.print(f"[bold red]Erreur: {e}[/bold red]")
        raise typer.Exit(1) from e


def _remove_products_interactive(config: SchemaConfig) -> None:
    """Supprime des produits de manière interactive."""
    while True:
        if not config.imports:
            console.print("[yellow]Aucun produit configuré.[/yellow]")
            return

        # Afficher les produits existants
        console.print()
        table = Table(title="Produits configurés")
        table.add_column("#", style="dim")
        table.add_column("Produit", style="cyan")
        table.add_column("Activé")
        table.add_column("Années")

        products_list = list(config.imports.items())
        for i, (product_id, prod_config) in enumerate(products_list, 1):
            enabled = "[green]oui[/green]" if prod_config.get("enabled", True) else "[red]non[/red]"
            years = ", ".join(prod_config.get("years", []))
            table.add_row(str(i), product_id, enabled, years)

        console.print(table)
        console.print()

        console.print("Entrez le numéro du produit à supprimer (ou 'q' pour quitter) :")
        choice = Prompt.ask("Choix", default="q")

        if choice.lower() == "q":
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(products_list):
                product_id = products_list[idx][0]
                if Confirm.ask(f"Supprimer le produit [cyan]{product_id}[/cyan] ?"):
                    del config.imports[product_id]
                    console.print(f"[green]Produit {product_id} supprimé[/green]")
            else:
                console.print("[red]Numéro invalide[/red]")
        except ValueError:
            console.print("[red]Veuillez entrer un numéro valide[/red]")


def _add_products_interactive(config: SchemaConfig) -> None:
    """Ajoute des produits via navigation interactive."""
    catalog = get_default_catalog()

    while True:
        console.print()
        console.print("[bold]Catégories de produits :[/bold]")

        # Grouper par catégorie
        categories: dict[str, list[IGNProduct]] = {}
        for product in catalog:
            cat = product.category.value
            categories.setdefault(cat, []).append(product)

        cat_list = list(categories.keys())
        for i, cat in enumerate(cat_list, 1):
            count = len(categories[cat])
            console.print(f"  [cyan]{i}[/cyan] : {cat} ({count} produits)")
        console.print("  [cyan]q[/cyan] : Terminer")
        console.print()

        choice = Prompt.ask("Catégorie", default="q")
        if choice == "q":
            break

        try:
            cat_idx = int(choice) - 1
            if 0 <= cat_idx < len(cat_list):
                category = cat_list[cat_idx]
                _select_product_from_category(config, categories[category])
        except ValueError:
            continue


def _select_product_from_category(
    config: SchemaConfig,
    products: list[IGNProduct],
) -> None:
    """Sélectionne un produit dans une catégorie."""
    console.print()
    console.print("[bold]Produits disponibles :[/bold]")

    for i, product in enumerate(products, 1):
        # Marquer si déjà configuré
        marker = "[green]✓[/green] " if product.id in config.imports else "  "
        console.print(f"  {marker}[cyan]{i}[/cyan] : {product.name}")
        console.print(f"       [dim]{product.description_fr}[/dim]")

    console.print("  [cyan]q[/cyan] : Retour")
    console.print()

    choice = Prompt.ask("Produit", default="q")
    if choice == "q":
        return

    try:
        prod_idx = int(choice) - 1
        if 0 <= prod_idx < len(products):
            product = products[prod_idx]
            _configure_product(config, product)
    except ValueError:
        pass


def _configure_product(config: SchemaConfig, product: IGNProduct) -> None:
    """Configure un produit pour l'import."""
    console.print()
    console.print(Panel.fit(f"[bold blue]{product.name}[/bold blue]"))
    console.print(f"[dim]{product.description_fr}[/dim]")
    console.print()

    # Afficher les couches disponibles
    console.print("[bold]Couches disponibles :[/bold]")
    tree = Tree(f"[cyan]{product.id}[/cyan]")
    for layer in product.layers:
        layer_desc = layer.description_fr or layer.name
        tree.add(f"{layer.name} - [dim]{layer_desc}[/dim]")
    console.print(tree)
    console.print()

    # Sélectionner les couches
    all_layers = [layer.name for layer in product.layers]
    console.print("Couches à importer (séparées par des virgules, ou 'all' pour toutes) :")
    layers_input = Prompt.ask("Couches", default="all")

    if layers_input.lower() == "all":
        selected_layers: list[str] = []
    else:
        selected_layers = [
            layer.strip() for layer in layers_input.split(",") if layer.strip() in all_layers
        ]

    # Territoire
    territories = [t.value for t in product.territories]
    territory = Prompt.ask(
        "Territoire",
        default=territories[0] if territories else "FRA",
    )

    # Format
    formats = [f.value for f in product.formats]
    file_format = Prompt.ask(
        "Format",
        choices=formats,
        default=formats[0] if formats else "shp",
    )

    # Années
    years_input = Prompt.ask("Années (séparées par des virgules)", default="2024")
    years = [y.strip() for y in years_input.split(",")]

    # Historisation
    hist_config: dict[str, Any] = {"enabled": False}
    if Confirm.ask("Activer l'historisation ?", default=False):
        hist_config["enabled"] = True
        hist_config["method"] = Prompt.ask(
            "Méthode de comparaison",
            choices=["md5", "jaccard", "hausdorff"],
            default="jaccard",
        )
        if hist_config["method"] != "md5":
            threshold = Prompt.ask("Seuil", default="0.95")
            hist_config["threshold"] = float(threshold)
        hist_config["key_field"] = Prompt.ask(
            "Champ clé d'identification",
            default="cd_insee",
        )

    # Enregistrer
    config.imports[product.id] = {
        "enabled": True,
        "layers": selected_layers,
        "territory": territory,
        "format": file_format,
        "years": years,
        "historization": hist_config,
    }

    console.print(f"[green]Produit {product.id} ajouté à la configuration[/green]")
