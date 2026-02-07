"""Interface en ligne de commande pour pyPgBoundary."""

import logging
from pathlib import Path
from typing import Annotated, Literal, cast

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from pgboundary import __version__
from pgboundary.config import (
    Settings,
    build_database_url,
    has_database_url_configured,
    save_database_url_to_env,
)
from pgboundary.db.connection import DatabaseManager
from pgboundary.loaders.admin_express import AdminExpressLoader
from pgboundary.loaders.product_loader import ProductLoader
from pgboundary.products import (
    FileFormat,
    ProductCategory,
    get_default_catalog,
)
from pgboundary.schema_config import (
    DEFAULT_CONFIG_FILENAME,
    SchemaConfig,
    StorageConfig,
    StorageMode,
    create_default_config,
    load_config,
    save_config,
)
from pgboundary.sources.ign import IGNDataSource

app = typer.Typer(
    name="pgboundary",
    help="Chargement des limites administratives françaises dans PostgreSQL/PostGIS.",
    add_completion=False,
)
console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure le logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def version_callback(value: bool) -> None:
    """Affiche la version et quitte."""
    if value:
        console.print(f"[bold]pgboundary[/bold] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Affiche la version.",
        ),
    ] = None,
) -> None:
    """pyPgBoundary - Limites administratives françaises pour PostgreSQL."""
    pass


@app.command()
def config(
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Chemin du fichier de configuration."),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option("--interactive", "-i", help="Mode interactif pour créer la configuration."),
    ] = False,
    show: Annotated[
        bool,
        typer.Option("--show", "-s", help="Affiche la configuration actuelle."),
    ] = False,
) -> None:
    """Gère le fichier de configuration YAML."""
    config_path = config_file or Path.cwd() / DEFAULT_CONFIG_FILENAME

    if show:
        if not config_path.exists():
            console.print(f"[yellow]Fichier de configuration inexistant: {config_path}[/yellow]")
            raise typer.Exit(1)

        cfg = load_config(config_path)
        _display_config(cfg, config_path)
        return

    if interactive:
        cfg = _interactive_config()
        save_config(cfg, config_path)
        console.print(f"[green]Configuration sauvegardée: {config_path}[/green]")
        _display_config(cfg, config_path)
    else:
        if config_path.exists():
            console.print(f"[yellow]Le fichier existe déjà: {config_path}[/yellow]")
            if not Confirm.ask("Voulez-vous le recréer avec les valeurs par défaut ?"):
                raise typer.Exit()

        create_default_config(config_path)
        console.print(f"[green]Fichier de configuration créé: {config_path}[/green]")


def _interactive_database_config() -> str:
    """Configure la connexion à la base de données en mode interactif.

    Returns:
        URL de connexion PostgreSQL.
    """
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

    return database_url


def _ensure_database_configured(
    database_url: str | None = None,
    interactive: bool = False,
) -> str | None:
    """S'assure que la base de données est configurée.

    Si aucune URL n'est fournie et qu'aucune configuration n'existe,
    propose la configuration interactive.

    Args:
        database_url: URL fournie en paramètre CLI.
        interactive: Mode interactif activé.

    Returns:
        URL de connexion ou None si configuration annulée.
    """
    # Si une URL est fournie en paramètre, l'utiliser
    if database_url:
        return database_url

    # Vérifier si une configuration existe
    if has_database_url_configured():
        return None  # Utiliser la config existante

    # Pas de configuration, proposer le mode interactif
    console.print("[yellow]Aucune configuration de base de données détectée.[/yellow]")

    if interactive or Confirm.ask(
        "Voulez-vous configurer la connexion à la base de données maintenant ?"
    ):
        return _interactive_database_config()

    console.print(
        "[dim]Vous pouvez configurer la base de données plus tard avec:[/dim]\n"
        "  [cyan]pgboundary setup-db[/cyan]"
    )
    return None


