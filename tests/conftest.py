"""Configuration des fixtures pytest pour pgBoundary.

Ce module fournit les fixtures communes pour tous les tests :
- Géométries de test (Polygon, MultiPolygon, GeoDataFrame)
- Configuration et settings mockés
- Mocks HTTP pour les téléchargements IGN
- Mocks de base de données
- Mocks pour les widgets CLI interactifs
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Generator

import geopandas as gpd
import pytest
import responses
from shapely.geometry import MultiPolygon, Point, Polygon

from pgboundary.config import Settings
from pgboundary.schema_config import SchemaConfig

# =============================================================================
# Marqueurs pytest
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Configure les marqueurs personnalisés."""
    config.addinivalue_line(
        "markers",
        "integration: Tests d'intégration nécessitant une vraie base de données",
    )
    config.addinivalue_line(
        "markers",
        "slow: Tests lents (téléchargements, opérations lourdes)",
    )


# =============================================================================
# Fixtures de configuration
# =============================================================================


@pytest.fixture
def settings() -> Settings:
    """Fixture pour la configuration de test."""
    return Settings(
        database_url="postgresql://test:test@localhost:5432/test_boundaries",
        data_dir=Path("/tmp/pgboundary_test"),
    )


@pytest.fixture
def temp_config_file() -> Generator[Path, None, None]:
    """Fixture pour un fichier de configuration temporaire."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yml",
        delete=False,
    ) as f:
        f.write("""
storage:
  mode: schema
  schema_name: geo_test
  table_prefix: geo_

field_prefixes:
  code: cd_
  label: lb_
  date: dt_

srid: 4326

