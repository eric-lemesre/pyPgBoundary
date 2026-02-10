"""Tests pour le module cli_widgets.

Ce module teste les widgets CLI interactifs :
- CheckboxItem et CheckboxResult
- SelectItem et SelectResult
- checkbox_select avec mocks
- select_single avec mocks
- select_territory, select_format, select_layers, select_editions
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import readchar

from pgboundary.cli_widgets import (
    CheckboxItem,
    CheckboxResult,
    SelectItem,
    SelectResult,
    _is_cancel_key,
    checkbox_select,
    select_editions,
    select_format,
    select_layers,
    select_single,
    select_territory,
)


class TestIsCancelKey:
    """Tests pour _is_cancel_key."""

    def test_escape_char(self) -> None:
        """Test avec le caractère ESC (0x1B)."""
        assert _is_cancel_key("\x1b") is True

    def test_r_key(self) -> None:
        """Test avec la touche 'r' (nouvelle touche de retour)."""
        assert _is_cancel_key("r") is True

    def test_other_keys(self) -> None:
        """Test avec d'autres touches."""
        assert _is_cancel_key("a") is False
        assert _is_cancel_key("q") is False
        assert _is_cancel_key(" ") is False
        assert _is_cancel_key("\n") is False
        assert _is_cancel_key("\r") is False

    def test_empty_string(self) -> None:
        """Test avec chaîne vide."""
        assert _is_cancel_key("") is False

    def test_control_chars(self) -> None:
        """Test avec d'autres caractères de contrôle."""
        assert _is_cancel_key("\x00") is False  # NULL
        assert _is_cancel_key("\x03") is False  # Ctrl+C
        assert _is_cancel_key("\x04") is False  # Ctrl+D


class TestCheckboxItem:
    """Tests pour la dataclass CheckboxItem."""

    def test_default_values(self) -> None:
        """Test création avec valeurs par défaut."""
        item = CheckboxItem(label="Test", value="test")
        assert item.label == "Test"
        assert item.value == "test"
        assert item.selected is False
        assert item.description is None

    def test_full_values(self) -> None:
        """Test création avec toutes les valeurs."""
        item = CheckboxItem(
            label="Test",
            value="test",
            selected=True,
            description="Description",
        )
        assert item.label == "Test"
        assert item.value == "test"
        assert item.selected is True
        assert item.description == "Description"

    def test_mutable_selected(self) -> None:
        """Test que selected est mutable."""
        item = CheckboxItem(label="Test", value="test")
        assert item.selected is False
        item.selected = True
        assert item.selected is True


class TestCheckboxResult:
    """Tests pour CheckboxResult."""

    def test_empty_result(self) -> None:
        """Test résultat vide."""
        result = CheckboxResult(items=[])
        assert result.selected_values == []
        assert result.selected_labels == []
        assert bool(result) is False

    def test_cancelled_result(self) -> None:
        """Test résultat annulé."""
        items = [CheckboxItem(label="A", value="a", selected=True)]
        result = CheckboxResult(items=items, cancelled=True)
        assert result.cancelled is True
        assert result.selected_values == ["a"]
        assert bool(result) is False  # Annulé donc False

    def test_with_selections(self) -> None:
        """Test avec sélections."""
        items = [
            CheckboxItem(label="A", value="a", selected=True),
            CheckboxItem(label="B", value="b", selected=False),
            CheckboxItem(label="C", value="c", selected=True),
        ]
        result = CheckboxResult(items=items)
        assert result.selected_values == ["a", "c"]
        assert result.selected_labels == ["A", "C"]
        assert bool(result) is True

    def test_no_selections(self) -> None:
        """Test sans sélection."""
        items = [
            CheckboxItem(label="A", value="a", selected=False),
            CheckboxItem(label="B", value="b", selected=False),
        ]
        result = CheckboxResult(items=items)
        assert result.selected_values == []
        assert bool(result) is False


