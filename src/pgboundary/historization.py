"""Geographic data historization module.

This module manages the historization of geographic entities during
the import of new vintage datasets.

Features:
- Addition of dt_debut and dt_fin columns
- Comparison with existing data
- Update of end dates for modified/deleted entities
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Any

import geopandas as gpd
from sqlalchemy import text

from pgboundary.geometry_compare import GeometryMatcher
from pgboundary.import_config import SimilarityMethod, SimilarityThresholds

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def get_year_start_date(year: str) -> date:
    """Return the start date of a year.

    Args:
        year: Year in "YYYY" format.

    Returns:
        Date of January 1st of the year.
    """
    return date(int(year), 1, 1)


def get_year_end_date(year: str) -> date:
    """Return the end date of a year.

    Args:
        year: Year in "YYYY" format.

    Returns:
        Date of December 31st of the year.
    """
    return date(int(year), 12, 31)


def add_historization_columns(gdf: gpd.GeoDataFrame, edition: str) -> gpd.GeoDataFrame:
    """Add historization columns to a GeoDataFrame.

    Args:
        gdf: GeoDataFrame to modify.
        edition: Data edition.

    Returns:
        GeoDataFrame with dt_debut and dt_fin columns.
    """
    gdf = gdf.copy()
    gdf["dt_debut"] = get_year_start_date(edition)
    gdf["dt_fin"] = None  # NULL = enregistrement courant
    return gdf


def close_old_records(
    engine: Engine,
    schema: str | None,
    table: str,
    key_field: str,
    keys_to_close: list[Any],
    end_date: date,
) -> int:
    """Close records that are no longer valid.

    Updates dt_fin for records whose key is in keys_to_close
    and that do not yet have an end date.

    Args:
        engine: SQLAlchemy Engine.
        schema: Schema name (or None).
        table: Table name.
        key_field: Key field name.
        keys_to_close: List of keys to close.
        end_date: End date to apply.

    Returns:
        Number of records updated.
    """
    if not keys_to_close:
        return 0

    full_table = f"{schema}.{table}" if schema else table

    # Construire la requête de mise à jour
    # Utiliser des placeholders pour éviter l'injection SQL
    placeholders = ", ".join([f":key_{i}" for i in range(len(keys_to_close))])

    query = text(f"""
        UPDATE {full_table}
        SET dt_fin = :end_date
        WHERE {key_field} IN ({placeholders})
        AND dt_fin IS NULL
    """)

    params: dict[str, Any] = {"end_date": end_date}
    for i, key in enumerate(keys_to_close):
        params[f"key_{i}"] = key

    with engine.connect() as conn:
        result = conn.execute(query, params)
        conn.commit()
        return result.rowcount


def get_existing_keys(
    engine: Engine,
    schema: str | None,
    table: str,
    key_field: str,
) -> set[Any]:
    """Retrieve existing keys (active records).

    Args:
        engine: SQLAlchemy Engine.
        schema: Schema name (or None).
        table: Table name.
        key_field: Key field name.

    Returns:
        Set of active keys (dt_fin IS NULL).
    """
    full_table = f"{schema}.{table}" if schema else table

    query = text(f"""
        SELECT DISTINCT {key_field}
        FROM {full_table}
        WHERE dt_fin IS NULL
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            return {row[0] for row in result}
    except Exception:
        # Table n'existe pas encore
        return set()


def get_existing_records(
    engine: Engine,
    schema: str | None,
    table: str,
    geometry_column: str = "geometry",
) -> gpd.GeoDataFrame:
    """Retrieve active records with their geometry.

    Args:
        engine: SQLAlchemy Engine.
        schema: Schema name (or None).
        table: Table name.
        geometry_column: Geometry column name.

    Returns:
        GeoDataFrame of active records.
    """
    full_table = f"{schema}.{table}" if schema else table

    query = f"""
        SELECT *
        FROM {full_table}
        WHERE dt_fin IS NULL
    """

    try:
        return gpd.read_postgis(query, engine, geom_col=geometry_column)
    except Exception:
        # Table n'existe pas encore
        return gpd.GeoDataFrame()


