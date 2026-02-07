"""Tests pour les types de données."""

import pytest
from pydantic import ValidationError
from shapely.geometry import MultiPolygon

from pgboundary.types.boundaries import (
    AdminLevel,
    Commune,
    Departement,
    Region,
)


class TestAdminLevel:
    """Tests pour l'énumération AdminLevel."""

    def test_admin_levels(self) -> None:
        """Teste les valeurs de l'énumération."""
        assert AdminLevel.REGION == "region"
        assert AdminLevel.DEPARTEMENT == "departement"
        assert AdminLevel.COMMUNE == "commune"


class TestRegion:
    """Tests pour le modèle Region."""

    def test_valid_region(self, sample_multipolygon: MultiPolygon) -> None:
        """Teste la création d'une région valide."""
        region = Region(
            id="REG001",
            nom="Île-de-France",
            code_insee="11",
            geometry=sample_multipolygon,
        )

        assert region.nom == "Île-de-France"
        assert region.code_insee == "11"

    def test_invalid_code_insee(self, sample_multipolygon: MultiPolygon) -> None:
        """Teste qu'un code INSEE invalide lève une erreur."""
        with pytest.raises(ValidationError):
            Region(
                id="REG001",
                nom="Test",
                code_insee="ABC",
                geometry=sample_multipolygon,
            )

    def test_to_dict(self, sample_multipolygon: MultiPolygon) -> None:
        """Teste la conversion en dictionnaire."""
        region = Region(
            id="REG001",
            nom="Test",
            code_insee="11",
            geometry=sample_multipolygon,
        )

        data = region.to_dict()

        assert "id" in data
        assert "geometry" in data
        assert isinstance(data["geometry"], str)


class TestDepartement:
    """Tests pour le modèle Departement."""

    def test_valid_departement(self, sample_multipolygon: MultiPolygon) -> None:
        """Teste la création d'un département valide."""
        dept = Departement(
            id="DEP075",
            nom="Paris",
            code_insee="75",
            code_region="11",
            geometry=sample_multipolygon,
        )

        assert dept.nom == "Paris"
        assert dept.code_insee == "75"
        assert dept.code_region == "11"

    def test_corse_code(self, sample_multipolygon: MultiPolygon) -> None:
        """Teste les codes corses (2A, 2B)."""
        dept = Departement(
            id="DEP2A",
            nom="Corse-du-Sud",
            code_insee="2A",
            code_region="94",
            geometry=sample_multipolygon,
        )

        assert dept.code_insee == "2A"


class TestCommune:
    """Tests pour le modèle Commune."""

    def test_valid_commune(self, sample_multipolygon: MultiPolygon) -> None:
        """Teste la création d'une commune valide."""
        commune = Commune(
            id="COM75056",
            nom="Paris",
            code_insee="75056",
            code_departement="75",
            code_region="11",
            geometry=sample_multipolygon,
            population=2145906,
        )

        assert commune.nom == "Paris"
        assert commune.population == 2145906

    def test_commune_with_optional_fields(self, sample_multipolygon: MultiPolygon) -> None:
        """Teste une commune avec champs optionnels."""
        commune = Commune(
            id="COM01001",
            nom="Test",
            code_insee="01001",
            code_departement="01",
            code_region="84",
            geometry=sample_multipolygon,
        )

        assert commune.code_postal is None
        assert commune.code_epci is None
        assert commune.population is None
