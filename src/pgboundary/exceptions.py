"""Custom exceptions for the pyPgBoundary module."""


class PyPgBoundaryError(Exception):
    """Base exception for pyPgBoundary."""


class DatabaseError(PyPgBoundaryError):
    """Database-related error."""


class ConnectionError(DatabaseError):
    """Database connection error."""


class DatabaseNotFoundError(ConnectionError):
    """The specified database does not exist."""


class SchemaError(DatabaseError):
    """Database schema-related error."""


class DownloadError(PyPgBoundaryError):
    """Error during data download."""


class DataSourceError(PyPgBoundaryError):
    """Data source-related error."""


class ValidationError(PyPgBoundaryError):
    """Data validation error."""


class LoaderError(PyPgBoundaryError):
    """Error during data loading."""


class AtomApiError(DataSourceError):
    """Atom API communication error."""
