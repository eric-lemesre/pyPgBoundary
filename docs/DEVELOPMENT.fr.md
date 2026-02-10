# Guide de développement

**[English version](DEVELOPMENT.md)**

## Configuration de l'environnement de développement

### Prérequis

- Python 3.11+
- Git
- PostgreSQL avec PostGIS (pour les tests d'intégration)
- 7-Zip

### Clonage et configuration

```bash
# Cloner le dépôt
git clone https://github.com/eric/pgboundary.git
cd pgboundary

# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou
.venv\Scripts\activate     # Windows

# Installer avec les dépendances de développement
pip install -e ".[dev]"

# Installer les hooks pre-commit
pre-commit install
```

## Structure du projet

```
pgboundary/
├── src/pgboundary/          # Package principal
│   ├── __init__.py            # Point d'entrée du package
│   ├── cli.py                 # Interface en ligne de commande
│   ├── config.py              # Gestion des paramètres
│   ├── schema_config.py       # Configuration YAML
│   ├── exceptions.py          # Exceptions personnalisées
│   ├── db/                    # Couche base de données
│   │   ├── connection.py      # Gestionnaire de connexion
│   │   └── models.py          # Modèles SQLAlchemy
│   ├── loaders/               # Chargeurs de données
│   │   ├── base.py            # Chargeur de base abstrait
│   │   └── admin_express.py   # Chargeur IGN Admin Express
│   ├── sources/               # Sources de données
│   │   └── ign.py             # Gestionnaire de téléchargement IGN
│   └── types/                 # Définitions de types
│       └── boundaries.py      # Modèles Pydantic
├── tests/                     # Suite de tests
├── docs/                      # Documentation
├── pyproject.toml             # Configuration du projet
└── pgboundary.yml           # Configuration par défaut
```

## Style de code

### Formatage et linting

Nous utilisons [Ruff](https://docs.astral.sh/ruff/) pour le linting et le formatage :

```bash
# Vérifier le style de code
ruff check src/ tests/

# Corriger automatiquement
ruff check --fix src/ tests/

# Formater le code
ruff format src/ tests/
```

### Vérification des types

Nous utilisons [mypy](https://mypy.readthedocs.io/) en mode strict :

```bash
mypy src/
```

### Hooks pre-commit

Les hooks pre-commit s'exécutent automatiquement à chaque commit pour garantir la qualité du code.

#### Installation

```bash
# Installer les hooks (à exécuter une fois après le clonage)
pre-commit install
```

#### Hooks disponibles

| Hook | Description | Auto-fix |
|------|-------------|----------|
| `trailing-whitespace` | Supprime les espaces en fin de ligne | ✅ Oui |
| `end-of-file-fixer` | Assure que les fichiers finissent par un saut de ligne | ✅ Oui |
| `check-yaml` | Valide la syntaxe YAML | ❌ Non |
| `check-toml` | Valide la syntaxe TOML | ❌ Non |
| `check-added-large-files` | Empêche les commits de gros fichiers | ❌ Non |
| `ruff` | Linting + auto-correction | ✅ Oui |
| `ruff-format` | Formatage du code | ✅ Oui |
| `mypy` | Vérification des types | ❌ Non |

#### Utilisation

```bash
# Exécuter sur tous les fichiers (recommandé avant une PR)
pre-commit run --all-files

# Exécuter un hook spécifique
pre-commit run ruff --all-files

# Mettre à jour les hooks vers les dernières versions
pre-commit autoupdate
```

#### Quand les hooks modifient des fichiers

Si un hook modifie des fichiers (auto-fix), le commit est **annulé**. C'est le comportement attendu :

```bash
# 1. Tentative de commit → hooks exécutés → fichiers modifiés → commit annulé
git commit -m "mes modifications"

# 2. Vérifier les changements effectués par les hooks
git diff

# 3. Stager et commiter à nouveau
git add -u && git commit -m "mes modifications"
```

#### Ignorer les hooks (déconseillé)

```bash
# Ignorer tous les hooks (urgence uniquement)
git commit --no-verify -m "message"

# Ignorer un hook spécifique
SKIP=mypy git commit -m "message"
```

## Tests

### Exécution des tests

```bash
# Exécuter tous les tests
pytest

# Exécuter avec la couverture
pytest --cov=pgboundary --cov-report=html

# Exécuter un fichier de test spécifique
pytest tests/test_config.py

# Exécuter avec sortie détaillée
pytest -v
```

### Base de données de test

Pour les tests d'intégration, configurez une base de données de test :

```bash
export PGBOUNDARY_DATABASE_URL=postgresql://test:test@localhost:5432/test_boundaries
```

### Écriture des tests

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

### Couche de configuration

```
Settings (pydantic-settings)
    └── SchemaConfig (YAML)
            ├── StorageConfig
            ├── FieldPrefixes
            └── TableNames
```

### Couche base de données

```
DatabaseManager
    ├── Engine (SQLAlchemy)
    ├── SessionFactory
    └── TableFactory
            └── Génération dynamique des tables
```

### Couche de chargement

```
BaseLoader (abstrait)
    └── AdminExpressLoader
            ├── IGNDataSource (téléchargement)
            └── Traitement GeoDataFrame
```

## Ajout de nouvelles fonctionnalités

### Ajout d'une nouvelle couche administrative

1. Ajouter la fonction de création de table dans `db/models.py` :

```python
def create_new_layer_table(metadata: MetaData, config: SchemaConfig) -> Table:
    table_name = config.get_full_table_name("new_layer")
    fp = config.field_prefixes

    return Table(
        table_name,
        metadata,
        Column("uid", Uuid, primary_key=True, default=uuid.uuid4),
        Column(f"{fp.label}nom", String(255), nullable=False),
        # ... autres colonnes
        Column("geometry", Geometry("MULTIPOLYGON", srid=config.srid)),
    )
```

1. Ajouter à la classe `TableFactory`
2. Ajouter le mapping des colonnes dans `get_column_mapping()`
3. Ajouter à `LAYER_TO_TABLE_KEY` dans le loader
4. Mettre à jour `TableNames` dans `schema_config.py`

### Ajout d'une nouvelle source de données

1. Créer la nouvelle source dans `sources/` :

```python
# sources/new_source.py
class NewDataSource:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def download(self, **kwargs) -> Path:
        # Logique de téléchargement
        pass
```

1. Créer le loader correspondant dans `loaders/`

## Processus de release

### Mise à jour de version

1. Mettre à jour la version dans `src/pgboundary/__init__.py`
2. Mettre à jour CHANGELOG.md
3. Commit : `git commit -m "Bump version to X.Y.Z"`
4. Tag : `git tag vX.Y.Z`
5. Push : `git push && git push --tags`

### Construction de la distribution

```bash
# Construire le package
python -m build

# Vérifier le package
twine check dist/*
```

## Directives de contribution

### Processus de Pull Request

1. Forker le dépôt
2. Créer une branche de fonctionnalité : `git checkout -b feature/ma-fonctionnalite`
3. Effectuer les modifications et ajouter des tests
4. Exécuter le linting et les tests : `ruff check && pytest`
5. Commiter avec un message descriptif
6. Pousser et créer une Pull Request

### Messages de commit

Suivre les conventional commits :

```
feat: ajouter le support d'une nouvelle couche administrative
fix: corriger le mapping des colonnes pour les EPCI
docs: mettre à jour le guide d'installation
test: ajouter des tests pour le chargement de configuration
refactor: simplifier la gestion de connexion à la base
```

### Checklist de revue de code

- [ ] Le code suit le guide de style du projet
- [ ] Tous les tests passent
- [ ] Les nouvelles fonctionnalités ont des tests
- [ ] La documentation est mise à jour
- [ ] Les hints de type sont complets
- [ ] Pas de vulnérabilités de sécurité

## Licence

Ce projet est sous licence GPL v3. Toutes les contributions doivent être compatibles avec cette licence.

Lors de l'ajout de nouveaux fichiers, inclure l'en-tête de licence :

```python
# pyPgBoundary - Limites administratives françaises pour PostgreSQL
# Copyright (C) 2024 Eric
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou
# le modifier selon les termes de la licence GNU General Public License
# telle que publiée par la Free Software Foundation, soit la version 3
# de la licence, soit (à votre choix) toute version ultérieure.
```
