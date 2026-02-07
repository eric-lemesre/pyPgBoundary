# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Non publié]

## [0.2.0] - 2026-02-07

### Ajouté

- **Architecture multi-produits IGN**
  - Catalogue de produits (`ProductCatalog`, `IGNProduct`, `LayerConfig`)
  - Support de 5 variantes Admin Express (EXPRESS, COG, COG-CARTO, COG-CARTO PE, COG-CARTO PLUS PE)
  - Support de 7 produits IGN additionnels :
    - Contours IRIS (découpage infra-communal INSEE)
    - BD FORÊT (occupation du sol forestier)
    - Masque FORÊT
    - BD CARTO (base cartographique multi-thèmes)
    - ADRESSE PREMIUM (points adresse enrichis)
    - BAN PLUS (base adresse nationale enrichie)
    - BCAE (bonnes conditions agricoles et environnementales)

- **Support des codes postaux** (4 sources)
  - Contours BAN (GeoJSON officiel, 2021)
  - Base La Poste (CSV avec correspondance CP/INSEE, mise à jour 2x/an)
  - Fond de carte Géoclip (Shapefile, 2013, métropole uniquement)
  - Génération Voronoï (tessellation locale à partir de La Poste + AdminExpress)

- **Loader générique `ProductLoader`**
  - Chargement unifié pour tous les produits IGN
  - Support des formats SHP et GPKG
  - Gestion multi-territoires (FRA, FXX, GLP, MTQ, GUF, REU, MYT)

- **Loader spécialisé `CodesPostauxLoader`**
  - Support des 4 sources de codes postaux
  - Génération Voronoï avec scipy (dépendance optionnelle)
  - Avertissements sur les limitations de chaque source

- **Nouvelles commandes CLI**
  - `pgboundary products` : Liste des produits IGN disponibles
  - `pgboundary product-info <id>` : Détails d'un produit
  - `pgboundary load-product <id>` : Chargement générique d'un produit

- **Configuration étendue**
  - Tables pour tous les nouveaux produits dans `schema_config.py`
  - Dépendance optionnelle `[voronoi]` pour scipy

### Modifié

- `AdminExpressLoader` hérite maintenant de `ProductLoader`
- `IGNDataSource` refactorisé avec interface `DataSource` abstraite
- Méthode `download_legacy()` pour rétrocompatibilité CLI

## [0.1.0] - 2026-02-07

### Ajouté
- **CLI interactive** avec Rich pour une meilleure expérience utilisateur
  - `pgboundary config` : Gestion de la configuration
  - `pgboundary init` : Initialisation du schéma de base de données
  - `pgboundary download` : Téléchargement des données Admin Express
  - `pgboundary load` : Chargement des données dans PostgreSQL
  - `pgboundary check` : Vérification de la connexion à la base
  - `pgboundary info` : Affichage de la configuration actuelle

- **Support des niveaux administratifs français**
  - Régions
  - Départements
  - EPCI (Établissements Publics de Coopération Intercommunale)
  - Communes
  - Communes associées et déléguées

- **Configuration flexible**
  - Fichier de configuration YAML (`pgboundary.yml`)
  - Mode schéma : tables dans un schéma dédié
  - Mode préfixe : tables avec préfixe dans le schéma public
  - Conventions de nommage des colonnes configurables (`cd_*`, `lb_*`, `dt_*`)

- **Fonctionnalités techniques**
  - Téléchargement automatique depuis les géoservices IGN
  - Clés primaires UUID pour toutes les entités
  - Système de coordonnées WGS84 (EPSG:4326) par défaut
  - Support de SRID configurable
  - Type hints complets
  - Configuration via pydantic-settings

- **Dépendances**
  - Python 3.11+
  - PostgreSQL 12+ avec PostGIS
  - GeoPandas, SQLAlchemy, GeoAlchemy2
  - Typer, Rich pour la CLI

### Documentation
- README en anglais et français
- Guide d'installation
- Guide de développement
- Guide de contribution

---

## Types de changements

- **Ajouté** : Nouvelles fonctionnalités
- **Modifié** : Changements dans les fonctionnalités existantes
- **Déprécié** : Fonctionnalités qui seront supprimées prochainement
- **Supprimé** : Fonctionnalités supprimées
- **Corrigé** : Corrections de bugs
- **Sécurité** : Corrections de vulnérabilités
