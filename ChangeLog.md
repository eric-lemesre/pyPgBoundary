# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**[Version française](ChangeLog.fr.md)**

## [Unreleased]

## [0.4.0] - 2026-02-08

### Added

- **Bilingual changelog**
  - `ChangeLog.md` (English, default)
  - `ChangeLog.fr.md` (French)
  - Cross-links between versions

## [0.3.0] - 2026-02-07

### Added

- **New product: Legislative Constituencies**
  - Product `circonscriptions-legislatives` (577 constituencies in France)
  - New product category: `electoral`
  - Source: data.gouv.fr (redistricting unchanged since 2012)

- **Product size display**
  - Approximate size shown in `pgboundary products`
  - Size documented in READMEs (KB, MB, GB as appropriate)

- **Combined geometric comparison system**
  - New `COMBINED` method (recommended) combining IoU and Hausdorff
  - Sequential logic: IoU calculation first, then Hausdorff if needed
  - Uses Shapely for all geometric operations

- **Similarity decision matrix**
  - `IDENTICAL` [0.95 - 1.00]: Automatic merge without verification
  - `LIKELY_MATCH` [0.80 - 0.95]: Strong match, validation if attributes differ
  - `SUSPECT` [0.50 - 0.80]: Potential conflict or temporal change
  - `DISTINCT` [< 0.50]: Distinct objects

- **New data structures** (`import_config.py`)
  - `SimilarityLevel`: Enumeration of 4 similarity levels
  - `SimilarityResult`: Detailed result with IoU score, Hausdorff distance, combined score
  - `SimilarityThresholds`: Configurable decision matrix thresholds

- **Computation functions** (`geometry_compare.py`)
  - `compute_combined_similarity()`: Sequential IoU then Hausdorff logic
  - `compute_similarity()`: Main function returning a `SimilarityResult`
  - `_compute_combined_score()`: Weighted normalized score (70% IoU, 30% Hausdorff)

- **CLI configuration commands**
  - `pgboundary config`: Display configuration summary
  - `pgboundary config info`: Display formatted YAML configuration
  - `pgboundary config init`: Create configuration interactively
  - `pgboundary config update`: Modify existing configuration
  - `pgboundary config db`: Configure database connection
  - `pgboundary config data add`: Add products interactively
  - `pgboundary config data remove`: Remove products (interactive or direct)
  - `pgboundary config sync-product`: Sync injection status with database

- **Inspection command**
  - `pgboundary inspect`: Inspect geographic tables
  - Options `--summary`, `--detailed`, `--full` for different detail levels
  - Option `--table` to inspect a specific table

- **Database indicator**
  - Active database displayed at top of each CLI command
  - Option `-q` / `--quiet` to disable display

- **Product injection tracking**
  - Tracking in configuration (date, entity count, vintage, layers)
  - YAML configuration for products to import with historization

### Changed

- CLI commands restructured under `pgboundary config`
- `SimilarityMethod`: Added `COMBINED` method (new default value)
- `HistorizationConfig`: Now uses `SimilarityThresholds` instead of simple threshold
- `GeometryMatcher.find_matches()`: Now returns 4 lists
  - `auto_matches`: Automatic matches (IDENTICAL)
  - `removed`: Removed features
  - `added`: Added features
  - `needs_validation`: Matches requiring validation (LIKELY_MATCH, SUSPECT)
- `HistorizationManager`: Support for new thresholds and combined method

### Removed

- Command `pgboundary setup-db` (replaced by `pgboundary config db`)
- Options `--interactive` and `--show` from `config` command (replaced by subcommands)

### Deprecated

- Simple `threshold` parameter in `HistorizationConfig` (use `thresholds` instead)
- `threshold` parameter in `GeometryMatcher` (use `thresholds` instead)
- Function `compute_similarity_score()` (use `compute_similarity()` instead)

## [0.2.0] - 2026-02-07

### Added

- **Multi-product IGN architecture**
  - Product catalog (`ProductCatalog`, `IGNProduct`, `LayerConfig`)
  - Support for 5 Admin Express variants (EXPRESS, COG, COG-CARTO, COG-CARTO PE, COG-CARTO PLUS PE)
  - Support for 7 additional IGN products:
    - IRIS Contours (INSEE sub-municipal divisions)
    - BD FORET (forest land cover)
    - Forest Mask
    - BD CARTO (multi-theme cartographic database)
    - ADRESSE PREMIUM (enriched address points)
    - BAN PLUS (enriched national address database)
    - BCAE (good agricultural and environmental conditions)

- **Postal code support** (4 sources)
  - BAN Contours (official GeoJSON, 2021)
  - La Poste Database (CSV with postal code/INSEE correspondence, updated 2x/year)
  - Geoclip Basemap (Shapefile, 2013, mainland only)
  - Voronoi Generation (local tessellation from La Poste + AdminExpress)

- **Generic `ProductLoader`**
  - Unified loading for all IGN products
  - SHP and GPKG format support
  - Multi-territory management (FRA, FXX, GLP, MTQ, GUF, REU, MYT)

- **Specialized `CodesPostauxLoader`**
  - Support for 4 postal code sources
  - Voronoi generation with scipy (optional dependency)
  - Warnings about each source's limitations

- **New CLI commands**
  - `pgboundary products`: List available IGN products
  - `pgboundary product-info <id>`: Product details
  - `pgboundary load-product <id>`: Generic product loading

- **Extended configuration**
  - Tables for all new products in `schema_config.py`
  - Optional `[voronoi]` dependency for scipy

### Changed

- `AdminExpressLoader` now inherits from `ProductLoader`
- `IGNDataSource` refactored with abstract `DataSource` interface
- `download_legacy()` method for CLI backward compatibility

## [0.1.0] - 2026-02-07

### Added
- **Interactive CLI** with Rich for better user experience
  - `pgboundary config`: Configuration management
  - `pgboundary init`: Database schema initialization
  - `pgboundary download`: Admin Express data download
  - `pgboundary load`: Data loading into PostgreSQL
  - `pgboundary check`: Database connection verification
  - `pgboundary info`: Current configuration display

- **French administrative levels support**
  - Regions
  - Departments
  - EPCI (Intercommunal Cooperation Establishments)
  - Municipalities
  - Associated and delegated municipalities

- **Flexible configuration**
  - YAML configuration file (`pgboundary.yml`)
  - Schema mode: tables in dedicated schema
  - Prefix mode: tables with prefix in public schema
  - Configurable column naming conventions (`cd_*`, `lb_*`, `dt_*`)

- **Technical features**
  - Automatic download from IGN geoservices
  - UUID primary keys for all entities
  - WGS84 (EPSG:4326) coordinate system by default
  - Configurable SRID support
  - Complete type hints
  - Configuration via pydantic-settings

- **Dependencies**
  - Python 3.11+
  - PostgreSQL 12+ with PostGIS
  - GeoPandas, SQLAlchemy, GeoAlchemy2
  - Typer, Rich for CLI

### Documentation
- README in English and French
- Installation guide
- Development guide
- Contribution guide

---

## Change Types

- **Added**: New features
- **Changed**: Changes in existing features
- **Deprecated**: Features that will be removed soon
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Vulnerability fixes
