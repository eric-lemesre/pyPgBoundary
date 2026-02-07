# Guide de contribution

Merci de votre intérêt pour contribuer à pyPgBoundary ! Ce document décrit les bonnes pratiques pour participer au projet.

## Comment contribuer

### Signaler un bug

1. Vérifiez que le bug n'a pas déjà été signalé dans les [issues](https://github.com/eric/pgboundary/issues)
2. Si ce n'est pas le cas, créez une nouvelle issue avec :
   - Une description claire du problème
   - Les étapes pour reproduire le bug
   - L'environnement (version Python, PostgreSQL, OS)
   - Les messages d'erreur complets

### Proposer une fonctionnalité

1. Ouvrez une issue pour discuter de la fonctionnalité proposée
2. Attendez une validation avant de commencer le développement
3. Les fonctionnalités doivent rester dans le périmètre du projet

### Soumettre du code

1. **Fork** le dépôt
2. **Créez une branche** à partir de `master` :
   ```bash
   git checkout -b feature/ma-fonctionnalite
   # ou
   git checkout -b fix/correction-bug
   ```
3. **Développez** en suivant les conventions du projet
4. **Testez** vos modifications
5. **Commitez** avec des messages clairs
6. **Ouvrez une Pull Request**

## Configuration de l'environnement

```bash
# Cloner le dépôt
git clone https://github.com/eric/pgboundary.git
cd pgboundary

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate

# Installer les dépendances de développement
pip install -e ".[dev]"

# Installer les hooks pre-commit
pre-commit install
```

## Standards de code

### Style

- **Formateur** : Ruff (configuré dans `pyproject.toml`)
- **Longueur de ligne** : 100 caractères maximum
- **Type hints** : Obligatoires pour toutes les fonctions publiques
- **Docstrings** : Format Google pour les fonctions et classes publiques

### Linting

```bash
# Vérifier le code
ruff check src/ tests/

# Formater automatiquement
ruff format src/ tests/

# Vérification des types
mypy src/
```

### Tests

```bash
# Lancer tous les tests
pytest

# Avec couverture
pytest --cov=pgboundary --cov-report=html

# Un test spécifique
pytest tests/test_loader.py -k "test_load_regions"
```

- Chaque nouvelle fonctionnalité doit être accompagnée de tests
- La couverture de code doit être maintenue au-dessus de 80%
- Les tests doivent pouvoir s'exécuter sans base de données réelle (mocks)

## Structure du projet

```
pgboundary/
├── src/pgboundary/     # Code source
│   ├── __init__.py
│   ├── cli.py            # Interface en ligne de commande
│   ├── config.py         # Configuration YAML
│   ├── database.py       # Connexion PostgreSQL
│   ├── downloader.py     # Téléchargement IGN
│   ├── loader.py         # Chargement des données
│   └── models.py         # Modèles SQLAlchemy
├── tests/                # Tests unitaires et d'intégration
├── docs/                 # Documentation
└── pyproject.toml        # Configuration du projet
```

## Conventions de commit

Utilisez des messages de commit clairs et descriptifs :

```
<type>(<portée>): <description courte>

<corps optionnel>
```

**Types** :
- `feat` : Nouvelle fonctionnalité
- `fix` : Correction de bug
- `docs` : Documentation
- `style` : Formatage, pas de changement de code
- `refactor` : Refactorisation
- `test` : Ajout ou modification de tests
- `chore` : Maintenance, dépendances

**Exemples** :
```
feat(loader): ajouter support des arrondissements
fix(database): corriger la connexion SSL
docs(readme): mettre à jour les exemples
```

## Pull Requests

- Une PR par fonctionnalité ou correction
- Description claire des changements
- Référencez l'issue liée (`Fixes #123`)
- Assurez-vous que les tests passent
- Mettez à jour la documentation si nécessaire
- Attendez la revue de code avant de merger

## Code de conduite

- Soyez respectueux et constructif
- Acceptez les critiques constructives
- Concentrez-vous sur ce qui est le mieux pour le projet
- Faites preuve d'empathie envers les autres contributeurs

## Licence

En contribuant, vous acceptez que vos contributions soient sous licence GPL v3.0.

## Questions

Pour toute question, ouvrez une issue ou contactez les mainteneurs.
