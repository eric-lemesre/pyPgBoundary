"""pgBoundary module configuration."""

import logging
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pgboundary.schema_config import (
    DEFAULT_CONFIG_FILENAME,
    SchemaConfig,
    load_config,
)

logger = logging.getLogger(__name__)

ENV_FILE = Path.cwd() / ".env"
ENV_VAR_DATABASE_URL = "PGBOUNDARY_DATABASE_URL"
ENV_VAR_DATA_DIR = "PGBOUNDARY_DATA_DIR"


class Settings(BaseSettings):
    """Global module configuration.

    Settings can be defined via environment variables prefixed with
    PGBOUNDARY_.
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

    catalog_db: Path = Field(
        default=Path.home() / ".pgboundary" / "catalog.db",
        description="Base SQLite du catalogue API",
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

    @field_validator("data_dir", "config_file", "catalog_db", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        """Convert the value to Path if necessary."""
        return Path(v) if isinstance(v, str) else v

    @property
    def schema_config(self) -> SchemaConfig:
        """Load and return the schema configuration.

        The configuration is cached after the first load.
        """
        if self._schema_config is None:
            self._schema_config = load_config(self.config_file)
        return self._schema_config

    @property
    def schema_name(self) -> str | None:
        """Return the schema name from the configuration."""
        return self.schema_config.get_schema_name()

    @property
    def srid(self) -> int:
        """Return the configured SRID."""
        return self.schema_config.srid

    def ensure_data_dir(self) -> Path:
        """Create the data directory if it does not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    def reload_schema_config(self) -> SchemaConfig:
        """Force reload of the schema configuration."""
        self._schema_config = load_config(self.config_file)
        return self._schema_config


def has_database_url_configured(env_file: Path | None = None) -> bool:
    """Check if a database URL is configured.

    Checks in order:
    1. PGBOUNDARY_DATABASE_URL environment variable
    2. .env file

    Args:
        env_file: Path to the .env file (default: ./.env)

    Returns:
        True if a URL is configured, False otherwise.
    """
    # Vérifier la variable d'environnement
    if os.environ.get(ENV_VAR_DATABASE_URL):
        return True

    # Vérifier le fichier .env
    env_path = env_file or ENV_FILE
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        # Chercher une ligne non commentée avec DATABASE_URL
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line.startswith(f"{ENV_VAR_DATABASE_URL}="):
                return True

    return False


def build_database_url(
    host: str = "localhost",
    port: int = 5432,
    database: str = "boundaries",
    user: str = "postgres",
    password: str = "",
) -> str:
    """Build a PostgreSQL connection URL.

    Args:
        host: PostgreSQL host.
        port: PostgreSQL port.
        database: Database name.
        user: Username.
        password: Password.

    Returns:
        PostgreSQL connection URL.
    """
    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    return f"postgresql://{user}@{host}:{port}/{database}"


def save_database_url_to_env(
    database_url: str,
    env_file: Path | None = None,
) -> None:
    """Save the database URL to the .env file.

    If the file exists, updates the PGBOUNDARY_DATABASE_URL line.
    Otherwise, creates the file with the URL.

    Args:
        database_url: PostgreSQL connection URL.
        env_file: Path to the .env file (default: ./.env)
    """
    env_path = env_file or ENV_FILE
    env_line = f"{ENV_VAR_DATABASE_URL}={database_url}"

    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        updated = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Remplacer la ligne existante (commentée ou non)
            if stripped.startswith(f"{ENV_VAR_DATABASE_URL}=") or stripped.startswith(
                f"# {ENV_VAR_DATABASE_URL}="
            ):
                lines[i] = env_line
                updated = True
                break

        if not updated:
            # Ajouter à la fin si non trouvé
            lines.append(env_line)

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        # Créer le fichier avec un en-tête
        content = f"""# Configuration pgBoundary
# Généré automatiquement

# URL de connexion PostgreSQL
{env_line}

# Niveau de journalisation (DEBUG, INFO, WARNING, ERROR)
PGBOUNDARY_LOG_LEVEL=INFO
"""
        env_path.write_text(content, encoding="utf-8")

    logger.info("Configuration sauvegardée dans: %s", env_path)


def save_data_dir_to_env(
    data_dir: str,
    env_file: Path | None = None,
) -> None:
    """Save the data directory to the .env file.

    If the file exists, updates the PGBOUNDARY_DATA_DIR line.
    Otherwise, appends the variable at the end of the file.

    Args:
        data_dir: Path to the data directory.
        env_file: Path to the .env file (default: ./.env)
    """
    env_path = env_file or ENV_FILE
    env_line = f"{ENV_VAR_DATA_DIR}={data_dir}"

    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        updated = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{ENV_VAR_DATA_DIR}=") or stripped.startswith(
                f"# {ENV_VAR_DATA_DIR}="
            ):
                lines[i] = env_line
                updated = True
                break

        if not updated:
            # Ajouter avec un commentaire
            lines.append("")
            lines.append("# Répertoire de stockage des données téléchargées")
            lines.append(env_line)

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        logger.warning("Fichier .env non trouvé: %s", env_path)
        return

    logger.info("Répertoire de données sauvegardé dans: %s", env_path)


def parse_database_url(url: str) -> dict[str, str | int]:
    """Parse a PostgreSQL connection URL.

    Args:
        url: PostgreSQL connection URL.

    Returns:
        Dictionary with host, port, database, user, password.
    """
    # Pattern pour parser postgresql://user:pass@host:port/database
    pattern = r"postgresql://(?:([^:]+)(?::([^@]*))?@)?([^:/]+)(?::(\d+))?/(.+)"
    match = re.match(pattern, url)

    if match:
        return {
            "user": match.group(1) or "postgres",
            "password": match.group(2) or "",
            "host": match.group(3) or "localhost",
            "port": int(match.group(4) or 5432),
            "database": match.group(5) or "boundaries",
        }

    # Valeurs par défaut si le parsing échoue
    return {
        "user": "postgres",
        "password": "",
        "host": "localhost",
        "port": 5432,
        "database": "boundaries",
    }
