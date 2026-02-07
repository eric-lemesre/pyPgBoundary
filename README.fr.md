# pyPgBoundary

[![Licence : GPL v3](https://img.shields.io/badge/Licence-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-336791.svg)](https://postgis.net/)

**[English version](README.md)**

Module Python pour charger les limites administratives françaises dans une base de données PostgreSQL/PostGIS.

## Présentation

pyPgBoundary automatise le téléchargement et l'import des données de limites administratives françaises depuis le jeu de données Admin Express de l'IGN (Institut Géographique National) vers une base de données PostgreSQL avec l'extension PostGIS.

### Niveaux administratifs supportés

- **Régions**
- **Départements**
- **EPCI** (Établissements Publics de Coopération Intercommunale)
- **Communes**
- **Communes associées/déléguées**

## Fonctionnalités

- Téléchargement automatique depuis les Géoservices de l'IGN
- Schéma de base de données configurable (schéma dédié ou préfixe de table)
- Conventions de nommage standardisées (`cd_*`, `lb_*`, `dt_*`)
- Clés primaires UUID pour toutes les entités
- Système de coordonnées WGS84 (EPSG:4326) par défaut
- CLI interactive avec formatage Rich
- Fichier de configuration YAML
- Typage complet et pratiques Python modernes

## Démarrage rapide

```bash
# Installer le package
pip install pgboundary

# Créer la configuration de manière interactive
pgboundary config --interactive

# Initialiser la base de données
pgboundary init

# Télécharger et charger les données
pgboundary load
```

## Prérequis

- Python 3.11+
- PostgreSQL 12+ avec l'extension PostGIS
- 7-Zip (pour extraire les archives IGN)

## Documentation

- [Guide d'installation](docs/INSTALL.fr.md)
- [Guide de développement](docs/DEVELOPMENT.fr.md)

## Schéma de base de données

### Modes de stockage

**Mode schema** (par défaut) : Les tables sont créées dans un schéma dédié
```
geo.region
geo.departement
geo.commune
...
```

**Mode prefix** : Les tables sont créées dans le schéma `public` avec un préfixe
```
public.geo_region
public.geo_departement
public.geo_commune
...
```

### Conventions de nommage des colonnes

| Type | Préfixe | Exemples |
|------|---------|----------|
| Codes | `cd_` | `cd_insee`, `cd_postal`, `cd_region` |
| Libellés | `lb_` | `lb_nom`, `lb_nature` |
| Dates | `dt_` | `dt_creation`, `dt_modification` |
| ID | `uid` | UUID, auto-généré |

## Configuration

La configuration est stockée dans `pgboundary.yml` :

```yaml
storage:
  mode: schema        # 'schema' ou 'prefix'
  schema_name: geo    # Nom du schéma PostgreSQL
  table_prefix: geo_  # Préfixe des tables (si mode = 'prefix')

field_prefixes:
  code: cd_
  label: lb_
  date: dt_

srid: 4326
```

## Commandes CLI

| Commande | Description |
|----------|-------------|
| `pgboundary config` | Gérer le fichier de configuration |
| `pgboundary init` | Initialiser le schéma et les tables |
| `pgboundary download` | Télécharger les données Admin Express |
| `pgboundary load` | Charger les données dans PostgreSQL |
| `pgboundary check` | Vérifier la connexion à la base |
| `pgboundary info` | Afficher la configuration actuelle |

## API Python

```python
from pgboundary import Settings, AdminExpressLoader

# Charger avec les paramètres par défaut
loader = AdminExpressLoader()
loader.load()

# Charger des couches spécifiques
loader.load_regions()
loader.load_departements()
loader.load_communes()
```

## Source des données

Les données proviennent de [IGN Admin Express COG](https://geoservices.ign.fr/adminexpress), le référentiel géographique officiel du gouvernement français.

## Licence

Ce projet est sous licence GNU General Public License v3.0 - voir le fichier [LICENSE](LICENSE) pour plus de détails.

## Contribuer

Les contributions sont les bienvenues ! Veuillez lire [DEVELOPMENT.fr.md](docs/DEVELOPMENT.fr.md) pour les directives.

## Remerciements

- [IGN](https://www.ign.fr/) pour la fourniture du jeu de données Admin Express
- [PostGIS](https://postgis.net/) pour les capacités de base de données spatiale
- [GeoPandas](https://geopandas.org/) pour le traitement des données géospatiales