def _interactive_config() -> SchemaConfig:
    """Crée une configuration en mode interactif."""
    console.print(Panel("[bold]Configuration du schéma de base de données[/bold]"))

    mode_choice = Prompt.ask(
        "Mode de stockage",
        choices=["schema", "prefix"],
        default="schema",
    )
    mode = StorageMode(mode_choice)

    if mode == StorageMode.SCHEMA:
        schema_name = Prompt.ask("Nom du schéma PostgreSQL", default="geo")
        table_prefix = "geo_"
    else:
        schema_name = "geo"
        table_prefix = Prompt.ask("Préfixe des tables", default="geo_")

    storage = StorageConfig(
        mode=mode,
        schema_name=schema_name,
        table_prefix=table_prefix,
    )

    console.print("\n[bold]Préfixes des colonnes:[/bold]")
    console.print("  - cd_* pour les codes (ex: cd_insee)")
    console.print("  - lb_* pour les libellés (ex: lb_nom)")
    console.print("  - dt_* pour les dates (ex: dt_creation)")

    if not Confirm.ask("\nGarder les préfixes par défaut ?", default=True):
        from pgboundary.schema_config import FieldPrefixes

        code_prefix = Prompt.ask("Préfixe pour les codes", default="cd_")
        label_prefix = Prompt.ask("Préfixe pour les libellés", default="lb_")
        date_prefix = Prompt.ask("Préfixe pour les dates", default="dt_")
        field_prefixes = FieldPrefixes(code=code_prefix, label=label_prefix, date=date_prefix)
    else:
        from pgboundary.schema_config import FieldPrefixes

        field_prefixes = FieldPrefixes()

    srid = int(Prompt.ask("SRID des géométries", default="4326"))

    return SchemaConfig(
        storage=storage,
        field_prefixes=field_prefixes,
        srid=srid,
    )


def _display_config(cfg: SchemaConfig, config_path: Path) -> None:
    """Affiche la configuration."""
    table = Table(title=f"Configuration: {config_path}")
    table.add_column("Paramètre", style="cyan")
    table.add_column("Valeur", style="green")

    table.add_row("Mode de stockage", cfg.storage.mode.value)
    if cfg.storage.mode == StorageMode.SCHEMA:
        table.add_row("Schéma", cfg.storage.schema_name)
    else:
        table.add_row("Préfixe tables", cfg.storage.table_prefix)

    table.add_row("Préfixe codes", cfg.field_prefixes.code)
    table.add_row("Préfixe libellés", cfg.field_prefixes.label)
    table.add_row("Préfixe dates", cfg.field_prefixes.date)
    table.add_row("SRID", str(cfg.srid))

    console.print(table)

    console.print("\n[bold]Tables qui seront créées:[/bold]")
    for key in ["region", "departement", "epci", "commune", "commune_associee_deleguee"]:
        full_name = cfg.get_full_table_name(key)
        schema = cfg.get_schema_name()
        if schema:
            console.print(f"  • {schema}.{full_name}")
        else:
            console.print(f"  • {full_name}")


@app.command(name="setup-db")
def setup_db(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Mode verbeux."),
    ] = False,
) -> None:
    """Configure la connexion à la base de données de manière interactive."""
    setup_logging(verbose)

    if has_database_url_configured():
        settings = Settings()
        console.print(f"[yellow]Configuration existante:[/yellow] {settings.database_url}")
        if not Confirm.ask("Voulez-vous la modifier ?"):
            raise typer.Exit()

    _interactive_database_config()


@app.command()
def init(
    database_url: Annotated[
        str | None,
        typer.Option("--database-url", "-d", help="URL de connexion PostgreSQL."),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Chemin du fichier de configuration."),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option("--interactive", "-i", help="Mode interactif pour la configuration."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Mode verbeux."),
    ] = False,
) -> None:
    """Initialise la base de données (schéma et tables)."""
    setup_logging(verbose)

    # Vérifier/configurer la connexion à la base de données
    db_url = _ensure_database_configured(database_url, interactive)

    config_path = config_file or Path.cwd() / DEFAULT_CONFIG_FILENAME

    if not config_path.exists():
        console.print(f"[yellow]Fichier de configuration inexistant: {config_path}[/yellow]")
        if interactive or Confirm.ask("Voulez-vous créer la configuration maintenant ?"):
            if interactive:
                cfg = _interactive_config()
                save_config(cfg, config_path)
            else:
                create_default_config(config_path)
            console.print(f"[green]Configuration créée: {config_path}[/green]")
        else:
            raise typer.Exit(1)

    settings = Settings(config_file=config_path)
    if db_url:
        settings.database_url = db_url

    console.print("[bold blue]Initialisation de la base de données...[/bold blue]")
    _display_config(settings.schema_config, config_path)

    try:
        db = DatabaseManager(settings)
        db.init_database()
        console.print("[bold green]Base de données initialisée avec succès ![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Erreur: {e}[/bold red]")
        raise typer.Exit(1) from e


