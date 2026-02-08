# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**[English version](ChangeLog.md)**

## [Non publié]

## [0.4.0] - 2026-02-08

### Ajouté

- **Changelog bilingue**
  - `ChangeLog.md` (anglais, par défaut)
  - `ChangeLog.fr.md` (français)
  - Liens croisés entre les versions

### Corrigé

- **Fix #1 :** `save_config()` sérialise les enums correctement
  - Utilisation de `model_dump(mode="json")` pour convertir les enums en chaînes
  - Évite `ConstructorError` lors du chargement YAML avec `safe_load()`

## [0.3.0] - 2026-02-07

### Ajouté

- **Nouveau produit : Circonscriptions législatives**
  - Produit `circonscriptions-legislatives` (577 circonscriptions en France)
  - Nouvelle catégorie de produits : `electoral`
  - Source : data.gouv.fr (découpage inchangé depuis 2012)

- **Affichage des tailles de produits**
  - Taille approximative affichée dans `pgboundary products`
  - Taille documentée dans les README (Ko, Mo, Go selon l'unité appropriée)

- **Système de comparaison géométrique combiné**
  - Nouvelle méthode `COMBINED` (recommandée) qui combine IoU et Hausdorff
  - Logique séquentielle : calcul IoU d'abord, puis Hausdorff si nécessaire
  - Utilise Shapely pour toutes les opérations géométriques

- **Matrice de décision pour la similarité**
  - `IDENTICAL` [0.95 - 1.00] : Fusion automatique sans vérification
  - `LIKELY_MATCH` [0.80 - 0.95] : Correspondance forte, validation si attributs diffèrent
  - `SUSPECT` [0.50 - 0.80] : Conflit potentiel ou changement temporel
  - `DISTINCT` [< 0.50] : Objets distincts

- **Nouvelles structures de données** (`import_config.py`)
  - `SimilarityLevel` : Énumération des 4 niveaux de similarité
  - `SimilarityResult` : Résultat détaillé avec score IoU, distance Hausdorff, score combiné
  - `SimilarityThresholds` : Seuils configurables de la matrice de décision

- **Fonctions de calcul** (`geometry_compare.py`)
  - `compute_combined_similarity()` : Logique séquentielle IoU puis Hausdorff
  - `compute_similarity()` : Fonction principale retournant un `SimilarityResult`
  - `_compute_combined_score()` : Score normalisé pondéré (70% IoU, 30% Hausdorff)

- **Commandes CLI de configuration**
  - `pgboundary config` : Afficher un résumé de la configuration
  - `pgboundary config info` : Afficher la configuration YAML formatée
  - `pgboundary config init` : Créer la configuration de manière interactive
  - `pgboundary config update` : Modifier la configuration existante
  - `pgboundary config db` : Configurer la connexion à la base de données
  - `pgboundary config data add` : Ajouter des produits de manière interactive
  - `pgboundary config data remove` : Supprimer des produits (interactif ou direct)
  - `pgboundary config sync-product` : Synchroniser le statut d'injection avec la base

- **Commande d'inspection**
  - `pgboundary inspect` : Inspecter les tables géographiques
  - Options `--summary`, `--detailed`, `--full` pour différents niveaux de détail
  - Option `--table` pour inspecter une table spécifique

- **Indicateur de base de données**
  - Affichage de la base de données active en haut de chaque commande CLI
  - Option `-q` / `--quiet` pour désactiver l'affichage

- **Suivi d'injection des produits**
  - Traçage dans la configuration (date, nombre d'entités, millésime, couches)
  - Configuration YAML des produits à importer avec historisation

### Modifié

- Restructuration des commandes CLI sous `pgboundary config`
- `SimilarityMethod` : Ajout de la méthode `COMBINED` (nouvelle valeur par défaut)
- `HistorizationConfig` : Utilise maintenant `SimilarityThresholds` au lieu d'un simple seuil
- `GeometryMatcher.find_matches()` : Retourne maintenant 4 listes
  - `auto_matches` : Correspondances automatiques (IDENTICAL)
  - `removed` : Features supprimées
  - `added` : Features ajoutées
  - `needs_validation` : Correspondances à valider (LIKELY_MATCH, SUSPECT)
- `HistorizationManager` : Support des nouveaux seuils et de la méthode combinée

### Supprimé

- Commande `pgboundary setup-db` (remplacée par `pgboundary config db`)
- Options `--interactive` et `--show` de la commande `config` (remplacées par sous-commandes)

### Déprécié

- Paramètre `threshold` simple dans `HistorizationConfig` (utiliser `thresholds` à la place)
- Paramètre `threshold` dans `GeometryMatcher` (utiliser `thresholds` à la place)
- Fonction `compute_similarity_score()` (utiliser `compute_similarity()` à la place)

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
