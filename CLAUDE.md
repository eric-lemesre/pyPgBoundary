# CLAUDE.md - pyPgBoundary Developer Guide

This document provides essential context for AI assistants and developers working on the pyPgBoundary project.

## Project Overview

**pyPgBoundary** is a Python module for automating the download and import of French administrative boundary data into PostgreSQL/PostGIS databases. It integrates geospatial data from the IGN (Institut Géographique National) Admin Express COG dataset.

- **Version**: 0.1.0 (Alpha)
- **License**: GPL-3.0-or-later
- **Python**: 3.11+
- **Data Source**: [IGN Geoservices](https://geoservices.ign.fr/adminexpress)

### Supported Administrative Levels

| Level | French Name | Count |
|-------|-------------|-------|
| Region | Région | 18 |
| Department | Département | 101 |
| EPCI | Établissement Public de Coopération Intercommunale | ~1,200 |
| Municipality | Commune | 34,500+ |
| Associated/Delegated | Commune associée/déléguée | Variable |

## Architecture

```
┌─────────────────────────────────────────────┐
│         CLI Layer (Typer + Rich)            │
│    src/pgboundary/cli.py                  │
├─────────────────────────────────────────────┤
│    Application Layer                        │
│  ┌─────────────────────────────────────┐   │
│  │  AdminExpressLoader (orchestration) │   │
│  │  Settings (configuration)           │   │
│  └─────────────────────────────────────┘   │
├─────────────────────────────────────────────┤
│    Domain Layer                             │
│  ┌────────────────────────────────────┐    │
│  │  Pydantic Models (types/)          │    │
│  │  Schema Configuration              │    │
│  └────────────────────────────────────┘    │
├─────────────────────────────────────────────┤
│    Infrastructure Layer                     │
│  ┌──────────────────┐  ┌─────────────────┐ │
│  │ IGNDataSource    │  │ DatabaseManager │ │
│  │ (HTTP + Extract) │  │ (SQLAlchemy)    │ │
│  └──────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────┤
│    Data Layer                               │
│  ┌─────────────────────────────────────┐   │
│  │  PostgreSQL/PostGIS + GeoPandas     │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Project Structure

```
pyPgBoundary/
├── src/pgboundary/
│   ├── __init__.py           # Public API exports
│   ├── cli.py                # Typer CLI commands
│   ├── config.py             # Pydantic Settings
│   ├── schema_config.py      # YAML schema definition
│   ├── exceptions.py         # Exception hierarchy
│   ├── db/
│   │   ├── connection.py     # DatabaseManager
│   │   └── models.py         # SQLAlchemy table factories
│   ├── loaders/
│   │   ├── base.py           # BaseLoader (abstract)
│   │   └── admin_express.py  # IGN Admin Express loader
│   ├── sources/
│   │   └── ign.py            # IGN data source (download/extract)
│   └── types/
│       └── boundaries.py     # Pydantic domain models
├── tests/
│   ├── conftest.py           # pytest fixtures
│   ├── test_config.py
│   ├── test_types.py
│   └── test_loaders.py
├── docs/
│   ├── INSTALL.md / INSTALL.fr.md
│   └── DEVELOPMENT.md / DEVELOPMENT.fr.md
├── pgboundary.yml          # Example configuration
├── .env.example
└── pyproject.toml
```

## Quick Reference

### CLI Commands

```bash
# Configuration
pgboundary config --interactive    # Create config interactively
pgboundary config --show           # Display current config
pgboundary info                    # Show configuration summary

# Database
pgboundary check                   # Verify DB connection + PostGIS
pgboundary init                    # Create schema and tables

# Data operations
pgboundary download --territory france_metropolitaine --year 2024
pgboundary load --layers "REGION,DEPARTEMENT,COMMUNE"
```

### API Usage

```python
from pgboundary import Settings, AdminExpressLoader

settings = Settings(database_url="postgresql://user:pass@localhost/db")
loader = AdminExpressLoader(settings=settings)
loader.load(territory="france_metropolitaine", year="2024")
```

### Environment Variables

All settings can be overridden via environment variables with the `PGBOUNDARY_` prefix:

```bash
PGBOUNDARY_DATABASE_URL=postgresql://user:pass@localhost:5432/boundaries
PGBOUNDARY_DATA_DIR=/custom/path/data
PGBOUNDARY_LOG_LEVEL=DEBUG
PGBOUNDARY_CONFIG_FILE=/path/to/custom.yml
```

## Development Guidelines

### Python Conventions

1. **Python Version**: 3.11+ required (uses modern type hints, `|` union syntax)

2. **Type Hints**: Mandatory on all public APIs
   ```python
   def load_layer(self, layer: AdminLevel, replace: bool = False) -> int:
       """Load a single administrative layer."""
   ```

3. **Docstrings**: Google-style format
   ```python
   def reproject(self, gdf: gpd.GeoDataFrame, target_srid: int) -> gpd.GeoDataFrame:
       """Reproject a GeoDataFrame to target SRID.

       Args:
           gdf: Input GeoDataFrame with geometry column.
           target_srid: Target EPSG code (e.g., 4326 for WGS84).

       Returns:
           Reprojected GeoDataFrame with updated CRS.

       Raises:
           ValidationError: If geometry column is missing.
       """
   ```

4. **Imports**: Use absolute imports, organized by isort
   ```python
   from __future__ import annotations

   import logging
   from pathlib import Path
   from typing import TYPE_CHECKING

   import geopandas as gpd
   from pydantic import BaseModel

   from pgboundary.exceptions import LoaderError

   if TYPE_CHECKING:
       from pgboundary.config import Settings
   ```

5. **Line Length**: 100 characters maximum

6. **Naming Conventions**:
   - Classes: `PascalCase` (e.g., `AdminExpressLoader`, `DatabaseManager`)
   - Functions/methods: `snake_case` (e.g., `load_regions`, `check_connection`)
   - Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_SRID`, `ADMIN_LEVELS`)
   - Private: Single underscore prefix (e.g., `_prepare_geodataframe`)