class HistorizationManager:
    """Historization manager for imports.

    This class orchestrates the historization process during the import
    of new vintage geographic datasets.

    Uses the decision matrix to classify matches:
    - IDENTICAL: automatic merge
    - LIKELY_MATCH: probable match
    - SUSPECT: potential conflict
    - DISTINCT: different objects
    """

    def __init__(
        self,
        engine: Engine,
        schema: str | None,
        table: str,
        key_field: str = "cd_insee",
        method: SimilarityMethod = SimilarityMethod.COMBINED,
        thresholds: SimilarityThresholds | None = None,
        # Rétrocompatibilité
        threshold: float | None = None,
    ) -> None:
        """Initialize the manager.

        Args:
            engine: SQLAlchemy Engine.
            schema: Schema name.
            table: Table name.
            key_field: Key field for identification.
            method: Comparison method (COMBINED recommended).
            thresholds: Decision matrix thresholds.
            threshold: [DEPRECATED] Use thresholds instead.
        """
        self.engine = engine
        self.schema = schema
        self.table = table
        self.key_field = key_field
        self.matcher = GeometryMatcher(
            method=method,
            thresholds=thresholds,
            key_field=key_field,
            threshold=threshold,
        )

    def prepare_import(
        self,
        new_data: gpd.GeoDataFrame,
        edition: str,
    ) -> tuple[gpd.GeoDataFrame, list[Any]]:
        """Prepare data for import with historization.

        Compares new data with existing data and determines:
        - New entities to insert
        - Entities to close (dt_fin)

        Args:
            new_data: New data to import.
            edition: Data edition.

        Returns:
            Tuple (data to insert, keys to close).
        """
        # Ajouter les colonnes d'historisation
        new_data = add_historization_columns(new_data, edition)

        # Récupérer les clés existantes
        existing_keys = get_existing_keys(self.engine, self.schema, self.table, self.key_field)

        if not existing_keys:
            # Première insertion, pas de comparaison nécessaire
            logger.info("Première insertion, pas d'historisation nécessaire")
            return new_data, []

        # Nouvelles clés
        new_keys = set(new_data[self.key_field].dropna().unique())

        # Clés à fermer (présentes avant, absentes maintenant)
        keys_to_close = list(existing_keys - new_keys)

        # TODO: Comparaison géométrique pour les clés communes
        # Pour l'instant, on ne ferme que les clés supprimées

        logger.info(
            "Historisation: %d nouvelles, %d à fermer, %d mises à jour",
            len(new_keys - existing_keys),
            len(keys_to_close),
            len(new_keys & existing_keys),
        )

        return new_data, keys_to_close

    def close_records(self, keys_to_close: list[Any], edition: str) -> int:
        """Close obsolete records.

        Args:
            keys_to_close: Keys of records to close.
            edition: New data edition.

        Returns:
            Number of records closed.
        """
        if not keys_to_close:
            return 0

        # La date de fin est le 31 décembre de l'année précédente
        previous_year = str(int(edition) - 1)
        end_date = get_year_end_date(previous_year)

        count = close_old_records(
            self.engine,
            self.schema,
            self.table,
            self.key_field,
            keys_to_close,
            end_date,
        )

        logger.info("Fermé %d enregistrements (dt_fin = %s)", count, end_date)
        return count

    def import_with_historization(
        self,
        new_data: gpd.GeoDataFrame,
        edition: str,
    ) -> int:
        """Import data with historization management.

        Args:
            new_data: Data to import.
            edition: Data edition.

        Returns:
            Number of records inserted.
        """
        # Préparer l'import
        data_to_insert, keys_to_close = self.prepare_import(new_data, edition)

        # Fermer les anciens enregistrements
        self.close_records(keys_to_close, edition)

        # Insérer les nouvelles données (append)
        full_table = self.table
        data_to_insert.to_postgis(
            name=full_table,
            con=self.engine,
            schema=self.schema,
            if_exists="append",
            index=False,
        )

        return len(data_to_insert)
