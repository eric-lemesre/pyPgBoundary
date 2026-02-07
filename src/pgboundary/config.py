"""Configuration du module pyPgBoundary."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pgboundary.schema_config import (
    DEFAULT_CONFIG_FILENAME,
    SchemaConfig,
    load_config,
)


class Settings(BaseSettings):
    """Configuration globale du module.

    Les paramètres peuvent être définis via des variables d'environnement
    préfixées par PGBOUNDARY_.
    """

    model_config = SettingsConfigDict(
        env_prefix="PGBOUNDARY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/boundaries",
        description="URL de connexion PostgreSQL",
    )

    config_file: Path = Field(
        default=Path.cwd() / DEFAULT_CONFIG_FILENAME,
        description="Chemin vers le fichier de configuration YAML",
    )

    data_dir: Path = Field(
        default=Path.home() / ".pgboundary" / "data",
        description="Répertoire de stockage des données téléchargées",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Niveau de journalisation",
    )

    admin_express_version: str = Field(
        default="latest",
        description="Version d'Admin Express à utiliser",
    )

    _schema_config: SchemaConfig | None = None

    @field_validator("data_dir", "config_file", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        """Convertit la valeur en Path si nécessaire."""
        return Path(v) if isinstance(v, str) else v

    @property
    def schema_config(self) -> SchemaConfig:
        """Charge et retourne la configuration du schéma.

        La configuration est mise en cache après le premier chargement.
        """
        if self._schema_config is None:
            self._schema_config = load_config(self.config_file)
        return self._schema_config

    @property
    def schema_name(self) -> str | None:
        """Retourne le nom du schéma selon la configuration."""
        return self.schema_config.get_schema_name()

    @property
    def srid(self) -> int:
        """Retourne le SRID configuré."""
        return self.schema_config.srid

    def ensure_data_dir(self) -> Path:
        """Crée le répertoire de données s'il n'existe pas."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    def reload_schema_config(self) -> SchemaConfig:
        """Force le rechargement de la configuration du schéma."""
        self._schema_config = load_config(self.config_file)
        return self._schema_config
