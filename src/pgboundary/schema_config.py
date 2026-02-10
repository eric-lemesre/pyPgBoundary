"""Database schema configuration via YAML file."""

import logging
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = "pgboundary.yml"


class StorageMode(StrEnum):
    """Table storage mode."""

    PREFIX = "prefix"  # Dans le schéma public avec préfixe
    SCHEMA = "schema"  # Dans un schéma dédié


class FieldPrefixes(BaseModel):
    """Field prefixes by type."""

    code: str = Field(default="cd_", description="Préfixe pour les champs de code")
    label: str = Field(default="lb_", description="Préfixe pour les champs de libellé/nom")
    date: str = Field(default="dt_", description="Préfixe pour les champs de date")


class TableNames(BaseModel):
    """Table names.

    This class defines table names for all supported IGN products.
    Tables are organized by product category.
    """

    # Admin Express - Couches de base
    region: str = Field(default="region", description="Table des régions")
    departement: str = Field(default="departement", description="Table des départements")
    arrondissement: str = Field(default="arrondissement", description="Table des arrondissements")
    epci: str = Field(default="epci", description="Table des EPCI")
    commune: str = Field(default="commune", description="Table des communes")
    commune_associee_deleguee: str = Field(
        default="commune_associee_deleguee",
        description="Table des communes associées/déléguées",
    )

    # Admin Express - Couches enrichies (CARTO, PLUS)
    arrondissement_municipal: str = Field(
        default="arrondissement_municipal",
        description="Table des arrondissements municipaux (Paris, Lyon, Marseille)",
    )
    chef_lieu_commune: str = Field(
        default="chef_lieu_commune",
        description="Table des chefs-lieux de commune",
    )
    chef_lieu_arrondissement_municipal: str = Field(
        default="chef_lieu_arrondissement_municipal",
        description="Table des chefs-lieux d'arrondissement municipal",
    )
    canton: str = Field(default="canton", description="Table des cantons")
    collectivite_territoriale: str = Field(
        default="collectivite_territoriale",
        description="Table des collectivités territoriales",
    )

    # Contours IRIS
    iris: str = Field(default="iris", description="Table des contours IRIS")

    # BD FORÊT
    formation_vegetale: str = Field(
        default="formation_vegetale",
        description="Table des formations végétales forestières",
    )
    masque_foret: str = Field(
        default="masque_foret",
        description="Table du masque forestier",
    )

    # BD CARTO
    commune_carto: str = Field(
        default="commune_carto",
        description="Table des communes (BD CARTO)",
    )
    limite_administrative: str = Field(
        default="limite_administrative",
        description="Table des limites administratives linéaires",
    )
    zone_activite: str = Field(
        default="zone_activite",
        description="Table des zones d'activité",
    )
    zone_habitation: str = Field(
        default="zone_habitation",
        description="Table des zones d'habitation",
    )
    aerodrome: str = Field(default="aerodrome", description="Table des aérodromes")
    cimetiere: str = Field(default="cimetiere", description="Table des cimetières")
    construction_surfacique: str = Field(
        default="construction_surfacique",
        description="Table des constructions surfaciques",
    )
    terrain_sport: str = Field(
        default="terrain_sport",
        description="Table des terrains de sport",
    )

    # Adresses
    adresse: str = Field(
        default="adresse",
        description="Table des adresses (ADRESSE PREMIUM)",
    )
    adresse_ban: str = Field(
        default="adresse_ban",
        description="Table des adresses BAN PLUS",
    )

    # BCAE
    bcae: str = Field(default="bcae", description="Table des zones BCAE")
    haie: str = Field(default="haie", description="Table des haies")
    mare: str = Field(default="mare", description="Table des mares")

    # Codes postaux
    code_postal: str = Field(
        default="code_postal",
        description="Table des codes postaux (générés Voronoï)",
    )
    code_postal_ban: str = Field(
        default="code_postal_ban",
        description="Table des codes postaux (contours BAN)",
    )
    code_postal_geoclip: str = Field(
        default="code_postal_geoclip",
        description="Table des codes postaux (Géoclip)",
    )
    correspondance_cp_insee: str = Field(
        default="correspondance_cp_insee",
        description="Table de correspondance codes postaux - INSEE",
    )

    # Circonscriptions électorales
    circonscription_legislative: str = Field(
        default="circonscription_legislative",
        description="Table des circonscriptions législatives",
    )
    bureau_vote: str = Field(
        default="bureau_vote",
        description="Table des bureaux de vote",
    )