### Geospatial Patterns

1. **Geometry Normalization**: Always normalize to MULTIPOLYGON
   ```python
   from shapely import MultiPolygon, Polygon

   def ensure_multi(geom: Polygon | MultiPolygon) -> MultiPolygon:
       if isinstance(geom, Polygon):
           return MultiPolygon([geom])
       return geom
   ```

2. **CRS Handling**: Always specify SRID explicitly
   ```python
   # Reproject to target SRID (default: 4326 WGS84)
   if gdf.crs.to_epsg() != target_srid:
       gdf = gdf.to_crs(epsg=target_srid)
   ```

3. **Column Prefixes** (configured in YAML):
   - `cd_*`: Codes (e.g., `cd_insee`, `cd_postal`, `cd_region`)
   - `lb_*`: Labels (e.g., `lb_nom`, `lb_nature`)
   - `dt_*`: Dates (e.g., `dt_creation`, `dt_modification`)

4. **PostGIS Loading**: Use GeoPandas to_postgis
   ```python
   gdf.to_postgis(
       name=table_name,
       con=engine,
       schema=schema_name,
       if_exists="replace",  # or "append"
       index=False,
   )
   ```

### Database Patterns

1. **Session Management**: Always use context manager
   ```python
   with db_manager.session() as session:
       result = session.execute(query)
       session.commit()
   # Automatic rollback on exception
   ```

2. **Connection Pooling**: Pre-configured (pool_size=5, max_overflow=10)

3. **Table Schema**: Dynamic generation via TableFactory based on YAML config

### Exception Handling

Use the project's exception hierarchy:

```python
from pgboundary.exceptions import (
    PyPgBoundaryError,  # Base exception
    DatabaseError,      # DB operations
    ConnectionError,    # Connection issues
    SchemaError,        # DDL operations
    DownloadError,      # HTTP/download issues
    DataSourceError,    # Source operations
    ValidationError,    # Data validation
    LoaderError,        # Loading pipeline
)
```

### Testing

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v --cov-report=html
```

**Fixtures** (in `conftest.py`):
- `settings`: Pre-configured Settings instance
- `sample_polygon`, `sample_multipolygon`: Test geometries
- `mock_db_manager`: Mocked DatabaseManager

### Code Quality Tools

```bash
# Linting and formatting
ruff check src tests
ruff format src tests

# Type checking
mypy src

# Pre-commit hooks
pre-commit run --all-files
```

**Ruff Rules** (configured in pyproject.toml):
- E, W: pycodestyle
- F: Pyflakes
- I: isort
- B: flake8-bugbear
- C4: flake8-comprehensions
- UP: pyupgrade
- PTH: flake8-use-pathlib

## Configuration

### Storage Modes

**Schema Mode** (default): Dedicated PostgreSQL schema
```yaml
storage:
  mode: schema
  schema_name: geo
