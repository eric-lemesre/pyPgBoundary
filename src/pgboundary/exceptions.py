"""Exceptions personnalisées du module pyPgBoundary."""


class PyPgBoundaryError(Exception):
    """Exception de base pour pyPgBoundary."""


class DatabaseError(PyPgBoundaryError):
    """Erreur liée à la base de données."""


class ConnectionError(DatabaseError):
    """Erreur de connexion à la base de données."""


class DatabaseNotFoundError(ConnectionError):
    """La base de données spécifiée n'existe pas."""


class SchemaError(DatabaseError):
    """Erreur liée au schéma de la base de données."""


class DownloadError(PyPgBoundaryError):
    """Erreur lors du téléchargement des données."""


class DataSourceError(PyPgBoundaryError):
    """Erreur liée à la source de données."""


class ValidationError(PyPgBoundaryError):
    """Erreur de validation des données."""


class LoaderError(PyPgBoundaryError):
    """Erreur lors du chargement des données."""


class AtomApiError(DataSourceError):
    """Erreur de communication avec l'API Atom."""
