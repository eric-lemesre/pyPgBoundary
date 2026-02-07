"""Tests pour le module de configuration."""

from pathlib import Path

from pgboundary.config import Settings
from pgboundary.schema_config import SchemaConfig, StorageMode


class TestSettings:
    """Tests pour la classe Settings."""

    def test_default_settings(self) -> None:
        """Teste les valeurs par défaut."""
        settings = Settings()

        # Le nom du schéma est maintenant géré via schema_config
        assert settings.schema_name == "geo"  # Nouvelle valeur par défaut
        assert settings.srid == 4326  # Nouvelle valeur par défaut
        assert settings.log_level == "INFO"

    def test_custom_settings_via_schema_config(self) -> None:
        """Teste les valeurs personnalisées via schema_config."""
        settings = Settings(log_level="DEBUG")
        assert settings.log_level == "DEBUG"

    def test_data_dir_path_conversion(self) -> None:
        """Teste la conversion du data_dir en Path."""
        settings = Settings(data_dir="/tmp/test")

        assert isinstance(settings.data_dir, Path)
        assert settings.data_dir == Path("/tmp/test")

    def test_ensure_data_dir_creates_directory(self, tmp_path: Path) -> None:
        """Teste que ensure_data_dir crée le répertoire."""
        data_dir = tmp_path / "pgboundary" / "data"
        settings = Settings(data_dir=data_dir)

        result = settings.ensure_data_dir()

        assert result == data_dir
        assert data_dir.exists()
        assert data_dir.is_dir()

    def test_schema_config_property(self) -> None:
        """Teste que schema_config est chargée correctement."""
        settings = Settings()
        config = settings.schema_config

        assert isinstance(config, SchemaConfig)
        assert config.storage.mode == StorageMode.SCHEMA


class TestSchemaConfig:
    """Tests pour la configuration du schéma."""

    def test_default_schema_config(self) -> None:
        """Teste les valeurs par défaut de SchemaConfig."""
        config = SchemaConfig()

        assert config.storage.mode == StorageMode.SCHEMA
        assert config.storage.schema_name == "geo"
        assert config.srid == 4326

    def test_get_full_table_name_schema_mode(self) -> None:
        """Teste get_full_table_name en mode schéma."""
        config = SchemaConfig()

        table_name = config.get_full_table_name("region")
        assert table_name == "region"

    def test_get_full_table_name_prefix_mode(self) -> None:
        """Teste get_full_table_name en mode préfixe."""
        from pgboundary.schema_config import StorageConfig

        config = SchemaConfig(storage=StorageConfig(mode=StorageMode.PREFIX, table_prefix="geo_"))

        table_name = config.get_full_table_name("region")
        assert table_name == "geo_region"

    def test_get_schema_name(self) -> None:
        """Teste get_schema_name."""
        config = SchemaConfig()
        assert config.get_schema_name() == "geo"

        from pgboundary.schema_config import StorageConfig

        config_prefix = SchemaConfig(storage=StorageConfig(mode=StorageMode.PREFIX))
        assert config_prefix.get_schema_name() is None

    def test_get_column_name(self) -> None:
        """Teste get_column_name avec les préfixes."""
        config = SchemaConfig()

        assert config.get_column_name("code", "insee") == "cd_insee"
        assert config.get_column_name("label", "nom") == "lb_nom"
        assert config.get_column_name("date", "creation") == "dt_creation"