class LayerTableOverride(BaseModel):
    """Table name override for a specific layer.

    Attributes:
        table_name: Custom table name for this layer.
    """

    table_name: str = Field(..., description="Nom de table personnalisé")


class ProductTableOverride(BaseModel):
    """Table name override for a product.

    Allows defining a default table name for all layers of a product,
    and/or specific names per layer.

    Attributes:
        default_table: Default table name for all layers of the product.
        layers: Layer-specific overrides (take priority over default_table).
    """

    default_table: str | None = Field(
        default=None,
        description="Nom de table par défaut pour toutes les couches du produit",
    )
    layers: dict[str, LayerTableOverride] = Field(
        default_factory=dict,
        description="Overrides spécifiques par nom de couche",
    )

    def get_table_name(self, layer_name: str) -> str | None:
        """Return the table name for a layer.

        Priority is: layer override > default_table > None.

        Args:
            layer_name: Layer name.

        Returns:
            Custom table name or None.
        """
        if layer_name in self.layers:
            return self.layers[layer_name].table_name
        return self.default_table


class TableOverrides(BaseModel):
    """Table name override configuration by product.

    Allows redirecting data from a product or layer to a specific table.

    Attributes:
        products: Dictionary of overrides by product ID.
    """

    products: dict[str, ProductTableOverride] = Field(
        default_factory=dict,
        description="Overrides par ID de produit",
    )

    def get_table_name(self, product_id: str, layer_name: str) -> str | None:
        """Return the table name for a product/layer.

        Args:
            product_id: Product identifier.
            layer_name: Layer name.

        Returns:
            Custom table name or None if no override.
        """
        if product_id not in self.products:
            return None
        return self.products[product_id].get_table_name(layer_name)

    def get_products_for_table(self, table_name: str) -> list[str]:
        """Return the products that use a given table.

        Useful for determining if type_produit is needed.

        Args:
            table_name: Table name.

        Returns:
            List of product IDs using this table.
        """
        result = []
        for product_id, override in self.products.items():
            if override.default_table == table_name:
                result.append(product_id)
            for layer_override in override.layers.values():
                if layer_override.table_name == table_name and product_id not in result:
                    result.append(product_id)
        return result


class StorageConfig(BaseModel):
    """Storage mode configuration."""

    mode: StorageMode = Field(
        default=StorageMode.SCHEMA,
        description="Mode de stockage: 'prefix' (public avec préfixe) ou 'schema' (schéma dédié)",
    )
    schema_name: str = Field(
        default="geo",
        description="Nom du schéma (si mode='schema')",
    )
    table_prefix: str = Field(
        default="geo_",
        description="Préfixe des tables (si mode='prefix')",
    )