class TestSelectItem:
    """Tests pour la dataclass SelectItem."""

    def test_default_values(self) -> None:
        """Test création avec valeurs par défaut."""
        item = SelectItem(label="Test", value="test")
        assert item.label == "Test"
        assert item.value == "test"
        assert item.description is None

    def test_with_description(self) -> None:
        """Test création avec description."""
        item = SelectItem(label="Test", value="test", description="Desc")
        assert item.description == "Desc"


class TestSelectResult:
    """Tests pour SelectResult."""

    def test_empty_result(self) -> None:
        """Test résultat vide."""
        result = SelectResult()
        assert result.item is None
        assert result.value is None
        assert result.label is None
        assert bool(result) is False

    def test_cancelled_result(self) -> None:
        """Test résultat annulé."""
        item = SelectItem(label="A", value="a")
        result = SelectResult(item=item, cancelled=True)
        assert result.cancelled is True
        assert result.value == "a"
        assert bool(result) is False

    def test_with_selection(self) -> None:
        """Test avec sélection."""
        item = SelectItem(label="Test", value="test_value")
        result = SelectResult(item=item)
        assert result.value == "test_value"
        assert result.label == "Test"
        assert bool(result) is True


class TestCheckboxSelect:
    """Tests pour checkbox_select avec mocks."""

    @pytest.fixture
    def mock_live(self) -> MagicMock:
        """Mock pour Rich Live."""
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_immediate_enter(self, mock_live: MagicMock) -> None:
        """Test validation immédiate avec entrée."""
        items = [
            CheckboxItem(label="A", value="a", selected=True),
            CheckboxItem(label="B", value="b"),
        ]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = checkbox_select(items)

        assert not result.cancelled
        assert result.selected_values == ["a"]

    def test_escape_cancels(self, mock_live: MagicMock) -> None:
        """Test annulation avec Échap."""
        items = [CheckboxItem(label="A", value="a", selected=True)]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value="\x1b"),
        ):
            result = checkbox_select(items)

        assert result.cancelled is True

    def test_space_toggles_selection(self, mock_live: MagicMock) -> None:
        """Test espace pour cocher/décocher."""
        items = [CheckboxItem(label="A", value="a", selected=False)]
        keys = [" ", readchar.key.ENTER]
        key_iter = iter(keys)

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", side_effect=lambda: next(key_iter)),
        ):
            result = checkbox_select(items)

        assert items[0].selected is True
        assert result.selected_values == ["a"]

    def test_select_all_with_a(self, mock_live: MagicMock) -> None:
        """Test 'a' pour tout sélectionner."""
        items = [
            CheckboxItem(label="A", value="a", selected=False),
            CheckboxItem(label="B", value="b", selected=False),
        ]
        keys = ["a", readchar.key.ENTER]
        key_iter = iter(keys)

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", side_effect=lambda: next(key_iter)),
        ):
            result = checkbox_select(items)

        assert result.selected_values == ["a", "b"]

    def test_deselect_all_with_n(self, mock_live: MagicMock) -> None:
        """Test 'n' pour tout désélectionner."""
        items = [
            CheckboxItem(label="A", value="a", selected=True),
            CheckboxItem(label="B", value="b", selected=True),
        ]
        keys = ["n", readchar.key.ENTER]
        key_iter = iter(keys)

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", side_effect=lambda: next(key_iter)),
        ):
            result = checkbox_select(items, min_selected=0)

        assert result.selected_values == []

    def test_navigation_up_down(self, mock_live: MagicMock) -> None:
        """Test navigation haut/bas."""
        items = [
            CheckboxItem(label="A", value="a"),
            CheckboxItem(label="B", value="b"),
        ]
        # Bas, espace (sélectionner B), entrée
        keys = [readchar.key.DOWN, " ", readchar.key.ENTER]
        key_iter = iter(keys)

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", side_effect=lambda: next(key_iter)),
        ):
            result = checkbox_select(items, min_selected=0)

        assert items[1].selected is True
        assert result.selected_values == ["b"]

    def test_navigation_j_k(self, mock_live: MagicMock) -> None:
        """Test navigation avec j/k (vim style)."""
        items = [
            CheckboxItem(label="A", value="a"),
            CheckboxItem(label="B", value="b"),
        ]
        # j (bas), espace (sélectionner B), k (haut), espace (sélectionner A), entrée
        keys = ["j", " ", "k", " ", readchar.key.ENTER]
        key_iter = iter(keys)

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", side_effect=lambda: next(key_iter)),
        ):
            result = checkbox_select(items, min_selected=0)

        assert result.selected_values == ["a", "b"]

    def test_wrap_around_navigation(self, mock_live: MagicMock) -> None:
        """Test navigation cyclique."""
        items = [
            CheckboxItem(label="A", value="a"),
            CheckboxItem(label="B", value="b"),
        ]
        # Haut (cycle vers B), espace, entrée
        keys = [readchar.key.UP, " ", readchar.key.ENTER]
        key_iter = iter(keys)

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", side_effect=lambda: next(key_iter)),
        ):
            checkbox_select(items, min_selected=0)

        assert items[1].selected is True  # B est sélectionné (index 1)

    def test_min_selected_enforcement(self, mock_live: MagicMock) -> None:
        """Test minimum de sélection requis."""
        items = [CheckboxItem(label="A", value="a", selected=False)]
        # Premier entrée (rejeté car min_selected=1), espace, entrée
        keys = [readchar.key.ENTER, " ", readchar.key.ENTER]
        key_iter = iter(keys)

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", side_effect=lambda: next(key_iter)),
            patch("pgboundary.cli_widgets.console") as mock_console,
        ):
            result = checkbox_select(items, min_selected=1)

        # Un message d'avertissement devrait être affiché
        mock_console.print.assert_called()
        assert result.selected_values == ["a"]