@app.command()
def download(
    territory: Annotated[
        str,
        typer.Option(
            "--territory", "-t", help="Territoire (france_metropolitaine, france_entiere)."
        ),
    ] = "france_metropolitaine",
    year: Annotated[
        str,
        typer.Option("--year", "-y", help="Année des données."),
    ] = "2024",
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force le re-téléchargement."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Mode verbeux."),
    ] = False,
) -> None:
    """Télécharge les données Admin Express depuis l'IGN."""
    setup_logging(verbose)

    settings = Settings()
    source = IGNDataSource(settings)

    console.print(f"[bold blue]Téléchargement des données {territory} {year}...[/bold blue]")

    try:
        territory_lit = cast("Literal['france_metropolitaine', 'france_entiere']", territory)
        archive_path = source.download_legacy(territory=territory_lit, year=year, force=force)
        console.print(f"[green]Archive téléchargée: {archive_path}[/green]")

        extract_path = source.extract(archive_path, force=force)
        console.print(f"[green]Données extraites: {extract_path}[/green]")

        shapefiles = source.find_shapefiles(extract_path)

        table = Table(title="Shapefiles trouvés")
        table.add_column("Couche", style="cyan")
        table.add_column("Fichier", style="green")

        for layer, path in shapefiles.items():
            table.add_row(layer, str(path.name))

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Erreur: {e}[/bold red]")
        raise typer.Exit(1) from e
    finally:
        source.close()


@app.command()
def load(
    source_path: Annotated[
        Path | None,
        typer.Option("--source", "-s", help="Chemin vers les données extraites."),
    ] = None,
    territory: Annotated[
        str,
        typer.Option("--territory", "-t", help="Territoire à télécharger si source non fournie."),
    ] = "france_metropolitaine",
    year: Annotated[
        str,
        typer.Option("--year", "-y", help="Année des données."),
    ] = "2024",
    layers: Annotated[
        str | None,
        typer.Option("--layers", "-l", help="Couches à charger (séparées par des virgules)."),
    ] = None,
    database_url: Annotated[
        str | None,
        typer.Option("--database-url", "-d", help="URL de connexion PostgreSQL."),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Chemin du fichier de configuration."),
    ] = None,
    replace: Annotated[
        bool,
        typer.Option("--replace", "-r", help="Remplace les tables existantes."),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Mode verbeux."),
    ] = False,
) -> None:
    """Charge les limites administratives dans PostgreSQL."""
    setup_logging(verbose)

    config_path = config_file or Path.cwd() / DEFAULT_CONFIG_FILENAME
    settings = Settings(config_file=config_path)
    if database_url:
        settings.database_url = database_url

    layers_list = layers.split(",") if layers else None
    if_exists_lit: Literal["replace", "append", "fail"] = "replace" if replace else "fail"
    territory_lit = cast("Literal['france_metropolitaine', 'france_entiere']", territory)

    console.print("[bold blue]Chargement des données...[/bold blue]")

    try:
        loader = AdminExpressLoader(settings=settings)

        count = loader.load(
            source_path=source_path,
            territory=territory_lit,
            year=year,
            layers=layers_list,
            if_exists=if_exists_lit,
        )

        console.print(f"[bold green]Chargement terminé: {count} entités chargées[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Erreur: {e}[/bold red]")
        raise typer.Exit(1) from e