class SchemaConfig(BaseModel):
    """Complete database schema configuration."""

    storage: StorageConfig = Field(default_factory=StorageConfig)
    field_prefixes: FieldPrefixes = Field(default_factory=FieldPrefixes)
    table_names: TableNames = Field(default_factory=TableNames)
    table_overrides: TableOverrides = Field(default_factory=TableOverrides)
    srid: int = Field(default=4326, description="SRID des géométries (WGS84 par défaut)")
    imports: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Configuration des imports par produit",
    )

    @field_validator("imports", mode="before")
    @classmethod
    def validate_imports(cls, v: Any) -> dict[str, dict[str, Any]]:
        """Validate the imports field, convert None to empty dict."""
        if v is None:
            return {}
        return dict(v)

    def get_full_table_name(
        self,
        table_key: str,
        *,
        product_id: str | None = None,
        layer_name: str | None = None,
        cli_table_name: str | None = None,
    ) -> str:
        """Return the full table name according to the storage mode.

        Table name resolution priority:
        1. CLI parameter (cli_table_name)
        2. Layer override (table_overrides.products[product_id].layers[layer_name])
        3. Product override (table_overrides.products[product_id].default_table)
        4. Default table name (table_names)

        Args:
            table_key: Table key (region, departement, etc.)
            product_id: Product identifier (optional).
            layer_name: Layer name (optional).
            cli_table_name: Table name specified via CLI (takes priority).

        Returns:
            Full table name.
        """
        # 1. Priorité au CLI
        if cli_table_name:
            base_name = cli_table_name
        # 2 & 3. Vérifier les overrides (couche puis produit)
        elif product_id and layer_name:
            override = self.table_overrides.get_table_name(product_id, layer_name)
            base_name = override if override else getattr(self.table_names, table_key)
        # 4. Nom par défaut
        else:
            base_name = getattr(self.table_names, table_key)

        if self.storage.mode == StorageMode.PREFIX:
            return f"{self.storage.table_prefix}{base_name}"
        return base_name

    def needs_type_produit(
        self,
        table_name: str,
        product_id: str,
    ) -> bool:
        """Determine if the type_produit column is needed.

        The column is added when multiple products share the same table.

        Args:
            table_name: Table name.
            product_id: Current product ID.

        Returns:
            True if type_produit is needed.
        """
        products_using_table = self.table_overrides.get_products_for_table(table_name)
        # Ajouter le produit courant s'il n'est pas dans les overrides
        if product_id not in products_using_table:
            products_using_table.append(product_id)
        return len(products_using_table) > 1

    def get_schema_name(self) -> str | None:
        """Return the schema name or None if in prefix mode.

        Returns:
            Schema name or None.
        """
        if self.storage.mode == StorageMode.SCHEMA:
            return self.storage.schema_name
        return None

    def get_column_name(self, field_type: Literal["code", "label", "date"], name: str) -> str:
        """Return the column name with the appropriate prefix.

        Args:
            field_type: Field type (code, label, date).
            name: Base field name.

        Returns:
            Prefixed column name.
        """
        prefix = getattr(self.field_prefixes, field_type)
        return f"{prefix}{name}"

    def get_import_config(self, product_id: str) -> dict[str, Any] | None:
        """Return the import configuration for a product.

        Args:
            product_id: Product identifier.

        Returns:
            Import configuration or None.
        """
        return self.imports.get(product_id)

    def get_enabled_imports(self) -> dict[str, dict[str, Any]]:
        """Return imports with at least one enabled layer.

        Returns:
            Dictionary of imports with at least one layer where enabled=True.
        """
        result = {}
        for k, v in self.imports.items():
            layers = v.get("layers", {})
            # Si layers est un dict, vérifier si au moins une couche est activée
            if isinstance(layers, dict):
                if any(layer.get("enabled", True) for layer in layers.values()):
                    result[k] = v
            # Si layers est une liste (ancienne structure), considérer comme activé
            elif isinstance(layers, list):
                result[k] = v
        return result

    def count_imports(self) -> tuple[int, int]:
        """Count imports (with enabled layers, total).

        Returns:
            Tuple (number with enabled layers, total number).
        """
        total = len(self.imports)
        enabled = len(self.get_enabled_imports())
        return enabled, total

    def update_injection_status(
        self,
        product_id: str,
        *,
        injected: bool,
        count: int | None = None,
        edition: str | None = None,
        layers: list[str] | None = None,
    ) -> None:
        """Update the injection status of a product.

        Args:
            product_id: Product identifier.
            injected: True if the product was injected.
            count: Number of injected entities.
            edition: Injected data edition.
            layers: Injected layers.
        """
        if product_id not in self.imports:
            return

        injection_info: dict[str, Any] = {
            "injected": injected,
            "injected_at": datetime.now().isoformat() if injected else None,
        }

        if injected:
            if count is not None:
                injection_info["entity_count"] = count
            if edition is not None:
                injection_info["injected_edition"] = edition
            if layers is not None:
                injection_info["injected_layers"] = layers

        self.imports[product_id]["injection"] = injection_info

    def get_injection_status(self, product_id: str) -> dict[str, Any] | None:
        """Return the injection status of a product.

        Args:
            product_id: Product identifier.

        Returns:
            Dictionary with injection information or None.
        """
        if product_id not in self.imports:
            return None
        return self.imports[product_id].get("injection")

    def get_injected_products(self) -> dict[str, dict[str, Any]]:
        """Return the products that have been injected.

        Returns:
            Dictionary of injected products with their information.
        """
        return {
            k: v for k, v in self.imports.items() if v.get("injection", {}).get("injected", False)
        }


def get_default_config() -> SchemaConfig:
    """Return the default configuration.

    Returns:
        Default configuration.
    """
    return SchemaConfig()