class TestSelectSingle:
    """Tests pour select_single avec mocks."""

    @pytest.fixture
    def mock_live(self) -> MagicMock:
        """Mock pour Rich Live."""
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_empty_items(self) -> None:
        """Test avec liste vide."""
        result = select_single([])
        assert result.cancelled is True

    def test_immediate_enter(self, mock_live: MagicMock) -> None:
        """Test validation immédiate."""
        items = [
            SelectItem(label="A", value="a"),
            SelectItem(label="B", value="b"),
        ]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_single(items)

        assert result.value == "a"  # Premier élément par défaut

    def test_escape_cancels(self, mock_live: MagicMock) -> None:
        """Test annulation avec Échap."""
        items = [SelectItem(label="A", value="a")]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value="\x1b"),
        ):
            result = select_single(items)

        assert result.cancelled is True

    def test_navigation_down(self, mock_live: MagicMock) -> None:
        """Test navigation vers le bas."""
        items = [
            SelectItem(label="A", value="a"),
            SelectItem(label="B", value="b"),
        ]
        keys = [readchar.key.DOWN, readchar.key.ENTER]
        key_iter = iter(keys)

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", side_effect=lambda: next(key_iter)),
        ):
            result = select_single(items)

        assert result.value == "b"

    def test_default_index(self, mock_live: MagicMock) -> None:
        """Test index par défaut."""
        items = [
            SelectItem(label="A", value="a"),
            SelectItem(label="B", value="b"),
            SelectItem(label="C", value="c"),
        ]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_single(items, default_index=2)

        assert result.value == "c"

    def test_default_index_out_of_bounds(self, mock_live: MagicMock) -> None:
        """Test index par défaut hors limites."""
        items = [
            SelectItem(label="A", value="a"),
            SelectItem(label="B", value="b"),
        ]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_single(items, default_index=10)

        # Devrait être limité au dernier élément
        assert result.value == "b"

    def test_enter_variations(self, mock_live: MagicMock) -> None:
        """Test différentes variantes de Enter."""
        items = [SelectItem(label="A", value="a")]

        for enter_key in [readchar.key.ENTER, "\r", "\n"]:
            with (
                patch("pgboundary.cli_widgets.Live", return_value=mock_live),
                patch("pgboundary.cli_widgets.readchar.readkey", return_value=enter_key),
            ):
                result = select_single(items)
            assert result.value == "a"


