# Installation Guide

**[Version française](INSTALL.fr.md)**

## Prerequisites

### System Requirements

- **Python**: 3.11 or higher
- **PostgreSQL**: 12 or higher with PostGIS extension
- **7-Zip**: Required for extracting IGN archives

### Database Setup

Ensure PostgreSQL is installed and running with the PostGIS extension:

```sql
-- Connect to your database
CREATE EXTENSION IF NOT EXISTS postgis;

-- Verify PostGIS installation
SELECT PostGIS_Version();
```

### Installing 7-Zip

**Debian/Ubuntu:**
```bash
sudo apt-get install p7zip-full
```

**Fedora/RHEL:**
```bash
sudo dnf install p7zip p7zip-plugins
```

**macOS:**
```bash
brew install p7zip
```

**Windows:**
Download from [7-zip.org](https://www.7-zip.org/) and ensure it's in your PATH.

## Installation Methods

### From PyPI (Recommended)

```bash
pip install pgboundary
```

### From Source

```bash
# Clone the repository
git clone https://github.com/eric/pgboundary.git
cd pgboundary

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install in development mode
pip install -e ".[dev]"
```

### Using pipx (Isolated Installation)

```bash
pipx install pgboundary
```

## Configuration

### Environment Variables

Create a `.env` file in your working directory:

```bash
# PostgreSQL connection URL
PGBOUNDARY_DATABASE_URL=postgresql://user:password@localhost:5432/boundaries

# Log level (DEBUG, INFO, WARNING, ERROR)
PGBOUNDARY_LOG_LEVEL=INFO

# Data directory for downloaded files
PGBOUNDARY_DATA_DIR=~/.pgboundary/data
```

### YAML Configuration

Create the configuration file interactively:

```bash
pgboundary config --interactive
```

Or create `pgboundary.yml` manually:

```yaml
storage:
  mode: schema          # 'schema' or 'prefix'
  schema_name: geo      # Schema name (if mode = 'schema')
  table_prefix: geo_    # Table prefix (if mode = 'prefix')

field_prefixes:
  code: cd_
  label: lb_
  date: dt_

srid: 4326
```

## Verification

### Check Installation

```bash
pgboundary --version
```

### Verify Database Connection

```bash
pgboundary check
```

Expected output:
```
Verifying connection...
✓ PostgreSQL connection OK
✓ PostGIS extension OK
All checks passed!
```

### Display Configuration

```bash
pgboundary info
```

## First Use

### 1. Initialize the Database

```bash
# With interactive configuration
pgboundary init --interactive

# Or with existing configuration
pgboundary init
```

### 2. Download Data

```bash
# Download metropolitan France data
pgboundary download --territory france_metropolitaine --year 2024
```

### 3. Load Data

```bash
# Load all layers
pgboundary load

# Or load specific layers
pgboundary load --layers REGION,DEPARTEMENT,COMMUNE
```

## Troubleshooting

### Connection Issues

**Error: "Could not connect to database"**
- Verify PostgreSQL is running
- Check connection URL in `.env` or environment
- Ensure database exists and user has permissions

### PostGIS Not Available

**Error: "PostGIS is not available"**
```sql
-- Install PostGIS extension
CREATE EXTENSION postgis;

-- If extension is not available, install PostGIS package
-- Debian/Ubuntu: sudo apt-get install postgresql-15-postgis-3
```

### 7-Zip Not Found

**Error: "7z command not found"**
- Install 7-zip (see prerequisites)
- Ensure `7z` is in your PATH
- On Windows, you may need to add `C:\Program Files\7-Zip` to PATH

### Permission Denied

**Error: "Permission denied" when creating schema**
```sql
-- Grant necessary permissions
GRANT CREATE ON DATABASE boundaries TO your_user;
```

## Upgrading

```bash
# From PyPI
pip install --upgrade pgboundary

# From source
git pull
pip install -e ".[dev]"
```

## Uninstallation

```bash
pip uninstall pgboundary

# Remove configuration and data (optional)
rm -rf ~/.pgboundary
rm pgboundary.yml
```
