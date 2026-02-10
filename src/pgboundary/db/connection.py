"""PostgreSQL/PostGIS database connection management."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from pgboundary.config import Settings
from pgboundary.db.models import TableFactory
from pgboundary.exceptions import ConnectionError, DatabaseNotFoundError, SchemaError

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Connection manager for the PostgreSQL/PostGIS database."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the database manager.

        Args:
            settings: Module configuration. Uses default values if not provided.
        """
        self.settings = settings or Settings()
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None
        self._table_factory: TableFactory | None = None

    @property
    def engine(self) -> "Engine":
        """Return the SQLAlchemy engine, creating it if necessary."""
        if self._engine is None:
            self._engine = create_engine(
                str(self.settings.database_url),
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
        return self._engine

    @property
    def session_factory(self) -> sessionmaker[Session]:
        """Return the session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        return self._session_factory

    @property
    def table_factory(self) -> TableFactory:
        """Return the table factory."""
        if self._table_factory is None:
            self._table_factory = TableFactory(self.settings.schema_config)
        return self._table_factory

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Context manager for database sessions.

        Yields:
            SQLAlchemy Session.

        Raises:
            ConnectionError: If a connection error occurs.
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.exception("Erreur lors de la transaction")
            raise ConnectionError(f"Erreur de transaction: {e}") from e
        finally:
            session.close()

    def check_connection(self) -> bool:
        """Check the database connection.

        Returns:
            True if the connection is established.

        Raises:
            DatabaseNotFoundError: If the database does not exist.
            ConnectionError: If the connection fails for another reason.
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Connexion à la base de données établie")
            return True
        except Exception as e:
            error_msg = str(e).lower()
            # Détection des erreurs "database does not exist"
            if "does not exist" in error_msg or "n'existe pas" in error_msg:
                db_name = self._get_database_name()
                raise DatabaseNotFoundError(f"La base de données '{db_name}' n'existe pas") from e
            raise ConnectionError(f"Impossible de se connecter à la base de données: {e}") from e

    def _get_database_name(self) -> str:
        """Extract the database name from the URL.

        Returns:
            Database name.
        """
        from urllib.parse import urlparse

        parsed = urlparse(str(self.settings.database_url))
        return parsed.path.lstrip("/") or "unknown"

    def _get_admin_url(self) -> str:
        """Return the connection URL to the postgres (admin) database.

        Returns:
            Connection URL to the postgres database.
        """
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(str(self.settings.database_url))
        # Remplacer le nom de la base par 'postgres'
        admin_parsed = parsed._replace(path="/postgres")
        return urlunparse(admin_parsed)

    def database_exists(self) -> bool:
        """Check if the database exists.

        Returns:
            True if the database exists, False otherwise.
        """
        db_name = self._get_database_name()
        admin_url = self._get_admin_url()

        try:
            admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
            with admin_engine.connect() as conn:
                result = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                    {"dbname": db_name},
                )
                exists = result.scalar() is not None
            admin_engine.dispose()
            return exists
        except Exception as e:
            logger.warning("Impossible de vérifier l'existence de la base: %s", e)
            return False

    def create_database(self) -> None:
        """Create the database.

        Raises:
            SchemaError: If the creation fails.
        """
        db_name = self._get_database_name()
        admin_url = self._get_admin_url()

        try:
            admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
            with admin_engine.connect() as conn:
                # Vérifier que la base n'existe pas déjà
                result = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                    {"dbname": db_name},
                )
                if result.scalar() is not None:
                    logger.info("La base de données '%s' existe déjà", db_name)
                    admin_engine.dispose()
                    return

                # Créer la base de données
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info("Base de données '%s' créée", db_name)

            admin_engine.dispose()
        except Exception as e:
            raise SchemaError(f"Impossible de créer la base de données '{db_name}': {e}") from e

    def ensure_extensions(self) -> None:
        """Create required PostgreSQL extensions if they don't exist.

        Creates the PostGIS and pgcrypto extensions.

        Raises:
            SchemaError: If the extension creation fails.
        """
        extensions = ["postgis", "pgcrypto"]

        try:
            with self.engine.connect() as conn:
                for ext in extensions:
                    conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
                    logger.info("Extension '%s' disponible", ext)
                conn.commit()
        except Exception as e:
            raise SchemaError(f"Impossible de créer les extensions: {e}") from e

    def check_postgis(self) -> bool:
        """Check that the PostGIS extension is available.

        Returns:
            True if PostGIS is installed.

        Raises:
            SchemaError: If PostGIS is not available.
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT PostGIS_Version()"))
                version = result.scalar()
                logger.info("PostGIS version: %s", version)
            return True
        except Exception as e:
            raise SchemaError(f"PostGIS n'est pas disponible: {e}") from e

    def create_schema(self) -> None:
        """Create the PostgreSQL schema for data (if schema mode).

        Raises:
            SchemaError: If a creation error occurs.
        """
        schema_name = self.settings.schema_name
        if schema_name is None:
            logger.info("Mode prefix: utilisation du schéma public")
            return

        try:
            with self.engine.connect() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
                conn.commit()
            logger.info("Schéma '%s' créé ou existant", schema_name)
        except Exception as e:
            raise SchemaError(f"Erreur lors de la création du schéma: {e}") from e

    def create_tables(self) -> None:
        """Create tables in the database.

        Raises:
            SchemaError: If a creation error occurs.
        """
        try:
            self.table_factory.get_all_tables()
            self.table_factory.metadata.create_all(self.engine)
            logger.info("Tables créées avec succès")
        except Exception as e:
            raise SchemaError(f"Erreur lors de la création des tables: {e}") from e

    def drop_tables(self) -> None:
        """Drop tables from the database.

        Raises:
            SchemaError: If a deletion error occurs.
        """
        try:
            self.table_factory.get_all_tables()
            self.table_factory.metadata.drop_all(self.engine)
            logger.info("Tables supprimées")
        except Exception as e:
            raise SchemaError(f"Erreur lors de la suppression des tables: {e}") from e

    def init_database(self) -> None:
        """Fully initialize the database.

        Checks the connection, creates extensions, schema, and tables.
        """
        self.check_connection()
        self.ensure_extensions()
        self.check_postgis()
        self.create_schema()
        self.create_tables()
        logger.info("Base de données initialisée avec succès")

    def close(self) -> None:
        """Close database connections."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._table_factory = None
            logger.info("Connexions fermées")
