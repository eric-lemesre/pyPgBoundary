# pyPgBoundary

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-336791.svg)](https://postgis.net/)

**[Version française](README.fr.md)**

A Python module for loading French administrative boundaries into PostgreSQL/PostGIS databases.

## Overview

pyPgBoundary automates the download and import of French administrative boundary data from the IGN (Institut Géographique National) Admin Express dataset into a PostgreSQL database with PostGIS extension.

### Supported Administrative Levels

- **Régions** (Regions)
- **Départements** (Departments)
- **EPCI** (Intercommunal Cooperation Establishments)
- **Communes** (Municipalities)
- **Communes associées/déléguées** (Associated/Delegated municipalities)

## Features

- Automatic download from IGN Geoservices
- Configurable database schema (dedicated schema or table prefix)
- Standardized column naming conventions (`cd_*`, `lb_*`, `dt_*`)
- UUID primary keys for all entities
- WGS84 (EPSG:4326) coordinate system by default
- Interactive CLI with Rich formatting
- YAML configuration file
- Full type hints and modern Python practices

## Quick Start

```bash
# Install the package
pip install pgboundary

# Create configuration interactively
pgboundary config --interactive

# Initialize the database
pgboundary init

# Download and load data
pgboundary load
```

## Requirements

- Python 3.11+
- PostgreSQL 12+ with PostGIS extension
- 7-Zip (for extracting IGN archives)

## Documentation

- [Installation Guide](docs/INSTALL.md)
- [Development Guide](docs/DEVELOPMENT.md)

## Database Schema

### Storage Modes

**Schema mode** (default): Tables are created in a dedicated schema
```
geo.region
geo.departement
geo.commune
...
```

**Prefix mode**: Tables are created in `public` schema with a prefix
```
public.geo_region
public.geo_departement
public.geo_commune
...
```

### Column Naming Conventions

| Type | Prefix | Examples |
|------|--------|----------|
| Codes | `cd_` | `cd_insee`, `cd_postal`, `cd_region` |
| Labels | `lb_` | `lb_nom`, `lb_nature` |
| Dates | `dt_` | `dt_creation`, `dt_modification` |
| ID | `uid` | UUID, auto-generated |

## Configuration

Configuration is stored in `pgboundary.yml`:

```yaml
storage:
  mode: schema        # 'schema' or 'prefix'
  schema_name: geo    # PostgreSQL schema name
  table_prefix: geo_  # Table prefix (if mode = 'prefix')

field_prefixes:
  code: cd_
  label: lb_
  date: dt_

srid: 4326
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `pgboundary config` | Manage configuration file |
| `pgboundary init` | Initialize database schema and tables |
| `pgboundary download` | Download Admin Express data |
| `pgboundary load` | Load data into PostgreSQL |
| `pgboundary check` | Verify database connection |
| `pgboundary info` | Display current configuration |

## Python API

```python
from pgboundary import Settings, AdminExpressLoader

# Load with default settings
loader = AdminExpressLoader()
loader.load()

# Load specific layers
loader.load_regions()
loader.load_departements()
loader.load_communes()
```

## Data Source

Data is sourced from [IGN Admin Express COG](https://geoservices.ign.fr/adminexpress), the official French government geographic reference dataset.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please read [DEVELOPMENT.md](docs/DEVELOPMENT.md) for guidelines.

## Acknowledgments

- [IGN](https://www.ign.fr/) for providing the Admin Express dataset
- [PostGIS](https://postgis.net/) for spatial database capabilities
- [GeoPandas](https://geopandas.org/) for geospatial data processing