class TestSelectTerritory:
    """Tests pour select_territory."""

    @pytest.fixture
    def mock_live(self) -> MagicMock:
        """Mock pour Rich Live."""
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_default_fra(self, mock_live: MagicMock) -> None:
        """Test sélection par défaut FRA."""
        territories = ["FXX", "FRA", "GLP"]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_territory(territories)

        assert result.value == "FRA"  # FRA est le défaut

    def test_custom_default(self, mock_live: MagicMock) -> None:
        """Test avec défaut personnalisé."""
        territories = ["FXX", "FRA", "GLP"]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_territory(territories, default="GLP")

        assert result.value == "GLP"

    def test_known_territories_have_descriptions(self, mock_live: MagicMock) -> None:
        """Test que les territoires connus ont des descriptions."""
        territories = ["FRA", "FXX", "GLP", "MTQ", "GUF", "REU", "MYT"]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value="\x1b"),
        ):
            # On annule juste pour vérifier que ça ne plante pas
            result = select_territory(territories)

        assert result.cancelled is True


class TestSelectFormat:
    """Tests pour select_format."""

    @pytest.fixture
    def mock_live(self) -> MagicMock:
        """Mock pour Rich Live."""
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_default_shp(self, mock_live: MagicMock) -> None:
        """Test sélection par défaut shp."""
        formats = ["gpkg", "shp", "geojson"]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_format(formats)

        assert result.value == "shp"

    def test_custom_default(self, mock_live: MagicMock) -> None:
        """Test avec défaut personnalisé."""
        formats = ["gpkg", "shp"]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_format(formats, default="gpkg")

        assert result.value == "gpkg"


class TestSelectLayers:
    """Tests pour select_layers."""

    @pytest.fixture
    def mock_live(self) -> MagicMock:
        """Mock pour Rich Live."""
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_all_preselected_by_default(self, mock_live: MagicMock) -> None:
        """Test que tout est sélectionné par défaut."""
        layers = [
            ("REGION", "Régions"),
            ("DEPARTEMENT", "Départements"),
        ]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_layers(layers)

        assert result.selected_values == ["REGION", "DEPARTEMENT"]

    def test_custom_preselection(self, mock_live: MagicMock) -> None:
        """Test avec présélection personnalisée."""
        layers = [
            ("REGION", "Régions"),
            ("DEPARTEMENT", "Départements"),
            ("COMMUNE", "Communes"),
        ]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_layers(layers, preselected=["COMMUNE"])

        assert result.selected_values == ["COMMUNE"]


class TestSelectEditions:
    """Tests pour select_editions."""

    @pytest.fixture
    def mock_live(self) -> MagicMock:
        """Mock pour Rich Live."""
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_default_editions(self, mock_live: MagicMock) -> None:
        """Test génération des éditions par défaut."""
        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_editions()

        # Aucun millésime disponible → annulé
        assert result.cancelled is True

    def test_custom_editions(self, mock_live: MagicMock) -> None:
        """Test avec éditions personnalisées."""
        editions = ["2024", "2023", "2022"]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_editions(available_editions=editions)

        # La première édition (2024) devrait être sélectionnée
        assert result.selected_values == ["2024"]

    def test_custom_preselection(self, mock_live: MagicMock) -> None:
        """Test avec présélection personnalisée."""
        editions = ["2024", "2023", "2022"]

        with (
            patch("pgboundary.cli_widgets.Live", return_value=mock_live),
            patch("pgboundary.cli_widgets.readchar.readkey", return_value=readchar.key.ENTER),
        ):
            result = select_editions(available_editions=editions, preselected=["2023", "2022"])

        assert set(result.selected_values) == {"2023", "2022"}
