"""Modèles de données pour les limites administratives françaises."""

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import MultiPolygon, Polygon


class AdminLevel(StrEnum):
    """Niveaux administratifs français."""

    REGION = "region"
    DEPARTEMENT = "departement"
    ARRONDISSEMENT = "arrondissement"
    EPCI = "epci"
    COMMUNE = "commune"
    COMMUNE_ASSOCIEE_DELEGUEE = "commune_associee_deleguee"


class BoundaryBase(BaseModel):
    """Modèle de base pour une limite administrative."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(..., description="Identifiant unique")
    nom: str = Field(..., description="Nom de l'entité")
    geometry: Polygon | MultiPolygon = Field(..., description="Géométrie de l'entité")
    date_creation: date | None = Field(default=None, description="Date de création")
    date_modification: date | None = Field(
        default=None, description="Date de dernière modification"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convertit le modèle en dictionnaire pour insertion."""
        data = self.model_dump(exclude={"geometry"})
        data["geometry"] = self.geometry.wkt
        return data


class Region(BoundaryBase):
    """Région française."""

    code_insee: str = Field(..., description="Code INSEE de la région", pattern=r"^\d{2}$")
    chef_lieu: str | None = Field(default=None, description="Code INSEE du chef-lieu")


class Departement(BoundaryBase):
    """Département français."""

    code_insee: str = Field(
        ...,
        description="Code INSEE du département",
        pattern=r"^(\d{2}|2[AB]|9[78]\d)$",
    )
    code_region: str = Field(..., description="Code INSEE de la région")
    chef_lieu: str | None = Field(default=None, description="Code INSEE de la préfecture")


class EPCI(BoundaryBase):
    """Établissement Public de Coopération Intercommunale."""

    code_siren: str = Field(..., description="Code SIREN de l'EPCI", pattern=r"^\d{9}$")
    nature: str = Field(..., description="Nature juridique (CC, CA, CU, MET)")
    code_departement: str | None = Field(default=None, description="Code du département principal")


class Commune(BoundaryBase):
    """Commune française."""

    code_insee: str = Field(
        ...,
        description="Code INSEE de la commune",
        pattern=r"^(\d{5}|2[AB]\d{3}|9[78]\d{3})$",
    )
    code_postal: str | None = Field(default=None, description="Code postal principal")
    code_departement: str = Field(..., description="Code INSEE du département")
    code_region: str = Field(..., description="Code INSEE de la région")
    code_epci: str | None = Field(default=None, description="Code SIREN de l'EPCI")
    population: int | None = Field(default=None, description="Population municipale")
    superficie: float | None = Field(default=None, description="Superficie en km²")


class CommuneAssocieeDeleguee(BoundaryBase):
    """Commune associée ou déléguée."""

    code_insee: str = Field(..., description="Code INSEE")
    code_commune_parente: str = Field(..., description="Code INSEE de la commune parente")
    type_entite: str = Field(..., description="Type: COMA (associée) ou COMD (déléguée)")
