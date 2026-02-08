"""Tests d'intégration pour pgBoundary.

Ces tests nécessitent une base PostgreSQL/PostGIS disponible.
Ils sont marqués avec @pytest.mark.integration et peuvent être exécutés avec :
    pytest -m integration

Pour les exécuter :
1. Avec testcontainers (recommandé) :
    pip install -e ".[dev,integration]"
    pytest -m integration

2. Avec une base existante :
    export PGBOUNDARY_TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test_db
    pytest -m integration
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from pgboundary.config import Settings
from pgboundary.db.connection import DatabaseManager
from pgboundary.exceptions import SchemaError
from pgboundary.schema_config import SchemaConfig, StorageConfig, StorageMode

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


# =============================================================================
# Fixtures pour les tests d'intégration
# =============================================================================

# Variable globale pour stocker le container (évite le garbage collection)
_container: Any = None


def _get_test_database_url() -> str | None:
    """Récupère l'URL de la base de données de test."""
    return os.environ.get("PGBOUNDARY_TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def integration_db_url() -> Generator[str | None, None, None]:
    """Fixture pour l'URL de la base de données d'intégration.

    Essaie dans l'ordre :
    1. Variable d'environnement PGBOUNDARY_TEST_DATABASE_URL
    2. Testcontainers (si disponible et Docker est en marche)
    """
    global _container

    # Option 1: Variable d'environnement
    url = _get_test_database_url()
    if url:
        print(f"\n📦 Utilisation de la base de données: {url}")
        yield url
        return

    # Option 2: Testcontainers
    try:
        from testcontainers.postgres import PostgresContainer

        print("\n🐳 Démarrage du container PostgreSQL/PostGIS...")
        _container = PostgresContainer(
            image="postgis/postgis:15-3.3",
            username="test",
            password="test",
            dbname="test_boundaries",
        )
        _container.start()

        # Construire l'URL de connexion
        url = _container.get_connection_url()
        # Remplacer psycopg2 par psycopg
        url = url.replace("psycopg2", "psycopg")
        print(f"✅ Container démarré: {url}")

        yield url

        # Cleanup
        print("\n🧹 Arrêt du container...")
        _container.stop()
        _container = None
        return

    except ImportError:
        print("\n⚠️  testcontainers non installé. Installez avec: pip install -e '.[integration]'")
        yield None
        return

    except Exception as e:
        print(f"\n❌ Erreur testcontainers: {e}")
        print("   Vérifiez que Docker est en cours d'exécution.")
        yield None
        return


@pytest.fixture
def integration_settings(
    integration_db_url: str | None,
    tmp_path: Path,
) -> Settings | None:
    """Fixture pour les Settings d'intégration."""
    if integration_db_url is None:
        return None

    # Créer un fichier de configuration temporaire
    config_file = tmp_path / "pgboundary.yml"
    config_file.write_text("""
storage:
  mode: schema
  schema_name: test_geo
  table_prefix: geo_

field_prefixes:
  code: cd_
  label: lb_
  date: dt_

srid: 4326
""")

    return Settings(
        database_url=integration_db_url,
        config_file=config_file,
        data_dir=tmp_path / "data",
    )


@pytest.fixture
def integration_db_manager(
    integration_settings: Settings | None,
) -> Generator[DatabaseManager | None, None, None]:
    """Fixture pour le DatabaseManager d'intégration."""
    if integration_settings is None:
        yield None
        return

    manager = DatabaseManager(settings=integration_settings)
    yield manager
    manager.close()


@pytest.fixture
def test_geodataframe() -> gpd.GeoDataFrame:
    """Fixture pour un GeoDataFrame de test."""
    data = {
        "cd_insee": ["01001", "01002", "01003"],
        "lb_nom": ["Commune A", "Commune B", "Commune C"],
        "geometry": [
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]),
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1), (1, 0)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 1), (2, 0)]),
        ],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


# =============================================================================
# Tests d'intégration
# =============================================================================