@app.command()
def info(
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Chemin du fichier de configuration."),
    ] = None,
) -> None:
    """Affiche les informations de configuration."""
    config_path = config_file or Path.cwd() / DEFAULT_CONFIG_FILENAME
    settings = Settings(config_file=config_path)

    table = Table(title="Configuration pgBoundary")
    table.add_column("Paramètre", style="cyan")
    table.add_column("Valeur", style="green")

    table.add_row("Version", __version__)
    table.add_row("Database URL", str(settings.database_url))
    table.add_row("Fichier config", str(config_path))
    table.add_row("Config existe", "Oui" if config_path.exists() else "Non")
    table.add_row("Répertoire données", str(settings.data_dir))
    table.add_row("Niveau log", settings.log_level)

    console.print(table)

    if config_path.exists():
        console.print()
        _display_config(settings.schema_config, config_path)


@app.command()
def check(
    database_url: Annotated[
        str | None,
        typer.Option("--database-url", "-d", help="URL de connexion PostgreSQL."),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Chemin du fichier de configuration."),
    ] = None,
) -> None:
    """Vérifie la connexion à la base de données."""
    config_path = config_file or Path.cwd() / DEFAULT_CONFIG_FILENAME
    settings = Settings(config_file=config_path)
    if database_url:
        settings.database_url = database_url

    console.print("[bold blue]Vérification de la connexion...[/bold blue]")

    try:
        db = DatabaseManager(settings)

        db.check_connection()
        console.print("[green]✓[/green] Connexion PostgreSQL OK")

        db.check_postgis()
        console.print("[green]✓[/green] Extension PostGIS OK")

        console.print("[bold green]Toutes les vérifications passées ![/bold green]")

    except Exception as e:
        console.print(f"[bold red]✗ Erreur: {e}[/bold red]")
        raise typer.Exit(1) from e


