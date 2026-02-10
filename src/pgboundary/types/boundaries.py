"""Data models for French administrative boundaries."""

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import MultiPolygon, Polygon


class AdminLevel(StrEnum):
    """French administrative levels."""

    REGION = "region"
    DEPARTEMENT = "departement"
    ARRONDISSEMENT = "arrondissement"
    EPCI = "epci"
    COMMUNE = "commune"
    COMMUNE_ASSOCIEE_DELEGUEE = "commune_associee_deleguee"


class BoundaryBase(BaseModel):
    """Base model for an administrative boundary."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(..., description="Unique identifier")
    nom: str = Field(..., description="Entity name")
    geometry: Polygon | MultiPolygon = Field(..., description="Entity geometry")
    date_creation: date | None = Field(default=None, description="Creation date")
    date_modification: date | None = Field(default=None, description="Last modification date")

    def to_dict(self) -> dict[str, Any]:
        """Convert the model to a dictionary for insertion."""
        data = self.model_dump(exclude={"geometry"})
        data["geometry"] = self.geometry.wkt
        return data


class Region(BoundaryBase):
    """French region."""

    code_insee: str = Field(..., description="INSEE code of the region", pattern=r"^\d{2}$")
    chef_lieu: str | None = Field(default=None, description="INSEE code of the capital")


class Departement(BoundaryBase):
    """French department."""

    code_insee: str = Field(
        ...,
        description="INSEE code of the department",
        pattern=r"^(\d{2}|2[AB]|9[78]\d)$",
    )
    code_region: str = Field(..., description="INSEE code of the region")
    chef_lieu: str | None = Field(default=None, description="INSEE code of the prefecture")


class EPCI(BoundaryBase):
    """Public Establishment for Intercommunal Cooperation (EPCI)."""

    code_siren: str = Field(..., description="SIREN code of the EPCI", pattern=r"^\d{9}$")
    nature: str = Field(..., description="Legal nature (CC, CA, CU, MET)")
    code_departement: str | None = Field(default=None, description="Main department code")


class Commune(BoundaryBase):
    """French commune (municipality)."""

    code_insee: str = Field(
        ...,
        description="INSEE code of the commune",
        pattern=r"^(\d{5}|2[AB]\d{3}|9[78]\d{3})$",
    )
    code_postal: str | None = Field(default=None, description="Main postal code")
    code_departement: str = Field(..., description="INSEE code of the department")
    code_region: str = Field(..., description="INSEE code of the region")
    code_epci: str | None = Field(default=None, description="SIREN code of the EPCI")
    population: int | None = Field(default=None, description="Municipal population")
    superficie: float | None = Field(default=None, description="Area in km²")


class CommuneAssocieeDeleguee(BoundaryBase):
    """Associated or delegated commune."""

    code_insee: str = Field(..., description="INSEE code")
    code_commune_parente: str = Field(..., description="INSEE code of the parent commune")
    type_entite: str = Field(..., description="Type: COMA (associated) or COMD (delegated)")
