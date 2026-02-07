"""Configuration des fixtures pytest."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from shapely.geometry import MultiPolygon, Polygon

from pgboundary.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Fixture pour la configuration de test."""
    return Settings(
        database_url="postgresql://test:test@localhost:5432/test_boundaries",
        schema_name="test_admin_express",
        data_dir=Path("/tmp/pgboundary_test"),
    )


@pytest.fixture
def sample_polygon() -> Polygon:
    """Fixture pour un polygone simple."""
    return Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])


@pytest.fixture
def sample_multipolygon(sample_polygon: Polygon) -> MultiPolygon:
    """Fixture pour un MultiPolygon."""
    return MultiPolygon([sample_polygon])


@pytest.fixture
def mock_db_manager(settings: Settings) -> MagicMock:
    """Fixture pour un mock du DatabaseManager."""
    mock = MagicMock()
    mock.settings = settings
    return mock