@app.command()
def products(
    category: Annotated[
        str | None,
        typer.Option(
            "--category", "-c", help="Filtrer par catégorie (admin, stats, land, address, carto)."
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Affiche plus de détails."),
    ] = False,
) -> None:
    """Liste les produits IGN disponibles."""
    catalog = get_default_catalog()

    # Filtrage par catégorie si demandé
    if category:
        category_map = {
            "admin": ProductCategory.ADMIN,
            "administrative": ProductCategory.ADMIN,
            "stats": ProductCategory.STATS,
            "statistics": ProductCategory.STATS,
            "land": ProductCategory.LAND,
            "landcover": ProductCategory.LAND,
            "address": ProductCategory.ADDRESS,
            "carto": ProductCategory.CARTO,
            "cartography": ProductCategory.CARTO,
        }
        cat_enum = category_map.get(category.lower())
        if cat_enum:
            products_list = catalog.list_by_category(cat_enum)
        else:
            console.print(f"[red]Catégorie inconnue: {category}[/red]")
            console.print(f"Catégories valides: {', '.join(category_map.keys())}")
            raise typer.Exit(1)
    else:
        products_list = catalog.list_all()

    if not products_list:
        console.print("[yellow]Aucun produit trouvé.[/yellow]")
        return

    table = Table(title="Produits IGN disponibles")
    table.add_column("ID", style="cyan")
    table.add_column("Nom", style="bold")
    table.add_column("Catégorie", style="green")
    table.add_column("Formats")

    if verbose:
        table.add_column("Territoires")
        table.add_column("Description")

    for product in products_list:
        formats_str = ", ".join(f.value for f in product.formats)

        if verbose:
            territories_str = ", ".join(t.value for t in product.territories)
            desc = product.description_fr
            if len(desc) > 50:
                desc = desc[:47] + "..."
            table.add_row(
                product.id,
                product.name,
                product.category.value,
                formats_str,
                territories_str,
                desc,
            )
        else:
            table.add_row(
                product.id,
                product.name,
                product.category.value,
                formats_str,
            )

    console.print(table)


@app.command(name="product-info")
def product_info(
    product_id: Annotated[
        str,
        typer.Argument(help="ID du produit (ex: admin-express-cog, contours-iris)."),
    ],
) -> None:
    """Affiche les détails d'un produit IGN."""
    catalog = get_default_catalog()
    product = catalog.get(product_id)

    if product is None:
        console.print(f"[red]Produit non trouvé: {product_id}[/red]")
        console.print(f"Produits disponibles: {', '.join(catalog.list_ids())}")
        raise typer.Exit(1)

    # Informations générales
    console.print(Panel(f"[bold]{product.name}[/bold]", title="Produit IGN"))

    info_table = Table(show_header=False)
    info_table.add_column("Attribut", style="cyan")
    info_table.add_column("Valeur")

    info_table.add_row("ID", product.id)
    info_table.add_row("Catégorie", product.category.value)
    info_table.add_row("Formats", ", ".join(f.value for f in product.formats))
    info_table.add_row("Territoires", ", ".join(t.value for t in product.territories))
    info_table.add_row("Version", product.version_pattern)

    console.print(info_table)

    # Description
    console.print(f"\n[bold]Description:[/bold]\n{product.description_fr}")

    # Couches disponibles
    console.print("\n[bold]Couches disponibles:[/bold]")

    layers_table = Table()
    layers_table.add_column("Nom", style="cyan")
    layers_table.add_column("Table", style="green")
    layers_table.add_column("Géométrie")
    layers_table.add_column("Description")

    for layer in product.layers:
        optional = " (optionnel)" if layer.optional else ""
        layers_table.add_row(
            layer.name,
            layer.table_key,
            layer.geometry_type.value,
            layer.description_fr + optional,
        )

    console.print(layers_table)


@app.command(name="load-product")
def load_product(
    product_id: Annotated[
        str,
        typer.Argument(help="ID du produit à charger (ex: admin-express-cog, contours-iris)."),
    ],
    file_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Format des données (shp, gpkg)."),
    ] = "shp",
    territory: Annotated[
        str,
        typer.Option("--territory", "-t", help="Territoire (FRA, FXX, GLP, MTQ, GUF, REU, MYT)."),
    ] = "FRA",
    year: Annotated[
        str,
        typer.Option("--year", "-y", help="Année des données."),
    ] = "2024",
    layers: Annotated[
        str | None,
        typer.Option("--layers", "-l", help="Couches à charger (séparées par des virgules)."),
    ] = None,
    database_url: Annotated[
        str | None,
        typer.Option("--database-url", "-d", help="URL de connexion PostgreSQL."),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Chemin du fichier de configuration."),
    ] = None,
    replace: Annotated[
        bool,
        typer.Option("--replace", "-r", help="Remplace les tables existantes."),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Mode verbeux."),
    ] = False,
) -> None:
    """Charge les données d'un produit IGN dans PostgreSQL."""
    setup_logging(verbose)

    # Vérification du produit
    catalog = get_default_catalog()
    product = catalog.get(product_id)

    if product is None:
        console.print(f"[red]Produit non trouvé: {product_id}[/red]")
        console.print(f"Produits disponibles: {', '.join(catalog.list_ids())}")
        raise typer.Exit(1)

    # Configuration
    config_path = config_file or Path.cwd() / DEFAULT_CONFIG_FILENAME
    settings = Settings(config_file=config_path)
    if database_url:
        settings.database_url = database_url

    # Conversion du format
    format_enum = FileFormat.SHP if file_format.lower() == "shp" else FileFormat.GPKG

    # Liste des couches
    layers_list = layers.split(",") if layers else None
    if_exists_lit: Literal["replace", "append", "fail"] = "replace" if replace else "fail"

    console.print(f"[bold blue]Chargement du produit {product.name}...[/bold blue]")
    console.print(f"  Territoire: {territory}")
    console.print(f"  Année: {year}")
    console.print(f"  Format: {file_format}")

    try:
        loader = ProductLoader(
            product=product,
            catalog=catalog,
            settings=settings,
        )

        count = loader.load(
            file_format=format_enum,
            territory=territory,
            year=year,
            layers=layers_list,
            if_exists=if_exists_lit,
        )

        console.print(f"[bold green]Chargement terminé: {count} entités chargées[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Erreur: {e}[/bold red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
