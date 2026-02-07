# Development Guide

**[Version française](DEVELOPMENT.fr.md)**

## Development Environment Setup

### Prerequisites

- Python 3.11+
- Git
- PostgreSQL with PostGIS (for integration tests)
- 7-Zip

### Clone and Setup

```bash
# Clone the repository
git clone https://github.com/eric/pgboundary.git
cd pgboundary

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Project Structure

```
pgboundary/
├── src/pgboundary/          # Main package
│   ├── __init__.py            # Package entry point
│   ├── cli.py                 # Command-line interface
│   ├── config.py              # Settings management
│   ├── schema_config.py       # YAML configuration
│   ├── exceptions.py          # Custom exceptions
│   ├── db/                    # Database layer
│   │   ├── connection.py      # Connection manager
│   │   └── models.py          # SQLAlchemy models
│   ├── loaders/               # Data loaders
│   │   ├── base.py            # Abstract base loader
│   │   └── admin_express.py   # IGN Admin Express loader
│   ├── sources/               # Data sources
│   │   └── ign.py             # IGN download handler
│   └── types/                 # Type definitions
│       └── boundaries.py      # Pydantic models
├── tests/                     # Test suite
├── docs/                      # Documentation
├── pyproject.toml             # Project configuration
└── pgboundary.yml           # Default configuration
```

## Code Style

### Formatting and Linting

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check code style
ruff check src/ tests/

# Fix automatically
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/
```

### Type Checking

We use [mypy](https://mypy.readthedocs.io/) in strict mode:

```bash
mypy src/
```

### Pre-commit Hooks

Pre-commit hooks run automatically on each commit:

```bash
# Run manually on all files
pre-commit run --all-files
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pgboundary --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v
```

### Test Database

For integration tests, set up a test database:

```bash
export PGBOUNDARY_DATABASE_URL=postgresql://test:test@localhost:5432/test_boundaries
```

### Writing Tests

```python
# tests/test_example.py
import pytest
from pgboundary.config import Settings

class TestExample:
    def test_default_settings(self) -> None:
        settings = Settings()
        assert settings.srid == 4326

    @pytest.fixture
    def custom_settings(self) -> Settings:
        return Settings(log_level="DEBUG")
```

## Architecture

### Configuration Layer

```
Settings (pydantic-settings)
    └── SchemaConfig (YAML)
            ├── StorageConfig
            ├── FieldPrefixes
            └── TableNames
```

### Database Layer

```
DatabaseManager
    ├── Engine (SQLAlchemy)
    ├── SessionFactory
    └── TableFactory
            └── Dynamic table generation
```

### Loader Layer

```
BaseLoader (abstract)
    └── AdminExpressLoader
            ├── IGNDataSource (download)
            └── GeoDataFrame processing
```

## Adding New Features

### Adding a New Administrative Layer

1. Add table creation function in `db/models.py`:

```python
def create_new_layer_table(metadata: MetaData, config: SchemaConfig) -> Table:
    table_name = config.get_full_table_name("new_layer")
    fp = config.field_prefixes

    return Table(
        table_name,
        metadata,
        Column("uid", Uuid, primary_key=True, default=uuid.uuid4),
        Column(f"{fp.label}nom", String(255), nullable=False),
        # ... other columns
        Column("geometry", Geometry("MULTIPOLYGON", srid=config.srid)),
    )
```

2. Add to `TableFactory` class
3. Add column mapping in `get_column_mapping()`
4. Add to `LAYER_TO_TABLE_KEY` in loader
5. Update `TableNames` in `schema_config.py`

### Adding a New Data Source

1. Create new source in `sources/`:

```python
# sources/new_source.py
class NewDataSource:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def download(self, **kwargs) -> Path:
        # Download logic
        pass
```

2. Create corresponding loader in `loaders/`

## Release Process

### Version Bump

1. Update version in `src/pgboundary/__init__.py`
2. Update CHANGELOG.md
3. Commit: `git commit -m "Bump version to X.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push && git push --tags`

### Building Distribution

```bash
# Build package
python -m build

# Check package
twine check dist/*
```

## Contributing Guidelines

### Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests
4. Run linting and tests: `ruff check && pytest`
5. Commit with descriptive message
6. Push and create Pull Request

### Commit Messages

Follow conventional commits:

```
feat: add new administrative layer support
fix: correct column mapping for EPCI
docs: update installation guide
test: add tests for configuration loading
refactor: simplify database connection handling
```

### Code Review Checklist

- [ ] Code follows project style guide
- [ ] All tests pass
- [ ] New features have tests
- [ ] Documentation is updated
- [ ] Type hints are complete
- [ ] No security vulnerabilities

## License

This project is licensed under GPL v3. All contributions must be compatible with this license.

When adding new files, include the license header:

```python
# pyPgBoundary - French Administrative Boundaries for PostgreSQL
# Copyright (C) 2024 Eric
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
```
