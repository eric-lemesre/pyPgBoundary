"""Tests pour le module db/connection.

Ce module teste le DatabaseManager et la gestion de connexion PostgreSQL/PostGIS.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pgboundary.config import Settings
from pgboundary.db.connection import DatabaseManager
from pgboundary.exceptions import ConnectionError, SchemaError


class TestDatabaseManagerInit:
    """Tests pour l'initialisation du DatabaseManager."""

    def test_init_with_settings(self, settings: Settings) -> None:
        """Test initialisation avec Settings fourni."""
        manager = DatabaseManager(settings=settings)
        assert manager.settings == settings
        assert manager._engine is None
        assert manager._session_factory is None
        assert manager._table_factory is None

    def test_init_without_settings(self) -> None:
        """Test initialisation sans Settings (utilise les défauts)."""
        with patch.object(Settings, "__init__", return_value=None):
            # On mock l'init de Settings pour éviter l'erreur de validation
            manager = DatabaseManager()
            assert manager._engine is None


class TestDatabaseManagerEngine:
    """Tests pour la propriété engine."""

    def test_engine_created_lazily(self, settings: Settings) -> None:
        """Test que l'engine est créé paresseusement."""
        manager = DatabaseManager(settings=settings)
        assert manager._engine is None

        with patch("pgboundary.db.connection.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            engine = manager.engine

            assert engine == mock_engine
            mock_create.assert_called_once()

    def test_engine_cached(self, settings: Settings) -> None:
        """Test que l'engine est mis en cache."""
        manager = DatabaseManager(settings=settings)

        with patch("pgboundary.db.connection.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            engine1 = manager.engine
            engine2 = manager.engine

            assert engine1 is engine2
            mock_create.assert_called_once()


class TestDatabaseManagerSessionFactory:
    """Tests pour la propriété session_factory."""

    def test_session_factory_created_lazily(self, settings: Settings) -> None:
        """Test que la session_factory est créée paresseusement."""
        manager = DatabaseManager(settings=settings)

        with (
            patch("pgboundary.db.connection.create_engine") as mock_create_engine,
            patch("pgboundary.db.connection.sessionmaker") as mock_sessionmaker,
        ):
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine
            mock_factory = MagicMock()
            mock_sessionmaker.return_value = mock_factory

            factory = manager.session_factory

            assert factory == mock_factory
            mock_sessionmaker.assert_called_once()

    def test_session_factory_cached(self, settings: Settings) -> None:
        """Test que la session_factory est mise en cache."""
        manager = DatabaseManager(settings=settings)

        with (
            patch("pgboundary.db.connection.create_engine"),
            patch("pgboundary.db.connection.sessionmaker") as mock_sessionmaker,
        ):
            mock_factory = MagicMock()
            mock_sessionmaker.return_value = mock_factory

            factory1 = manager.session_factory
            factory2 = manager.session_factory

            assert factory1 is factory2
            mock_sessionmaker.assert_called_once()


class TestDatabaseManagerTableFactory:
    """Tests pour la propriété table_factory."""

    def test_table_factory_created_lazily(self, settings: Settings) -> None:
        """Test que la table_factory est créée paresseusement."""
        manager = DatabaseManager(settings=settings)

        with patch("pgboundary.db.connection.TableFactory") as mock_table_factory:
            mock_factory = MagicMock()
            mock_table_factory.return_value = mock_factory

            factory = manager.table_factory

            assert factory == mock_factory
            mock_table_factory.assert_called_once()


class TestDatabaseManagerSession:
    """Tests pour le context manager session."""

    def test_session_success(self, settings: Settings) -> None:
        """Test session avec succès (commit)."""
        manager = DatabaseManager(settings=settings)
        mock_session = MagicMock()

        with (
            patch("pgboundary.db.connection.create_engine"),
            patch("pgboundary.db.connection.sessionmaker") as mock_sessionmaker,
        ):
            mock_factory = MagicMock(return_value=mock_session)
            mock_sessionmaker.return_value = mock_factory

            with manager.session() as session:
                assert session == mock_session

            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_session_rollback_on_error(self, settings: Settings) -> None:
        """Test session avec rollback sur erreur."""
        manager = DatabaseManager(settings=settings)
        mock_session = MagicMock()

        with (
            patch("pgboundary.db.connection.create_engine"),
            patch("pgboundary.db.connection.sessionmaker") as mock_sessionmaker,
        ):
            mock_factory = MagicMock(return_value=mock_session)
            mock_sessionmaker.return_value = mock_factory

            with pytest.raises(ConnectionError), manager.session():
                raise ValueError("Test error")

            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
            mock_session.commit.assert_not_called()


class TestDatabaseManagerCheckConnection:
    """Tests pour check_connection."""

    def test_check_connection_success(self, settings: Settings) -> None:
        """Test vérification de connexion réussie."""
        manager = DatabaseManager(settings=settings)

        with patch("pgboundary.db.connection.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_create.return_value = mock_engine

            result = manager.check_connection()

            assert result is True
            mock_conn.execute.assert_called_once()

    def test_check_connection_failure(self, settings: Settings) -> None:
        """Test échec de vérification de connexion."""
        manager = DatabaseManager(settings=settings)

        with patch("pgboundary.db.connection.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_engine.connect.side_effect = Exception("Connection refused")
            mock_create.return_value = mock_engine

            with pytest.raises(ConnectionError) as exc_info:
                manager.check_connection()

            assert "Impossible de se connecter" in str(exc_info.value)


class TestDatabaseManagerCheckPostgis:
    """Tests pour check_postgis."""

    def test_check_postgis_success(self, settings: Settings) -> None:
        """Test vérification PostGIS réussie."""
        manager = DatabaseManager(settings=settings)

        with patch("pgboundary.db.connection.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = "3.4.0"

            mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.execute.return_value = mock_result
            mock_create.return_value = mock_engine

            result = manager.check_postgis()

            assert result is True

    def test_check_postgis_failure(self, settings: Settings) -> None:
        """Test échec de vérification PostGIS."""
        manager = DatabaseManager(settings=settings)

        with patch("pgboundary.db.connection.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = Exception("PostGIS not installed")

            mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_create.return_value = mock_engine

            with pytest.raises(SchemaError) as exc_info:
                manager.check_postgis()

            assert "PostGIS" in str(exc_info.value)


class TestDatabaseManagerCreateSchema:
    """Tests pour create_schema."""

    def test_create_schema_success(self, settings: Settings) -> None:
        """Test création de schéma réussie."""
        manager = DatabaseManager(settings=settings)

        with patch("pgboundary.db.connection.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_conn = MagicMock()

            mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_create.return_value = mock_engine

            # On doit configurer le schema_name
            manager.settings._schema_config = MagicMock()
            manager.settings._schema_config.storage.schema_name = "geo_test"

            manager.create_schema()

            # Vérifier que CREATE SCHEMA a été appelé
            mock_conn.execute.assert_called()
            mock_conn.commit.assert_called()

    def test_create_schema_prefix_mode(self, settings: Settings) -> None:
        """Test création de schéma en mode prefix (pas de schéma)."""
        manager = DatabaseManager(settings=settings)

        # Configurer le mock pour retourner None comme schema_name
        mock_schema_config = MagicMock()
        mock_schema_config.storage.schema_name = None
        settings._schema_config = mock_schema_config

        with patch("pgboundary.db.connection.create_engine"):
            manager.create_schema()
            # Pas d'erreur, pas de création de schéma

    def test_create_schema_failure(self, settings: Settings) -> None:
        """Test échec de création de schéma."""
        manager = DatabaseManager(settings=settings)

        with patch("pgboundary.db.connection.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = Exception("Permission denied")

            mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_create.return_value = mock_engine

            # Configurer le schema_name
            manager.settings._schema_config = MagicMock()
            manager.settings._schema_config.storage.schema_name = "geo_test"

            with pytest.raises(SchemaError) as exc_info:
                manager.create_schema()

            assert "Erreur lors de la création du schéma" in str(exc_info.value)


class TestDatabaseManagerCreateTables:
    """Tests pour create_tables."""

    def test_create_tables_success(self, settings: Settings) -> None:
        """Test création de tables réussie."""
        manager = DatabaseManager(settings=settings)

        with (
            patch("pgboundary.db.connection.create_engine") as mock_create,
            patch("pgboundary.db.connection.TableFactory") as mock_tf_class,
        ):
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            mock_tf = MagicMock()
            mock_tf_class.return_value = mock_tf

            manager.create_tables()

            mock_tf.get_all_tables.assert_called_once()
            mock_tf.metadata.create_all.assert_called_once_with(mock_engine)

    def test_create_tables_failure(self, settings: Settings) -> None:
        """Test échec de création de tables."""
        manager = DatabaseManager(settings=settings)

        with (
            patch("pgboundary.db.connection.create_engine") as mock_create,
            patch("pgboundary.db.connection.TableFactory") as mock_tf_class,
        ):
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            mock_tf = MagicMock()
            mock_tf.get_all_tables.side_effect = Exception("Table error")
            mock_tf_class.return_value = mock_tf

            with pytest.raises(SchemaError) as exc_info:
                manager.create_tables()

            assert "Erreur lors de la création des tables" in str(exc_info.value)


class TestDatabaseManagerDropTables:
    """Tests pour drop_tables."""

    def test_drop_tables_success(self, settings: Settings) -> None:
        """Test suppression de tables réussie."""
        manager = DatabaseManager(settings=settings)

        with (
            patch("pgboundary.db.connection.create_engine") as mock_create,
            patch("pgboundary.db.connection.TableFactory") as mock_tf_class,
        ):
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            mock_tf = MagicMock()
            mock_tf_class.return_value = mock_tf

            manager.drop_tables()

            mock_tf.get_all_tables.assert_called_once()
            mock_tf.metadata.drop_all.assert_called_once_with(mock_engine)

    def test_drop_tables_failure(self, settings: Settings) -> None:
        """Test échec de suppression de tables."""
        manager = DatabaseManager(settings=settings)

        with (
            patch("pgboundary.db.connection.create_engine") as mock_create,
            patch("pgboundary.db.connection.TableFactory") as mock_tf_class,
        ):
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            mock_tf = MagicMock()
            mock_tf.get_all_tables.side_effect = Exception("Drop error")
            mock_tf_class.return_value = mock_tf

            with pytest.raises(SchemaError) as exc_info:
                manager.drop_tables()

            assert "Erreur lors de la suppression" in str(exc_info.value)


class TestDatabaseManagerInitDatabase:
    """Tests pour init_database."""

    def test_init_database_calls_all_methods(self, settings: Settings) -> None:
        """Test que init_database appelle toutes les méthodes dans l'ordre."""
        manager = DatabaseManager(settings=settings)

        with (
            patch.object(manager, "check_connection") as mock_check_conn,
            patch.object(manager, "check_postgis") as mock_check_postgis,
            patch.object(manager, "create_schema") as mock_create_schema,
            patch.object(manager, "create_tables") as mock_create_tables,
        ):
            manager.init_database()

            mock_check_conn.assert_called_once()
            mock_check_postgis.assert_called_once()
            mock_create_schema.assert_called_once()
            mock_create_tables.assert_called_once()


class TestDatabaseManagerClose:
    """Tests pour close."""

    def test_close_disposes_engine(self, settings: Settings) -> None:
        """Test que close dispose de l'engine."""
        manager = DatabaseManager(settings=settings)

        with patch("pgboundary.db.connection.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            # Accéder à l'engine pour le créer
            _ = manager.engine
            assert manager._engine is not None

            manager.close()

            mock_engine.dispose.assert_called_once()
            assert manager._engine is None
            assert manager._session_factory is None
            assert manager._table_factory is None

    def test_close_when_not_initialized(self, settings: Settings) -> None:
        """Test que close fonctionne même si pas initialisé."""
        manager = DatabaseManager(settings=settings)

        # Pas d'erreur même si l'engine n'a jamais été créé
        manager.close()

        assert manager._engine is None
