"""Tests pour le module CLI du catalogue (cli_catalog.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from pgboundary.cli_catalog import catalog_app


@pytest.fixture
def runner() -> CliRunner:
    """Fixture pour le CliRunner."""
    return CliRunner()


# =============================================================================
# Tests de catalog_update
# =============================================================================


class TestCatalogUpdate:
    """Tests pour catalog_update."""

    def test_update_help(self, runner: CliRunner) -> None:
        """Test aide de catalog update."""
        result = runner.invoke(catalog_app, ["update", "--help"])
        assert result.exit_code == 0

    def test_update_single_product(self, runner: CliRunner) -> None:
        """Test scan d'un seul produit."""
        mock_result = MagicMock()
        mock_result.products_scanned = 1
        mock_result.editions_discovered = 5
        mock_result.editions_new = 3
        mock_result.duration = 1.5
        mock_result.errors = []

        with (
            patch("pgboundary.cli_catalog.Settings") as mock_settings,
            patch("pgboundary.sources.explorer.CatalogExplorer") as mock_explorer,
        ):
            mock_settings.return_value.catalog_db = Path("/tmp/test_catalog.db")
            mock_explorer.return_value.scan_product.return_value = mock_result

            result = runner.invoke(catalog_app, ["update", "--product", "ADMIN-EXPRESS-COG"])
            assert result.exit_code == 0
            assert "1" in result.output

    def test_update_all_products(self, runner: CliRunner) -> None:
        """Test scan complet."""
        mock_result = MagicMock()
        mock_result.products_scanned = 10
        mock_result.editions_discovered = 50
        mock_result.editions_new = 20
        mock_result.duration = 5.0
        mock_result.errors = []

        with (
            patch("pgboundary.cli_catalog.Settings") as mock_settings,
            patch("pgboundary.sources.explorer.CatalogExplorer") as mock_explorer,
        ):
            mock_settings.return_value.catalog_db = Path("/tmp/test_catalog.db")
            mock_explorer.return_value.scan_all.return_value = mock_result

            result = runner.invoke(catalog_app, ["update"])
            assert result.exit_code == 0

    def test_update_with_errors(self, runner: CliRunner) -> None:
        """Test scan avec erreurs."""
        mock_result = MagicMock()
        mock_result.products_scanned = 5
        mock_result.editions_discovered = 10
        mock_result.editions_new = 5
        mock_result.duration = 3.0
        mock_result.errors = ["Erreur produit X", "Timeout produit Y"]

        with (
            patch("pgboundary.cli_catalog.Settings") as mock_settings,
            patch("pgboundary.sources.explorer.CatalogExplorer") as mock_explorer,
        ):
            mock_settings.return_value.catalog_db = Path("/tmp/test_catalog.db")
            mock_explorer.return_value.scan_product.return_value = mock_result

            result = runner.invoke(catalog_app, ["update", "--product", "TEST"])
            assert result.exit_code == 0
            assert "Erreur" in result.output or "erreur" in result.output.lower()


# =============================================================================
# Tests de catalog_list
# =============================================================================


class TestCatalogList:
    """Tests pour catalog_list."""

    def test_list_help(self, runner: CliRunner) -> None:
        """Test aide de catalog list."""
        result = runner.invoke(catalog_app, ["list", "--help"])
        assert result.exit_code == 0

    def test_list_all_products(self, runner: CliRunner) -> None:
        """Test listage de tous les produits."""
        mock_product = MagicMock()
        mock_product.id = "admin-express-cog"
        mock_product.name = "Admin Express COG"
        mock_product.provider = "IGN"
        mock_product.api_product = "ADMIN-EXPRESS-COG"
        mock_product.category.value = "administrative"
        mock_product.formats = []
        mock_product.territories = []
        mock_product.last_date = "2024-01-01"

        with (
            patch("pgboundary.cli_catalog.Settings") as mock_settings,
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
        ):
            mock_settings.return_value.catalog_db = Path("/tmp/nonexistent.db")
            mock_catalog.return_value.list_all.return_value = [mock_product]

            result = runner.invoke(catalog_app, ["list"])
            assert result.exit_code == 0

    def test_list_with_category_filter(self, runner: CliRunner) -> None:
        """Test listage avec filtre catégorie."""
        mock_product = MagicMock()
        mock_product.id = "admin-express-cog"
        mock_product.name = "Admin Express COG"
        mock_product.provider = "IGN"
        mock_product.api_product = None
        mock_product.category.value = "administrative"
        mock_product.formats = []
        mock_product.territories = []
        mock_product.last_date = None

        with (
            patch("pgboundary.cli_catalog.Settings") as mock_settings,
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
        ):
            mock_settings.return_value.catalog_db = Path("/tmp/nonexistent.db")
            mock_catalog.return_value.list_all.return_value = [mock_product]

            result = runner.invoke(catalog_app, ["list", "--category", "administrative"])
            assert result.exit_code == 0

    def test_list_empty_catalog(self, runner: CliRunner) -> None:
        """Test listage avec catalogue vide."""
        with (
            patch("pgboundary.cli_catalog.Settings") as mock_settings,
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
        ):
            mock_settings.return_value.catalog_db = Path("/tmp/nonexistent.db")
            mock_catalog.return_value.list_all.return_value = []

            result = runner.invoke(catalog_app, ["list"])
            assert result.exit_code == 0


# =============================================================================
# Tests de catalog_show
# =============================================================================


class TestCatalogShow:
    """Tests pour catalog_show."""

    def test_show_help(self, runner: CliRunner) -> None:
        """Test aide de catalog show."""
        result = runner.invoke(catalog_app, ["show", "--help"])
        assert result.exit_code == 0

    def test_show_yaml_product_no_sqlite(self, runner: CliRunner) -> None:
        """Test affichage d'un produit YAML sans SQLite."""
        mock_product = MagicMock()
        mock_product.name = "Admin Express COG"
        mock_product.id = "admin-express-cog"
        mock_product.provider = "IGN"
        mock_product.category.value = "administrative"
        mock_product.api_product = "ADMIN-EXPRESS-COG"
        mock_product.formats = [MagicMock(value="shp"), MagicMock(value="gpkg")]
        mock_product.territories = [MagicMock(value="FRA")]
        mock_product.get_size_formatted.return_value = "500 Mo"

        with (
            patch("pgboundary.cli_catalog.Settings") as mock_settings,
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
        ):
            mock_settings.return_value.catalog_db = Path("/tmp/nonexistent.db")
            mock_catalog.return_value.get.return_value = mock_product

            result = runner.invoke(catalog_app, ["show", "admin-express-cog"])
            assert result.exit_code == 0
            assert "Admin Express COG" in result.output

    def test_show_unknown_product(self, runner: CliRunner) -> None:
        """Test affichage d'un produit inconnu (ni YAML ni SQLite)."""
        with (
            patch("pgboundary.cli_catalog.Settings") as mock_settings,
            patch("pgboundary.products.get_default_catalog") as mock_catalog,
        ):
            mock_settings.return_value.catalog_db = Path("/tmp/nonexistent.db")
            mock_catalog.return_value.get.return_value = None

            result = runner.invoke(catalog_app, ["show", "UNKNOWN-PRODUCT"])
            # Devrait afficher un message mais pas crasher
            assert result.exit_code == 0 or "non trouvé" in result.output.lower()