@pytest.mark.integration
class TestDatabaseConnection:
    """Tests d'intégration pour la connexion à la base de données."""

    def test_check_connection(
        self,
        integration_db_manager: DatabaseManager | None,
    ) -> None:
        """Test de connexion à la base de données."""
        if integration_db_manager is None:
            pytest.skip("Base de données d'intégration non disponible")

        result = integration_db_manager.check_connection()
        assert result is True

    def test_check_postgis(
        self,
        integration_db_manager: DatabaseManager | None,
    ) -> None:
        """Test de vérification PostGIS."""
        if integration_db_manager is None:
            pytest.skip("Base de données d'intégration non disponible")

        try:
            result = integration_db_manager.check_postgis()
            assert result is True
        except SchemaError:
            pytest.skip("PostGIS n'est pas installé sur la base de test")


@pytest.mark.integration
class TestSchemaCreation:
    """Tests d'intégration pour la création de schéma."""

    def test_create_schema(
        self,
        integration_db_manager: DatabaseManager | None,
    ) -> None:
        """Test de création de schéma."""
        if integration_db_manager is None:
            pytest.skip("Base de données d'intégration non disponible")

        # Créer le schéma
        integration_db_manager.create_schema()

        # Vérifier que le schéma existe
        with integration_db_manager.engine.connect() as conn:
            from sqlalchemy import text

            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = 'test_geo'"
                )
            )
            schemas = [row[0] for row in result]
            assert "test_geo" in schemas

    def test_create_tables(
        self,
        integration_db_manager: DatabaseManager | None,
    ) -> None:
        """Test de création de tables."""
        if integration_db_manager is None:
            pytest.skip("Base de données d'intégration non disponible")

        # Créer le schéma d'abord
        integration_db_manager.create_schema()

        # Créer les tables
        integration_db_manager.create_tables()

        # Vérifier qu'au moins une table existe
        with integration_db_manager.engine.connect() as conn:
            from sqlalchemy import text

            result = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'test_geo'"
                )
            )
            tables = [row[0] for row in result]
            assert len(tables) > 0


@pytest.mark.integration
class TestDataLoading:
    """Tests d'intégration pour le chargement de données."""

    def test_load_geodataframe(
        self,
        integration_db_manager: DatabaseManager | None,
        test_geodataframe: gpd.GeoDataFrame,
    ) -> None:
        """Test de chargement d'un GeoDataFrame."""
        if integration_db_manager is None:
            pytest.skip("Base de données d'intégration non disponible")

        # S'assurer que le schéma existe
        integration_db_manager.create_schema()

        # Charger les données
        schema_name = integration_db_manager.settings.schema_name
        test_geodataframe.to_postgis(
            name="test_commune",
            con=integration_db_manager.engine,
            schema=schema_name,
            if_exists="replace",
            index=False,
        )

        # Vérifier que les données ont été chargées
        loaded = gpd.read_postgis(
            f"SELECT * FROM {schema_name}.test_commune",
            con=integration_db_manager.engine,
            geom_col="geometry",
        )

        assert len(loaded) == 3
        assert "cd_insee" in loaded.columns
        assert "lb_nom" in loaded.columns

    def test_load_with_srid(
        self,
        integration_db_manager: DatabaseManager | None,
        test_geodataframe: gpd.GeoDataFrame,
    ) -> None:
        """Test de chargement avec SRID correct."""
        if integration_db_manager is None:
            pytest.skip("Base de données d'intégration non disponible")

        # S'assurer que le schéma existe
        integration_db_manager.create_schema()

        schema_name = integration_db_manager.settings.schema_name

        # Charger avec SRID 4326
        test_geodataframe.to_postgis(
            name="test_commune_srid",
            con=integration_db_manager.engine,
            schema=schema_name,
            if_exists="replace",
            index=False,
        )

        # Vérifier le SRID
        with integration_db_manager.engine.connect() as conn:
            from sqlalchemy import text

            result = conn.execute(
                text(f"SELECT ST_SRID(geometry) FROM {schema_name}.test_commune_srid LIMIT 1")
            )
            srid = result.scalar()
            assert srid == 4326


