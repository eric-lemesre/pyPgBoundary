# pyPgBoundary

[![CI](https://github.com/eric-lemesre/pyPgBoundary/actions/workflows/ci.yml/badge.svg)](https://github.com/eric-lemesre/pyPgBoundary/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/eric-lemesre/pyPgBoundary/graph/badge.svg)](https://codecov.io/gh/eric-lemesre/pyPgBoundary)
[![Licence : GPL v3](https://img.shields.io/badge/Licence-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-336791.svg)](https://postgis.net/)

**[English version](README.md)**

Module Python pour charger les limites administratives françaises dans une base de données PostgreSQL/PostGIS.

## Présentation

pyPgBoundary automatise le téléchargement et l'import des données de limites administratives françaises depuis
le jeu de données Admin Express de l'IGN (Institut Géographique National) vers une base de données PostgreSQL
avec l'extension PostGIS.

### Niveaux administratifs supportés

- **Régions**
- **Départements**
- **EPCI** (Établissements Publics de Coopération Intercommunale)
- **Communes**
- **Communes associées/déléguées**

## Produits IGN supportés

pyPgBoundary supporte 18 produits organisés en 6 catégories.

### Limites administratives

| Produit | Taille | Description |
|---------|-------:|-------------|
| `admin-express` | 400 Mo | Limites administratives simplifiées (version 3-2) |
| `admin-express-cog` | 500 Mo | Avec Code Officiel Géographique (COG) |
| `admin-express-cog-carto` | 550 Mo | Version cartographique avec chefs-lieux |
| `admin-express-cog-carto-pe` | 200 Mo | Version cartographique petite échelle |
| `admin-express-cog-carto-plus-pe` | 250 Mo | Version enrichie avec cantons |

**Couches** : REGION, DEPARTEMENT, ARRONDISSEMENT, EPCI, COMMUNE, COMMUNE_ASSOCIEE_OU_DELEGUEE, CANTON, COLLECTIVITE_TERRITORIALE, ARRONDISSEMENT_MUNICIPAL, CHEF_LIEU_*

### Données statistiques

| Produit | Taille | Description |
|---------|-------:|-------------|
| `contours-iris` | 150 Mo | Contours IRIS - divisions statistiques infra-communales (communes >10 000 hab.) |

### Circonscriptions électorales

| Produit | Taille | Description |
|---------|-------:|-------------|
| `circonscriptions-legislatives` | 10 Mo | Circonscriptions législatives (577 en France, découpage 2012) |
| `bureaux-de-vote` | 645 Mo | Contours des bureaux de vote (~69 000, Voronoï depuis le REU) |

### Occupation du sol

| Produit | Taille | Description |
|---------|-------:|-------------|
| `bd-foret` | 2.5 Go | Formations végétales forestières et occupation du sol |
| `masque-foret` | 300 Mo | Masque simplifié des zones forestières |
| `bcae` | 800 Mo | Bonnes Conditions Agricoles et Environnementales (haies, prairies, mares) |

### Adresses et codes postaux

| Produit | Taille | Description |
|---------|-------:|-------------|
| `codes-postaux-ban` | 50 Mo | Contours des codes postaux (enveloppes convexes BAN) |
| `codes-postaux-laposte` | 2 Mo | Base officielle La Poste (points/centroïdes) |
| `codes-postaux-geoclip` | 15 Mo | Fond de carte Géoclip (métropole uniquement) |
| `codes-postaux-generated` | ~100 Mo | Contours générés par Voronoï (calcul local) |
| `adresse-premium` | 4 Go | Points adresses géolocalisés et enrichis |
| `ban-plus` | 3 Go | Base Adresse Nationale enrichie par l'IGN |

### Cartographie

| Produit | Taille | Description |
|---------|-------:|-------------|
| `bd-carto` | 1.2 Go | Base cartographique multi-thèmes (limites, zones d'activité, équipements) |

### Territoires disponibles

| Code | Territoire |
|------|------------|
| `FRA` | France entière |
| `FXX` | France métropolitaine |
| `GLP` | Guadeloupe |
| `MTQ` | Martinique |
| `GUF` | Guyane française |
| `REU` | La Réunion |
| `MYT` | Mayotte |

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

### Vue d'ensemble

Les commandes sont organisées par workflow :

**Configuration**
| Commande | Description |
|----------|-------------|
| `pgboundary config` | Gérer la configuration (schéma, DB, produits) |
| `pgboundary check` | Vérifier la connexion à la base |
| `pgboundary init` | Initialiser le schéma et les tables |

**Produits & Données**
| Commande | Description |
|----------|-------------|
| `pgboundary products` | Lister les produits IGN disponibles |
| `pgboundary product-info` | Afficher les détails d'un produit |
| `pgboundary download` | Télécharger les données Admin Express |
| `pgboundary load` | Charger les données selon la configuration |
| `pgboundary load-product` | Charger un produit spécifique |

**Utilitaires**
| Commande | Description |
|----------|-------------|
| `pgboundary info` | Afficher la configuration actuelle |
| `pgboundary inspect` | Inspecter les tables géographiques |
| `pgboundary completion` | Gérer la complétion shell |

**Note** : Une indication de la base de données active s'affiche en haut de chaque commande. Utilisez `-q` pour la désactiver.

### Configuration (`pgboundary config`)

```bash
# Afficher un résumé de la configuration
pgboundary config

# Afficher la configuration complète formatée
pgboundary config info

# Créer la configuration de manière interactive
pgboundary config init
pgboundary config init --force    # Écraser le fichier existant

# Modifier la configuration existante
pgboundary config update

# Configurer la connexion à la base de données
pgboundary config db

# Gestion des produits à importer (arborescence interactive)
pgboundary config data                              # Vue arborescente (défaut)
pgboundary config data update                       # Idem, navigation interactive
pgboundary config data add                          # Ajouter des produits
pgboundary config data remove                       # Mode interactif
pgboundary config data remove admin-express-cog     # Suppression directe
pgboundary config data remove prod1 prod2 prod3     # Suppression multiple

# Synchroniser le statut d'injection avec la base de données
pgboundary config sync-product                      # Tous les produits
pgboundary config sync-product admin-express-cog    # Produit spécifique
```

### Inspection des tables géographiques (`pgboundary inspect`)

```bash
pgboundary inspect                    # Résumé (défaut)
pgboundary inspect --summary          # Résumé : lignes, type géométrie, SRID
pgboundary inspect --detailed         # Détaillé : + colonnes, index, taille
pgboundary inspect --full             # Complet : + statistiques, extent
pgboundary inspect --table commune    # Table spécifique
```

### Vérification de la connexion

```bash
# Vérifier la connexion et PostGIS
pgboundary check
pgboundary check --database-url "postgresql://user:pass@localhost:5432/db"
```

### Initialisation de la base de données (`pgboundary init`)

```bash
pgboundary init                           # Utilise la configuration existante
pgboundary init --interactive             # Mode interactif
pgboundary init --database-url "..."      # Spécifier l'URL de connexion
pgboundary init --config /path/to/config.yml
pgboundary init --verbose                 # Mode verbeux
```

### Téléchargement des données (`pgboundary download`)

```bash
pgboundary download                                      # France métropolitaine 2024
pgboundary download --territory france_entiere          # France entière (avec DOM-TOM)
pgboundary download --year 2023                          # Année spécifique
pgboundary download --force                              # Forcer le re-téléchargement
pgboundary download --verbose                            # Mode verbeux
```

### Chargement des données (`pgboundary load`)

```bash
pgboundary load                      # Affiche la config et demande validation
pgboundary load --all                # Importe tous les produits activés
pgboundary load --product admin-express-cog   # Importe un seul produit
pgboundary load --config /path/to/config.yml
pgboundary load --verbose
```

### Catalogue des produits IGN

```bash
# Lister tous les produits disponibles
pgboundary products
pgboundary products --verbose        # Avec plus de détails

# Filtrer par catégorie
pgboundary products --category admin      # Limites administratives
pgboundary products --category stats      # Données statistiques (IRIS, etc.)
pgboundary products --category land       # Occupation du sol
pgboundary products --category address    # Adresses
pgboundary products --category carto      # Données cartographiques

# Détails d'un produit spécifique
pgboundary product-info admin-express-cog
pgboundary product-info contours-iris
```

### Chargement d'un produit (`pgboundary load-product`)

```bash
pgboundary load-product admin-express-cog               # Charger Admin Express
pgboundary load-product contours-iris --territory FXX   # Métropole uniquement
pgboundary load-product admin-express-cog --format gpkg # Format GeoPackage
pgboundary load-product admin-express-cog --year 2023
pgboundary load-product admin-express-cog --layers "REGION,DEPARTEMENT"
pgboundary load-product admin-express-cog --replace     # Remplacer les tables
pgboundary load-product admin-express-cog --database-url "..."
pgboundary load-product admin-express-cog --verbose
```

### Options globales

| Option | Description |
|--------|-------------|
| `--version`, `-v` | Affiche la version de pgboundary |
| `--verbose`, `-V` | Active le mode verbeux (logging DEBUG) |
| `--config`, `-c` | Chemin du fichier de configuration |
| `--database-url`, `-d` | URL de connexion PostgreSQL |
| `--quiet`, `-q` | Désactive l'affichage du statut de la base |
| `--install-completion` | Installe la complétion shell |
| `--show-completion` | Affiche le script de complétion shell |

### Complétion Shell (`pgboundary completion`)

Active la complétion par tabulation pour bash, zsh, fish ou PowerShell.

```bash
# Installation rapide (détecte le shell automatiquement)
pgboundary completion install

# Afficher le script de complétion pour un shell spécifique
pgboundary completion show bash
pgboundary completion show zsh
pgboundary completion show fish
pgboundary completion show powershell

# Vérifier le statut de la complétion pour tous les shells
pgboundary completion status
```

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
