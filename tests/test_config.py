"""Tests pour le module de configuration."""

from pathlib import Path

from pgboundary.config import Settings


class TestSettings:
    """Tests pour la classe Settings."""

    def test_default_settings(self) -> None:
        """Teste les valeurs par défaut."""
        settings = Settings()

        assert settings.schema_name == "admin_express"
        assert settings.srid == 2154
        assert settings.log_level == "INFO"

    def test_custom_settings(self) -> None:
        """Teste les valeurs personnalisées."""
        settings = Settings(
            schema_name="custom_schema",
            srid=4326,
            log_level="DEBUG",
        )

        assert settings.schema_name == "custom_schema"
        assert settings.srid == 4326
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