# Tables: geo.region, geo.departement, geo.commune, etc.
```

**Prefix Mode**: Tables in public schema with prefix
```yaml
storage:
  mode: prefix
  table_prefix: geo_
# Tables: public.geo_region, public.geo_departement, etc.
```

### Configuration File (pgboundary.yml)

```yaml
storage:
  mode: schema
  schema_name: geo
  table_prefix: geo_

field_prefixes:
  code: cd_
  label: lb_
  date: dt_

table_names:
  region: region
  departement: departement
  epci: epci
  commune: commune
  commune_associee_deleguee: commune_associee_deleguee

srid: 4326
```

## Internationalization (i18n)

The project supports multiple languages with English as the default.

### Documentation Strategy

- README.md (English) / README.fr.md (French)
- docs/INSTALL.md / docs/INSTALL.fr.md
- docs/DEVELOPMENT.md / docs/DEVELOPMENT.fr.md

### Code Comments and Docstrings

- **Code comments**: English (for international collaboration)
- **User-facing messages**: Should use locale-aware formatting

### Locale Detection (Future)

```python
import locale

# Get system locale
system_locale = locale.getdefaultlocale()[0]  # e.g., 'fr_FR', 'en_US'

# Use for user-facing messages
if system_locale and system_locale.startswith('fr'):
    message = "Chargement des données..."
else:
    message = "Loading data..."
```

### CLI Messages

The CLI (Typer + Rich) should support locale-aware output:
- Error messages
- Progress indicators
- Help text

## Key Dependencies

| Package | Purpose | Min Version |
|---------|---------|-------------|
| geopandas | GeoDataFrames | 1.0.0 |
| shapely | Geometry operations | 2.0.0 |
| sqlalchemy | ORM + DDL | 2.0.0 |
| geoalchemy2 | PostGIS dialect | 0.15.0 |
| psycopg | PostgreSQL driver | 3.1.0 |
| typer | CLI framework | 0.12.0 |
| pydantic | Data validation | 2.0.0 |
| pydantic-settings | Settings management | 2.0.0 |
| rich | Terminal formatting | 13.0.0 |
| httpx | HTTP client | 0.27.0 |
| pyproj | CRS transformations | 3.6.0 |

## External Requirements

- **PostgreSQL**: 12+ with PostGIS extension
- **7-Zip**: Required for extracting .7z archives from IGN
- **Network**: Access to data.geopf.fr for downloads

## Common Tasks

### Adding a New Administrative Layer

1. Add enum value in `types/boundaries.py`:
   ```python
   class AdminLevel(StrEnum):
       ARRONDISSEMENT = "arrondissement"  # New layer
   ```

2. Add Pydantic model in `types/boundaries.py`

3. Add column mapping in `db/models.py` TableFactory

4. Add table name in `schema_config.py`

5. Add loader method in `loaders/admin_express.py`

6. Add CLI option in `cli.py`

7. Add tests in `tests/`

### Modifying Column Mappings

Edit `db/models.py` in the relevant `_get_*_columns()` method:

```python
def _get_commune_columns(self) -> list[Column]:
    return [
        Column("uid", UUID, primary_key=True, default=uuid4),
        Column(f"{self.prefix_label}nom", String(255), nullable=False),
        Column(f"{self.prefix_code}insee", String(5), nullable=False, unique=True),
        # Add new column here
    ]
```

## Debugging Tips

1. **Enable debug logging**:
   ```bash
   PGBOUNDARY_LOG_LEVEL=DEBUG pgboundary load
   ```

2. **Check PostGIS**:
   ```sql
   SELECT PostGIS_Version();
   SELECT * FROM spatial_ref_sys WHERE srid = 4326;
   ```

3. **Inspect loaded data**:
   ```sql
   SELECT cd_insee, lb_nom, ST_AsText(ST_Centroid(geometry))
   FROM geo.commune LIMIT 10;
   ```

## Git Workflow

- Main branch: `master`
- Feature branches: `feature/<description>`
- Commit messages: Conventional commits (feat:, fix:, docs:, refactor:)
- Pre-commit hooks: ruff, mypy

---

*This document is maintained for AI assistants and developers. Update when adding features or changing conventions.*
