"""Configuration du schéma de base de données via fichier YAML."""

import logging
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = "pgboundary.yml"


class StorageMode(StrEnum):
    """Mode de stockage des tables."""

    PREFIX = "prefix"  # Dans le schéma public avec préfixe
    SCHEMA = "schema"  # Dans un schéma dédié


class FieldPrefixes(BaseModel):
    """Préfixes des champs selon leur type."""

    code: str = Field(default="cd_", description="Préfixe pour les champs de code")
    label: str = Field(default="lb_", description="Préfixe pour les champs de libellé/nom")
    date: str = Field(default="dt_", description="Préfixe pour les champs de date")


class TableNames(BaseModel):
    """Noms des tables.

    Cette classe définit les noms de tables pour tous les produits IGN supportés.
    Les tables sont organisées par catégorie de produit.
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


class StorageConfig(BaseModel):
    """Configuration du mode de stockage."""

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
    """Configuration complète du schéma de base de données."""

    storage: StorageConfig = Field(default_factory=StorageConfig)
    field_prefixes: FieldPrefixes = Field(default_factory=FieldPrefixes)
    table_names: TableNames = Field(default_factory=TableNames)
    srid: int = Field(default=4326, description="SRID des géométries (WGS84 par défaut)")
    imports: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Configuration des imports par produit",
    )

    def get_full_table_name(self, table_key: str) -> str:
        """Retourne le nom complet de la table selon le mode de stockage.

        Args:
            table_key: Clé de la table (region, departement, etc.)

        Returns:
            Nom complet de la table.
        """
        base_name: str = getattr(self.table_names, table_key)

        if self.storage.mode == StorageMode.PREFIX:
            return f"{self.storage.table_prefix}{base_name}"
        return base_name

    def get_schema_name(self) -> str | None:
        """Retourne le nom du schéma ou None si mode prefix.

        Returns:
            Nom du schéma ou None.
        """
        if self.storage.mode == StorageMode.SCHEMA:
            return self.storage.schema_name
        return None

    def get_column_name(self, field_type: Literal["code", "label", "date"], name: str) -> str:
        """Retourne le nom de colonne avec le préfixe approprié.

        Args:
            field_type: Type de champ (code, label, date).
            name: Nom de base du champ.

        Returns:
            Nom de colonne préfixé.
        """
        prefix = getattr(self.field_prefixes, field_type)
        return f"{prefix}{name}"

    def get_import_config(self, product_id: str) -> dict[str, Any] | None:
        """Retourne la configuration d'import pour un produit.

        Args:
            product_id: Identifiant du produit.

        Returns:
            Configuration d'import ou None.
        """
        return self.imports.get(product_id)

    def get_enabled_imports(self) -> dict[str, dict[str, Any]]:
        """Retourne les imports activés.

        Returns:
            Dictionnaire des imports avec enabled=True.
        """
        return {k: v for k, v in self.imports.items() if v.get("enabled", True)}

    def count_imports(self) -> tuple[int, int]:
        """Compte les imports (activés, total).

        Returns:
            Tuple (nombre activés, nombre total).
        """
        total = len(self.imports)
        enabled = sum(1 for v in self.imports.values() if v.get("enabled", True))
        return enabled, total

    def update_injection_status(
        self,
        product_id: str,
        *,
        injected: bool,
        count: int | None = None,
        year: str | None = None,
        layers: list[str] | None = None,
    ) -> None:
        """Met à jour le statut d'injection d'un produit.

        Args:
            product_id: Identifiant du produit.
            injected: True si le produit a été injecté.
            count: Nombre d'entités injectées.
            year: Millésime injecté.
            layers: Couches injectées.
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
            if year is not None:
                injection_info["injected_year"] = year
            if layers is not None:
                injection_info["injected_layers"] = layers

        self.imports[product_id]["injection"] = injection_info

    def get_injection_status(self, product_id: str) -> dict[str, Any] | None:
        """Retourne le statut d'injection d'un produit.

        Args:
            product_id: Identifiant du produit.

        Returns:
            Dictionnaire avec les informations d'injection ou None.
        """
        if product_id not in self.imports:
            return None
        return self.imports[product_id].get("injection")

    def get_injected_products(self) -> dict[str, dict[str, Any]]:
        """Retourne les produits qui ont été injectés.

        Returns:
            Dictionnaire des produits injectés avec leurs informations.
        """
        return {
            k: v for k, v in self.imports.items() if v.get("injection", {}).get("injected", False)
        }


def get_default_config() -> SchemaConfig:
    """Retourne la configuration par défaut.

    Returns:
        Configuration par défaut.
    """
    return SchemaConfig()


def get_default_yaml() -> str:
    """Génère le contenu YAML par défaut avec commentaires.

    Returns:
        Contenu YAML formaté.
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

# SRID des géométries (4326 = WGS84, standard international)
srid: 4326

# Configuration des imports de produits
# Utilisez 'pgboundary config data add' pour ajouter des produits
imports:
  # Exemple de configuration Admin Express COG
  # admin-express-cog:
  #   enabled: true
  #   layers: [REGION, DEPARTEMENT, EPCI, COMMUNE]
  #   territory: FRA
  #   format: shp
  #   years: ["2024"]
  #   historization:
  #     enabled: true
  #     method: jaccard    # md5 | jaccard | hausdorff
  #     threshold: 0.95    # ratio pour jaccard, mètres pour hausdorff
  #     key_field: cd_insee
  #   injection:           # Statut d'injection (géré automatiquement)
  #     injected: true
  #     injected_at: "2024-01-15T10:30:00"
  #     entity_count: 34500
  #     injected_year: "2024"
  #     injected_layers: [REGION, DEPARTEMENT, COMMUNE]
"""


def load_config(config_path: Path | None = None) -> SchemaConfig:
    """Charge la configuration depuis un fichier YAML.

    Si le fichier n'existe pas, il est créé avec les valeurs par défaut.

    Args:
        config_path: Chemin vers le fichier de configuration.
                    Si None, utilise le répertoire courant.

    Returns:
        Configuration chargée.
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
    """Crée le fichier de configuration par défaut.

    Args:
        config_path: Chemin où créer le fichier.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("w", encoding="utf-8") as f:
        f.write(get_default_yaml())

    logger.info("Fichier de configuration créé: %s", config_path)


def save_config(config: SchemaConfig, config_path: Path) -> None:
    """Sauvegarde la configuration dans un fichier YAML.

    Args:
        config: Configuration à sauvegarder.
        config_path: Chemin du fichier.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # mode="json" convertit les enums en leurs valeurs string
    data = config.model_dump(mode="json")

    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Configuration sauvegardée: %s", config_path)
