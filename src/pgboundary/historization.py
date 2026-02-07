"""Module d'historisation des données géographiques.

Ce module gère l'historisation des entités géographiques lors
de l'import de nouveaux millésimes.

Fonctionnalités:
- Ajout des colonnes dt_debut et dt_fin
- Comparaison avec les données existantes
- Mise à jour des dates de fin pour les entités modifiées/supprimées
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
    """Retourne la date de début d'une année.

    Args:
        year: Année au format "YYYY".

    Returns:
        Date du 1er janvier de l'année.
    """
    return date(int(year), 1, 1)


def get_year_end_date(year: str) -> date:
    """Retourne la date de fin d'une année.

    Args:
        year: Année au format "YYYY".

    Returns:
        Date du 31 décembre de l'année.
    """
    return date(int(year), 12, 31)


def add_historization_columns(gdf: gpd.GeoDataFrame, year: str) -> gpd.GeoDataFrame:
    """Ajoute les colonnes d'historisation à un GeoDataFrame.

    Args:
        gdf: GeoDataFrame à modifier.
        year: Année du millésime.

    Returns:
        GeoDataFrame avec colonnes dt_debut et dt_fin.
    """
    gdf = gdf.copy()
    gdf["dt_debut"] = get_year_start_date(year)
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
    """Ferme les enregistrements qui ne sont plus valides.

    Met à jour dt_fin pour les enregistrements dont la clé est dans keys_to_close
    et qui n'ont pas encore de date de fin.

    Args:
        engine: Engine SQLAlchemy.
        schema: Nom du schéma (ou None).
        table: Nom de la table.
        key_field: Nom du champ clé.
        keys_to_close: Liste des clés à fermer.
        end_date: Date de fin à appliquer.

    Returns:
        Nombre d'enregistrements mis à jour.
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
    """Récupère les clés existantes (enregistrements actifs).

    Args:
        engine: Engine SQLAlchemy.
        schema: Nom du schéma (ou None).
        table: Nom de la table.
        key_field: Nom du champ clé.

    Returns:
        Ensemble des clés actives (dt_fin IS NULL).
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
    """Récupère les enregistrements actifs avec leur géométrie.

    Args:
        engine: Engine SQLAlchemy.
        schema: Nom du schéma (ou None).
        table: Nom de la table.
        geometry_column: Nom de la colonne géométrie.

    Returns:
        GeoDataFrame des enregistrements actifs.
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
    """Gestionnaire d'historisation pour les imports.

    Cette classe orchestre le processus d'historisation lors de l'import
    de nouveaux millésimes de données géographiques.

    Utilise la matrice de décision pour classifier les correspondances:
    - IDENTICAL: fusion automatique
    - LIKELY_MATCH: correspondance probable
    - SUSPECT: conflit potentiel
    - DISTINCT: objets différents
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
        """Initialise le gestionnaire.

        Args:
            engine: Engine SQLAlchemy.
            schema: Nom du schéma.
            table: Nom de la table.
            key_field: Champ clé pour l'identification.
            method: Méthode de comparaison (COMBINED recommandé).
            thresholds: Seuils de la matrice de décision.
            threshold: [DEPRECATED] Utilisez thresholds à la place.
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
        year: str,
    ) -> tuple[gpd.GeoDataFrame, list[Any]]:
        """Prépare les données pour l'import avec historisation.

        Compare les nouvelles données avec les existantes et détermine:
        - Les nouvelles entités à insérer
        - Les entités à fermer (dt_fin)

        Args:
            new_data: Nouvelles données à importer.
            year: Année du millésime.

        Returns:
            Tuple (données à insérer, clés à fermer).
        """
        # Ajouter les colonnes d'historisation
        new_data = add_historization_columns(new_data, year)

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

    def close_records(self, keys_to_close: list[Any], year: str) -> int:
        """Ferme les enregistrements obsolètes.

        Args:
            keys_to_close: Clés des enregistrements à fermer.
            year: Année du nouveau millésime.

        Returns:
            Nombre d'enregistrements fermés.
        """
        if not keys_to_close:
            return 0

        # La date de fin est le 31 décembre de l'année précédente
        previous_year = str(int(year) - 1)
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
        year: str,
    ) -> int:
        """Importe des données avec gestion de l'historisation.

        Args:
            new_data: Données à importer.
            year: Année du millésime.

        Returns:
            Nombre d'enregistrements insérés.
        """
        # Préparer l'import
        data_to_insert, keys_to_close = self.prepare_import(new_data, year)

        # Fermer les anciens enregistrements
        self.close_records(keys_to_close, year)

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
