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

## Supported IGN Products

pyPgBoundary supports 17 IGN products organized in 6 categories.

### Administrative Boundaries

| Product | Size | Description |
|---------|-----:|-------------|
| `admin-express` | 400 MB | Simplified administrative boundaries (version 3-2) |
| `admin-express-cog` | 500 MB | With Official Geographic Code (COG) |
| `admin-express-cog-carto` | 550 MB | Cartographic version with municipal centers |
| `admin-express-cog-carto-pe` | 200 MB | Small-scale cartographic version |
| `admin-express-cog-carto-plus-pe` | 250 MB | Enriched version with cantons |

**Layers**: REGION, DEPARTEMENT, ARRONDISSEMENT, EPCI, COMMUNE, COMMUNE_ASSOCIEE_OU_DELEGUEE, CANTON, COLLECTIVITE_TERRITORIALE, ARRONDISSEMENT_MUNICIPAL, CHEF_LIEU_*

### Statistical Data

| Product | Size | Description |
|---------|-----:|-------------|
| `contours-iris` | 150 MB | IRIS contours - sub-municipal statistical divisions (communes >10,000 inhabitants) |

### Electoral Constituencies

| Product | Size | Description |
|---------|-----:|-------------|
| `circonscriptions-legislatives` | 10 MB | Legislative constituencies (577 in France, 2012 redistricting) |

### Land Cover

| Product | Size | Description |
|---------|-----:|-------------|
| `bd-foret` | 2.5 GB | Forest vegetation formations and land cover |
| `masque-foret` | 300 MB | Simplified forest area mask |
| `bcae` | 800 MB | Good Agricultural and Environmental Conditions (hedgerows, grasslands, ponds) |

### Addresses and Postal Codes

| Product | Size | Description |
|---------|-----:|-------------|
| `codes-postaux-ban` | 50 MB | Postal code contours (BAN convex hulls) |
| `codes-postaux-laposte` | 2 MB | Official La Poste database (points/centroids) |
| `codes-postaux-geoclip` | 15 MB | Géoclip basemap (mainland only) |
| `codes-postaux-generated` | ~100 MB | Voronoi-generated contours (local computation) |
| `adresse-premium` | 4 GB | Geolocated enriched address points |
| `ban-plus` | 3 GB | National Address Database enriched by IGN |

### Cartography

| Product | Size | Description |
|---------|-----:|-------------|
| `bd-carto` | 1.2 GB | Multi-theme cartographic database (boundaries, activity zones, facilities) |

### Available Territories

| Code | Territory |
|------|-----------|
| `FRA` | France (complete) |
| `FXX` | Metropolitan France |
| `GLP` | Guadeloupe |
| `MTQ` | Martinique |
| `GUF` | French Guiana |
| `REU` | Réunion |
| `MYT` | Mayotte |

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

### Overview

| Command | Description |
|---------|-------------|
| `pgboundary config` | Manage configuration (schema, DB, products) |
| `pgboundary init` | Initialize schema and tables |
| `pgboundary check` | Verify database connection |
| `pgboundary inspect` | Inspect geographic tables |
| `pgboundary info` | Display current configuration |
| `pgboundary download` | Download Admin Express data |
| `pgboundary load` | Load data according to configuration |
| `pgboundary products` | List available IGN products |
| `pgboundary product-info` | Show product details |
| `pgboundary load-product` | Load a specific product |

**Note**: A database indicator is displayed at the top of each command. Use `-q` to disable it.

### Configuration (`pgboundary config`)

```bash
pgboundary config                  # Show configuration summary
pgboundary config info             # Show full formatted configuration
pgboundary config init             # Create configuration interactively
pgboundary config init --force     # Overwrite existing file
pgboundary config update           # Modify existing configuration
pgboundary config db               # Configure database connection

# Product management
pgboundary config data add                          # Interactive mode
pgboundary config data remove                       # Interactive mode
pgboundary config data remove admin-express-cog     # Direct removal
pgboundary config data remove prod1 prod2 prod3     # Multiple removal

# Sync injection status with database
pgboundary config sync-product                      # All products
pgboundary config sync-product admin-express-cog    # Specific product
```

### Geographic Table Inspection (`pgboundary inspect`)

```bash
pgboundary inspect                    # Summary (default)
pgboundary inspect --summary          # Summary: rows, geometry type, SRID
pgboundary inspect --detailed         # Detailed: + columns, indexes, size
pgboundary inspect --full             # Full: + statistics, extent
pgboundary inspect --table commune    # Specific table
```

### IGN Product Catalog

```bash
pgboundary products                        # List all available products
pgboundary products --verbose              # With more details
pgboundary products --category admin       # Administrative boundaries
pgboundary products --category stats       # Statistical data (IRIS, etc.)
pgboundary products --category land        # Land cover
pgboundary products --category address     # Addresses
pgboundary products --category carto       # Cartographic data

pgboundary product-info admin-express-cog  # Product details
```

### Loading a Product (`pgboundary load-product`)

```bash
pgboundary load-product admin-express-cog               # Load Admin Express
pgboundary load-product contours-iris --territory FXX   # Metropolitan only
pgboundary load-product admin-express-cog --format gpkg # GeoPackage format
pgboundary load-product admin-express-cog --year 2023
pgboundary load-product admin-express-cog --layers "REGION,DEPARTEMENT"
pgboundary load-product admin-express-cog --replace     # Replace tables
```

### Global Options

| Option | Description |
|--------|-------------|
| `--version`, `-v` | Show pgboundary version |
| `--verbose`, `-V` | Enable verbose mode (DEBUG logging) |
| `--config`, `-c` | Configuration file path |
| `--database-url`, `-d` | PostgreSQL connection URL |
| `--quiet`, `-q` | Disable database status display |

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
