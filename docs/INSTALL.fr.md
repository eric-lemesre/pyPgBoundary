# Guide d'installation

**[English version](INSTALL.md)**

## Prérequis

### Configuration système requise

- **Python** : 3.11 ou supérieur
- **PostgreSQL** : 12 ou supérieur avec l'extension PostGIS
- **7-Zip** : Requis pour extraire les archives IGN

### Configuration de la base de données

Assurez-vous que PostgreSQL est installé et fonctionne avec l'extension PostGIS :

```sql
-- Connectez-vous à votre base de données
CREATE EXTENSION IF NOT EXISTS postgis;

-- Vérifier l'installation de PostGIS
SELECT PostGIS_Version();
```

### Installation de 7-Zip

**Debian/Ubuntu :**
```bash
sudo apt-get install p7zip-full
```

**Fedora/RHEL :**
```bash
sudo dnf install p7zip p7zip-plugins
```

**macOS :**
```bash
brew install p7zip
```

**Windows :**
Téléchargez depuis [7-zip.org](https://www.7-zip.org/) et assurez-vous qu'il est dans votre PATH.

## Méthodes d'installation

### Depuis PyPI (Recommandé)

```bash
pip install pgboundary
```

### Depuis les sources

```bash
# Cloner le dépôt
git clone https://github.com/eric/pgboundary.git
cd pgboundary

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou
.venv\Scripts\activate     # Windows

# Installer en mode développement
pip install -e ".[dev]"
```

### Avec pipx (Installation isolée)

```bash
pipx install pgboundary
```

## Configuration

### Variables d'environnement

Créez un fichier `.env` dans votre répertoire de travail :

```bash
# URL de connexion PostgreSQL
PGBOUNDARY_DATABASE_URL=postgresql://utilisateur:motdepasse@localhost:5432/boundaries

# Niveau de log (DEBUG, INFO, WARNING, ERROR)
PGBOUNDARY_LOG_LEVEL=INFO

# Répertoire de données pour les fichiers téléchargés
PGBOUNDARY_DATA_DIR=~/.pgboundary/data
```

### Configuration YAML

Créez le fichier de configuration de manière interactive :

```bash
pgboundary config --interactive
```

Ou créez `pgboundary.yml` manuellement :

```yaml
storage:
  mode: schema          # 'schema' ou 'prefix'
  schema_name: geo      # Nom du schéma (si mode = 'schema')
  table_prefix: geo_    # Préfixe des tables (si mode = 'prefix')

field_prefixes:
  code: cd_
  label: lb_
  date: dt_

srid: 4326
```

## Vérification

### Vérifier l'installation

```bash
pgboundary --version
```

### Vérifier la connexion à la base de données

```bash
pgboundary check
```

Sortie attendue :
```
Vérification de la connexion...
✓ Connexion PostgreSQL OK
✓ Extension PostGIS OK
Toutes les vérifications passées !
```

### Afficher la configuration

```bash
pgboundary info
```

## Première utilisation

### 1. Initialiser la base de données

```bash
# Avec configuration interactive
pgboundary init --interactive

# Ou avec une configuration existante
pgboundary init
```

### 2. Télécharger les données

```bash
# Télécharger les données de la France métropolitaine
pgboundary download --territory france_metropolitaine --year 2024
```

### 3. Charger les données

```bash
# Charger toutes les couches
pgboundary load

# Ou charger des couches spécifiques
pgboundary load --layers REGION,DEPARTEMENT,COMMUNE
```

## Dépannage

### Problèmes de connexion

**Erreur : "Impossible de se connecter à la base de données"**
- Vérifiez que PostgreSQL fonctionne
- Vérifiez l'URL de connexion dans `.env` ou l'environnement
- Assurez-vous que la base de données existe et que l'utilisateur a les permissions

### PostGIS non disponible

**Erreur : "PostGIS n'est pas disponible"**
```sql
-- Installer l'extension PostGIS
CREATE EXTENSION postgis;

-- Si l'extension n'est pas disponible, installez le paquet PostGIS
-- Debian/Ubuntu : sudo apt-get install postgresql-15-postgis-3
```

### 7-Zip non trouvé

**Erreur : "Commande 7z introuvable"**
- Installez 7-zip (voir prérequis)
- Assurez-vous que `7z` est dans votre PATH
- Sous Windows, vous devrez peut-être ajouter `C:\Program Files\7-Zip` au PATH

### Permission refusée

**Erreur : "Permission refusée" lors de la création du schéma**
```sql
-- Accorder les permissions nécessaires
GRANT CREATE ON DATABASE boundaries TO votre_utilisateur;
```

## Mise à jour

```bash
# Depuis PyPI
pip install --upgrade pgboundary

# Depuis les sources
git pull
pip install -e ".[dev]"
```

## Désinstallation

```bash
pip uninstall pgboundary

# Supprimer la configuration et les données (optionnel)
rm -rf ~/.pgboundary
rm pgboundary.yml
```