def get_default_yaml() -> str:
    """Generate the default YAML content with comments.

    Returns:
        Formatted YAML content.
    """
    return """# Configuration pyPgBoundary - Schéma de base de données
# Ce fichier est créé automatiquement avec les valeurs par défaut

# Mode de stockage des tables
storage:
  # Mode: 'prefix' (tables dans public avec préfixe) ou 'schema' (schéma dédié)
  mode: schema

  # Nom du schéma PostgreSQL (utilisé si mode = 'schema')
  schema_name: geo

  # Préfixe des tables (utilisé si mode = 'prefix')
  table_prefix: geo_

# Préfixes des colonnes selon leur type
field_prefixes:
  # Champs de code (ex: cd_insee, cd_postal)
  code: cd_

  # Champs de libellé/nom (ex: lb_nom, lb_region)
  label: lb_

  # Champs de date (ex: dt_creation, dt_modification)
  date: dt_

# Noms des tables (sans préfixe, celui-ci est ajouté automatiquement si mode='prefix')
table_names:
  region: region
  departement: departement
  epci: epci
  commune: commune
  commune_associee_deleguee: commune_associee_deleguee

# Overrides de noms de tables par produit/couche
# Permet de rediriger les données vers des tables personnalisées
# Priorité: CLI --table-name > override couche > override produit > table_names
table_overrides:
  products: {}
  # Exemple: rediriger admin-express-cog vers des tables personnalisées
  # products:
  #   admin-express-cog:
  #     default_table: null  # Nom de table par défaut pour toutes les couches
  #     layers:
  #       COMMUNE:
  #         table_name: commune_admin_express
  #       REGION:
  #         table_name: region_admin_express
  #
  # Exemple: plusieurs produits partageant la même table (type_produit ajouté automatiquement)
  #   admin-express-cog:
  #     layers:
  #       COMMUNE:
  #         table_name: commune_unified
  #   admin-express-cog-carto:
  #     layers:
  #       COMMUNE:
  #         table_name: commune_unified

# SRID des géométries (4326 = WGS84, standard international)
srid: 4326

# Configuration des imports de produits
# Utilisez 'pgboundary config data add' pour ajouter des produits
imports:
  # Exemple de configuration Admin Express COG
  # admin-express-cog:
  #   # Valeurs par défaut pour toutes les couches
  #   territory: FRA
  #   format: shp
  #   editions: ["2024"]
  #   historization:
  #     enabled: true
  #     method: combined   # md5 | jaccard | hausdorff | combined
  #     thresholds:
  #       identical_min: 0.95
  #       likely_match_min: 0.80
  #       suspect_min: 0.50
  #       hausdorff_max: 10.0
  #     key_field: cd_insee
  #
  #   # Configuration par couche (enabled au niveau couche uniquement)
  #   layers:
  #     REGION:
  #       enabled: true
  #       table_name: region
  #     DEPARTEMENT:
  #       enabled: true
  #       table_name: departement
  #     COMMUNE:
  #       enabled: true
  #       table_name: commune
  #       editions: ["2023", "2024"]  # Surcharge locale
  #     EPCI:
  #       enabled: false
  #       table_name: epci
  #
  #   injection:           # Statut d'injection (géré automatiquement)
  #     injected: true
  #     injected_at: "2024-01-15T10:30:00"
  #     entity_count: 34500
  #     injected_edition: "2024"
  #     injected_layers: [REGION, DEPARTEMENT, COMMUNE]
"""


def load_config(config_path: Path | None = None) -> SchemaConfig:
    """Load the configuration from a YAML file.

    If the file does not exist, it is created with default values.

    Args:
        config_path: Path to the configuration file.
                    If None, uses the current directory.

    Returns:
        Loaded configuration.
    """
    if config_path is None:
        config_path = Path.cwd() / DEFAULT_CONFIG_FILENAME

    if not config_path.exists():
        logger.info("Fichier de configuration inexistant, création: %s", config_path)
        create_default_config(config_path)

    logger.debug("Chargement de la configuration: %s", config_path)

    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        return get_default_config()

    return SchemaConfig.model_validate(data)


def create_default_config(config_path: Path) -> None:
    """Create the default configuration file.

    Args:
        config_path: Path where the file will be created.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("w", encoding="utf-8") as f:
        f.write(get_default_yaml())

    logger.info("Fichier de configuration créé: %s", config_path)


def save_config(config: SchemaConfig, config_path: Path) -> None:
    """Save the configuration to a YAML file.

    Args:
        config: Configuration to save.
        config_path: File path.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # mode="json" convertit les enums en leurs valeurs string
    data = config.model_dump(mode="json")

    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Configuration sauvegardée: %s", config_path)
