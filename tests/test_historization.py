"""Tests pour le module historization.

Ce module teste les fonctionnalités d'historisation des données
géographiques lors de l'import de nouveaux millésimes.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from pgboundary.historization import (
    HistorizationManager,
    add_historization_columns,
    close_old_records,
    get_existing_keys,
    get_existing_records,
    get_year_end_date,
    get_year_start_date,
)
from pgboundary.import_config import SimilarityMethod, SimilarityThresholds


class TestGetYearStartDate:
    """Tests pour get_year_start_date."""

    def test_standard_year(self) -> None:
        """Test avec une année standard."""
        result = get_year_start_date("2024")
        assert result == date(2024, 1, 1)

    def test_old_year(self) -> None:
        """Test avec une année ancienne."""
        result = get_year_start_date("2000")
        assert result == date(2000, 1, 1)

    def test_future_year(self) -> None:
        """Test avec une année future."""
        result = get_year_start_date("2030")
        assert result == date(2030, 1, 1)


class TestGetYearEndDate:
    """Tests pour get_year_end_date."""

    def test_standard_year(self) -> None:
        """Test avec une année standard."""
        result = get_year_end_date("2024")
        assert result == date(2024, 12, 31)

    def test_old_year(self) -> None:
        """Test avec une année ancienne."""
        result = get_year_end_date("2000")
        assert result == date(2000, 12, 31)


class TestAddHistorizationColumns:
    """Tests pour add_historization_columns."""

    def test_add_columns(self, sample_geodataframe: gpd.GeoDataFrame) -> None:
        """Test ajout des colonnes d'historisation."""
        result = add_historization_columns(sample_geodataframe, "2024")

        assert "dt_debut" in result.columns
        assert "dt_fin" in result.columns

        # Vérifier les valeurs
        assert all(result["dt_debut"] == date(2024, 1, 1))
        assert all(result["dt_fin"].isna())

    def test_original_not_modified(self, sample_geodataframe: gpd.GeoDataFrame) -> None:
        """Test que le GeoDataFrame original n'est pas modifié."""
        original_columns = set(sample_geodataframe.columns)
        add_historization_columns(sample_geodataframe, "2024")

        assert set(sample_geodataframe.columns) == original_columns
        assert "dt_debut" not in sample_geodataframe.columns

    def test_different_years(self, sample_geodataframe: gpd.GeoDataFrame) -> None:
        """Test avec différentes années."""
        result_2023 = add_historization_columns(sample_geodataframe, "2023")
        result_2024 = add_historization_columns(sample_geodataframe, "2024")

        assert all(result_2023["dt_debut"] == date(2023, 1, 1))
        assert all(result_2024["dt_debut"] == date(2024, 1, 1))


class TestCloseOldRecords:
    """Tests pour close_old_records."""

    def test_close_with_empty_list(self) -> None:
        """Test avec liste vide de clés."""
        mock_engine = MagicMock()
        result = close_old_records(
            engine=mock_engine,
            schema="geo",
            table="commune",
            key_field="cd_insee",
            keys_to_close=[],
            end_date=date(2023, 12, 31),
        )
        assert result == 0
        mock_engine.connect.assert_not_called()

    def test_close_with_keys(self) -> None:
        """Test fermeture avec des clés."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3

        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        result = close_old_records(
            engine=mock_engine,
            schema="geo",
            table="commune",
            key_field="cd_insee",
            keys_to_close=["01001", "01002", "01003"],
            end_date=date(2023, 12, 31),
        )

        assert result == 3
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_close_without_schema(self) -> None:
        """Test fermeture sans schéma."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1

        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        result = close_old_records(
            engine=mock_engine,
            schema=None,
            table="commune",
            key_field="cd_insee",
            keys_to_close=["01001"],
            end_date=date(2023, 12, 31),
        )

        assert result == 1