imports: {}
""")
        f.flush()
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def schema_config() -> SchemaConfig:
    """Fixture pour une configuration de schéma de test."""
    return SchemaConfig()


# =============================================================================
# Fixtures géométriques
# =============================================================================


@pytest.fixture
def sample_polygon() -> Polygon:
    """Fixture pour un polygone simple (carré 1x1)."""
    return Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])


@pytest.fixture
def sample_polygon_shifted() -> Polygon:
    """Fixture pour un polygone décalé (pour tests de similarité)."""
    return Polygon([(0.1, 0.1), (1.1, 0.1), (1.1, 1.1), (0.1, 1.1), (0.1, 0.1)])


@pytest.fixture
def sample_polygon_different() -> Polygon:
    """Fixture pour un polygone très différent."""
    return Polygon([(10, 10), (12, 10), (12, 12), (10, 12), (10, 10)])


@pytest.fixture
def sample_multipolygon(sample_polygon: Polygon) -> MultiPolygon:
    """Fixture pour un MultiPolygon."""
    return MultiPolygon([sample_polygon])


@pytest.fixture
def sample_point() -> Point:
    """Fixture pour un point simple."""
    return Point(0.5, 0.5)


@pytest.fixture
def sample_geodataframe(sample_polygon: Polygon) -> gpd.GeoDataFrame:
    """Fixture pour un GeoDataFrame simple avec communes."""
    data = {
        "cd_insee": ["01001", "01002", "01003"],
        "lb_nom": ["Commune A", "Commune B", "Commune C"],
        "geometry": [
            sample_polygon,
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1), (1, 0)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 1), (2, 0)]),
        ],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


@pytest.fixture
def sample_geodataframe_updated(sample_polygon_shifted: Polygon) -> gpd.GeoDataFrame:
    """Fixture pour un GeoDataFrame avec changements (pour tests historisation)."""
    data = {
        "cd_insee": ["01001", "01002", "01004"],  # 01003 supprimé, 01004 ajouté
        "lb_nom": ["Commune A modifiée", "Commune B", "Commune D"],
        "geometry": [
            sample_polygon_shifted,  # Géométrie légèrement modifiée
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1), (1, 0)]),
            Polygon([(3, 0), (4, 0), (4, 1), (3, 1), (3, 0)]),
        ],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


# =============================================================================
# Fixtures de base de données
# =============================================================================


@pytest.fixture
def mock_db_manager(settings: Settings) -> MagicMock:
    """Fixture pour un mock du DatabaseManager."""
    mock = MagicMock()
    mock.settings = settings
    mock.engine = MagicMock()
    return mock


@pytest.fixture
def mock_db_session() -> Generator[MagicMock, None, None]:
    """Fixture pour une session SQLAlchemy mockée."""
    session = MagicMock()
    session.execute = MagicMock(return_value=MagicMock())
    session.commit = MagicMock()
    session.rollback = MagicMock()

    # Configurer le context manager
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)

    yield session


# =============================================================================
# Fixtures HTTP (mocks pour téléchargements IGN)
# =============================================================================


@pytest.fixture
def mock_http_responses() -> Generator[responses.RequestsMock, None, None]:
    """Fixture pour mocker les requêtes HTTP avec responses."""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def mock_ign_download(mock_http_responses: responses.RequestsMock) -> responses.RequestsMock:
    """Fixture pour mocker un téléchargement IGN typique."""
    # Mock de la réponse HEAD pour obtenir la taille
    mock_http_responses.add(
        responses.HEAD,
        "https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS-COG/ADMIN-EXPRESS-COG_3-2__SHP_WGS84G_FRA_2024-02-22/ADMIN-EXPRESS-COG_3-2__SHP_WGS84G_FRA_2024-02-22.7z",
        headers={"Content-Length": "1024000"},
        status=200,
    )

    # Mock de la réponse GET pour le téléchargement
    mock_http_responses.add(
        responses.GET,
        "https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS-COG/ADMIN-EXPRESS-COG_3-2__SHP_WGS84G_FRA_2024-02-22/ADMIN-EXPRESS-COG_3-2__SHP_WGS84G_FRA_2024-02-22.7z",
        body=b"fake archive content",
        status=200,
    )

    return mock_http_responses


# =============================================================================
# Fixtures CLI (mocks pour widgets interactifs)
# =============================================================================


@pytest.fixture
def mock_readchar() -> Generator[MagicMock, None, None]:
    """Fixture pour mocker readchar.readkey() dans les widgets CLI."""
    with patch("pgboundary.cli_widgets.readchar.readkey") as mock:
        yield mock


@pytest.fixture
def mock_console() -> Generator[MagicMock, None, None]:
    """Fixture pour mocker la console Rich."""
    with patch("pgboundary.cli_widgets.console") as mock:
        yield mock


@pytest.fixture
def mock_live() -> Generator[MagicMock, None, None]:
    """Fixture pour mocker Rich Live (affichage dynamique)."""
    with patch("pgboundary.cli_widgets.Live") as mock:
        # Configurer le context manager
        mock_instance = MagicMock()
        mock.return_value.__enter__ = MagicMock(return_value=mock_instance)
        mock.return_value.__exit__ = MagicMock(return_value=False)
        yield mock


# =============================================================================
# Helpers pour créer des données de test
# =============================================================================


def create_test_shapefile(
    path: Path,
    data: dict[str, Any] | None = None,
) -> Path:
    """Crée un shapefile de test.

    Args:
        path: Chemin du fichier à créer
        data: Données optionnelles (défaut: 3 communes)

    Returns:
        Chemin du fichier créé
    """
    if data is None:
        data = {
            "NOM": ["Commune A", "Commune B", "Commune C"],
            "INSEE_COM": ["01001", "01002", "01003"],
            "geometry": [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]),
                Polygon([(1, 0), (2, 0), (2, 1), (1, 1), (1, 0)]),
                Polygon([(2, 0), (3, 0), (3, 1), (2, 1), (2, 0)]),
            ],
        }

    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path)
    return path


def create_test_geopackage(
    path: Path,
    layer_name: str = "communes",
    data: dict[str, Any] | None = None,
) -> Path:
    """Crée un GeoPackage de test.

    Args:
        path: Chemin du fichier à créer
        layer_name: Nom de la couche
        data: Données optionnelles

    Returns:
        Chemin du fichier créé
    """
    if data is None:
        data = {
            "NOM": ["Commune A", "Commune B"],
            "INSEE_COM": ["01001", "01002"],
            "geometry": [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]),
                Polygon([(1, 0), (2, 0), (2, 1), (1, 1), (1, 0)]),
            ],
        }

    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, layer=layer_name, driver="GPKG")
    return path
