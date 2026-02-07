# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Non publié]

### En cours
- Développement initial du projet

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