class TestGetExistingKeys:
    """Tests pour get_existing_keys."""

    def test_get_keys_success(self) -> None:
        """Test récupération des clés avec succès."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = lambda _self: iter([("01001",), ("01002",), ("01003",)])

        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        result = get_existing_keys(
            engine=mock_engine,
            schema="geo",
            table="commune",
            key_field="cd_insee",
        )

        assert result == {"01001", "01002", "01003"}

    def test_get_keys_table_not_exists(self) -> None:
        """Test quand la table n'existe pas."""
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(
            side_effect=Exception("Table not found")
        )
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        result = get_existing_keys(
            engine=mock_engine,
            schema="geo",
            table="commune",
            key_field="cd_insee",
        )

        assert result == set()

    def test_get_keys_without_schema(self) -> None:
        """Test récupération sans schéma."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = lambda _self: iter([("01001",)])

        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        result = get_existing_keys(
            engine=mock_engine,
            schema=None,
            table="commune",
            key_field="cd_insee",
        )

        assert result == {"01001"}


class TestGetExistingRecords:
    """Tests pour get_existing_records."""

    def test_get_records_table_not_exists(self) -> None:
        """Test quand la table n'existe pas."""
        mock_engine = MagicMock()

        with patch("pgboundary.historization.gpd.read_postgis") as mock_read:
            mock_read.side_effect = Exception("Table not found")

            result = get_existing_records(
                engine=mock_engine,
                schema="geo",
                table="commune",
            )

            assert isinstance(result, gpd.GeoDataFrame)
            assert len(result) == 0

    def test_get_records_success(self) -> None:
        """Test récupération avec succès."""
        mock_engine = MagicMock()
        expected_gdf = gpd.GeoDataFrame(
            {"cd_insee": ["01001"], "geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])]},
            crs="EPSG:4326",
        )

        with patch("pgboundary.historization.gpd.read_postgis") as mock_read:
            mock_read.return_value = expected_gdf

            result = get_existing_records(
                engine=mock_engine,
                schema="geo",
                table="commune",
            )

            assert len(result) == 1
            assert "cd_insee" in result.columns


class TestHistorizationManager:
    """Tests pour la classe HistorizationManager."""

    @pytest.fixture
    def mock_engine(self) -> MagicMock:
        """Fixture pour un engine mocké."""
        return MagicMock()

    @pytest.fixture
    def manager(self, mock_engine: MagicMock) -> HistorizationManager:
        """Fixture pour un manager d'historisation."""
        return HistorizationManager(
            engine=mock_engine,
            schema="geo",
            table="commune",
            key_field="cd_insee",
        )

    def test_init_default(self, mock_engine: MagicMock) -> None:
        """Test initialisation par défaut."""
        manager = HistorizationManager(
            engine=mock_engine,
            schema="geo",
            table="commune",
        )
        assert manager.key_field == "cd_insee"
        assert manager.matcher.method == SimilarityMethod.COMBINED

    def test_init_custom(self, mock_engine: MagicMock) -> None:
        """Test initialisation personnalisée."""
        thresholds = SimilarityThresholds(identical_min=0.90)
        manager = HistorizationManager(
            engine=mock_engine,
            schema="geo",
            table="commune",
            key_field="code_iris",
            method=SimilarityMethod.JACCARD,
            thresholds=thresholds,
        )
        assert manager.key_field == "code_iris"
        assert manager.matcher.method == SimilarityMethod.JACCARD

    def test_init_legacy_threshold(self, mock_engine: MagicMock) -> None:
        """Test initialisation avec threshold legacy."""
        manager = HistorizationManager(
            engine=mock_engine,
            schema="geo",
            table="commune",
            threshold=0.85,
        )
        assert manager.matcher.thresholds.identical_min == 0.85

    def test_prepare_import_first_insertion(
        self,
        manager: HistorizationManager,
        sample_geodataframe: gpd.GeoDataFrame,
    ) -> None:
        """Test préparation pour première insertion."""
        with patch(
            "pgboundary.historization.get_existing_keys",
            return_value=set(),
        ):
            data, keys_to_close = manager.prepare_import(sample_geodataframe, "2024")

            assert "dt_debut" in data.columns
            assert "dt_fin" in data.columns
            assert keys_to_close == []

    def test_prepare_import_with_removals(
        self,
        manager: HistorizationManager,
        sample_geodataframe: gpd.GeoDataFrame,
    ) -> None:
        """Test préparation avec suppressions."""
        # Clés existantes incluent "01004" qui n'est pas dans les nouvelles données
        existing_keys = {"01001", "01002", "01003", "01004"}

        with patch(
            "pgboundary.historization.get_existing_keys",
            return_value=existing_keys,
        ):
            _, keys_to_close = manager.prepare_import(sample_geodataframe, "2024")

            assert "01004" in keys_to_close
            assert len(keys_to_close) == 1

    def test_prepare_import_with_additions(
        self,
        manager: HistorizationManager,
        sample_geodataframe: gpd.GeoDataFrame,
    ) -> None:
        """Test préparation avec ajouts."""
        # Clés existantes n'incluent que "01001"
        existing_keys = {"01001"}

        with patch(
            "pgboundary.historization.get_existing_keys",
            return_value=existing_keys,
        ):
            _, keys_to_close = manager.prepare_import(sample_geodataframe, "2024")

            # Pas de clés à fermer car toutes les existantes sont encore présentes
            assert keys_to_close == []

    def test_close_records_empty(self, manager: HistorizationManager) -> None:
        """Test fermeture avec liste vide."""
        result = manager.close_records([], "2024")
        assert result == 0

    def test_close_records_with_keys(self, manager: HistorizationManager) -> None:
        """Test fermeture avec des clés."""
        with patch(
            "pgboundary.historization.close_old_records",
            return_value=2,
        ) as mock_close:
            result = manager.close_records(["01001", "01002"], "2024")

            assert result == 2
            mock_close.assert_called_once()
            # Vérifier que la date de fin est le 31/12 de l'année précédente
            call_args = mock_close.call_args
            # Les arguments sont positionnels
            assert call_args[0][5] == date(2023, 12, 31)  # end_date est le 6ème argument

    def test_import_with_historization(
        self,
        manager: HistorizationManager,
        sample_geodataframe: gpd.GeoDataFrame,
    ) -> None:
        """Test import complet avec historisation."""
        with (
            patch(
                "pgboundary.historization.get_existing_keys",
                return_value=set(),
            ),
            patch(
                "geopandas.GeoDataFrame.to_postgis",
            ) as mock_to_postgis,
        ):
            result = manager.import_with_historization(sample_geodataframe, "2024")

            assert result == len(sample_geodataframe)
            mock_to_postgis.assert_called_once()


class TestHistorizationIntegration:
    """Tests d'intégration pour l'historisation."""

    def test_full_workflow(self, sample_geodataframe: gpd.GeoDataFrame) -> None:
        """Test du workflow complet d'historisation."""
        mock_engine = MagicMock()
        manager = HistorizationManager(
            engine=mock_engine,
            schema="geo",
            table="commune",
            key_field="cd_insee",
        )

        # Simuler des clés existantes avec une suppression
        existing_keys = {"01001", "01002", "01003", "01999"}

        with (
            patch(
                "pgboundary.historization.get_existing_keys",
                return_value=existing_keys,
            ),
            patch(
                "pgboundary.historization.close_old_records",
                return_value=1,
            ) as mock_close,
            patch(
                "geopandas.GeoDataFrame.to_postgis",
            ),
        ):
            result = manager.import_with_historization(sample_geodataframe, "2024")

            # Vérifier que close_old_records a été appelé avec la bonne clé
            mock_close.assert_called_once()
            call_args = mock_close.call_args
            # keys_to_close est le 5ème argument (index 4)
            assert "01999" in call_args[0][4]

            assert result == len(sample_geodataframe)