@pytest.mark.integration
class TestFullWorkflow:
    """Tests d'intégration pour le workflow complet."""

    def test_init_database(
        self,
        integration_db_manager: DatabaseManager | None,
    ) -> None:
        """Test d'initialisation complète de la base de données."""
        if integration_db_manager is None:
            pytest.skip("Base de données d'intégration non disponible")

        try:
            # Initialiser la base de données
            integration_db_manager.init_database()

            # Vérifier que tout est en place
            assert integration_db_manager.check_connection() is True

        except SchemaError as e:
            if "PostGIS" in str(e):
                pytest.skip("PostGIS n'est pas installé sur la base de test")
            raise

    def test_cleanup_drop_tables(
        self,
        integration_db_manager: DatabaseManager | None,
    ) -> None:
        """Test de nettoyage (suppression des tables)."""
        if integration_db_manager is None:
            pytest.skip("Base de données d'intégration non disponible")

        # Créer d'abord les tables
        integration_db_manager.create_schema()
        integration_db_manager.create_tables()

        # Supprimer les tables
        integration_db_manager.drop_tables()

        # Vérifier que les tables ont été supprimées
        with integration_db_manager.engine.connect() as conn:
            from sqlalchemy import text

            result = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'test_geo'"
                )
            )
            tables = [row[0] for row in result]
            # Les tables créées par la table_factory devraient être supprimées
            # Mais d'autres tables de test peuvent exister
            assert "region" not in tables or "commune" not in tables


@pytest.mark.integration
class TestHistorizationIntegration:
    """Tests d'intégration pour l'historisation."""

    def test_historization_workflow(
        self,
        integration_db_manager: DatabaseManager | None,
        test_geodataframe: gpd.GeoDataFrame,
    ) -> None:
        """Test du workflow d'historisation complet."""
        if integration_db_manager is None:
            pytest.skip("Base de données d'intégration non disponible")

        from pgboundary.historization import HistorizationManager

        # Créer le schéma
        integration_db_manager.create_schema()

        schema_name = integration_db_manager.settings.schema_name

        # Créer le manager d'historisation
        hist_manager = HistorizationManager(
            engine=integration_db_manager.engine,
            schema=schema_name,
            table="test_hist_commune",
            key_field="cd_insee",
        )

        # Premier import
        result = hist_manager.import_with_historization(
            test_geodataframe,
            "2024",
        )

        assert result == 3

        # Vérifier les colonnes d'historisation
        loaded = gpd.read_postgis(
            f"SELECT * FROM {schema_name}.test_hist_commune",
            con=integration_db_manager.engine,
            geom_col="geometry",
        )

        assert "dt_debut" in loaded.columns
        assert "dt_fin" in loaded.columns
        assert len(loaded) == 3


# =============================================================================
# Tests de configuration sans base de données
# =============================================================================


class TestSchemaConfigIntegration:
    """Tests d'intégration pour la configuration de schéma."""

    def test_schema_config_creation(self, tmp_path: Path) -> None:
        """Test de création de configuration de schéma."""
        config_file = tmp_path / "test_config.yml"

        config = SchemaConfig(
            storage=StorageConfig(
                mode=StorageMode.SCHEMA,
                schema_name="test_schema",
                table_prefix="t_",
            ),
            srid=2154,  # Lambert 93
        )

        # Sauvegarder la configuration
        from pgboundary.schema_config import load_config, save_config

        save_config(config, config_file)

        # Recharger et vérifier
        loaded = load_config(config_file)
        assert loaded.storage.schema_name == "test_schema"
        assert loaded.srid == 2154

    def test_full_table_name_generation(self) -> None:
        """Test de génération des noms de tables complets."""
        config = SchemaConfig(
            storage=StorageConfig(
                mode=StorageMode.SCHEMA,
                schema_name="geo",
                table_prefix="geo_",
            ),
        )

        # get_full_table_name retourne le nom de table (sans préfixe dans ce cas)
        # Le nom de table par défaut pour "commune" est "commune"
        table_name = config.get_full_table_name("commune")
        assert table_name == "commune"
        assert config.get_schema_name() == "geo"

    def test_prefix_mode_table_names(self) -> None:
        """Test des noms de tables en mode prefix."""
        config = SchemaConfig(
            storage=StorageConfig(
                mode=StorageMode.PREFIX,
                schema_name="public",
                table_prefix="boundaries_",
            ),
        )

        # En mode PREFIX, get_full_table_name retourne le nom avec le préfixe
        table_name = config.get_full_table_name("region")
        assert table_name == "boundaries_region"
        # En mode prefix, le schéma est public (retourne None car c'est public)
        assert config.get_schema_name() is None
