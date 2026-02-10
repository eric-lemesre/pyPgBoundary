"""Dynamically generated SQLAlchemy models for administrative boundaries."""

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, Uuid
from sqlalchemy.orm import DeclarativeBase

from pgboundary.schema_config import SchemaConfig


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


def create_metadata(config: SchemaConfig) -> MetaData:
    """Create the MetaData object with the appropriate schema.

    Args:
        config: Schema configuration.

    Returns:
        Configured MetaData.
    """
    schema = config.get_schema_name()
    return MetaData(schema=schema)


def create_region_table(metadata: MetaData, config: SchemaConfig) -> Table:
    """Create the regions table.

    Args:
        metadata: SQLAlchemy MetaData.
        config: Schema configuration.

    Returns:
        SQLAlchemy Table.
    """
    table_name = config.get_full_table_name("region")
    fp = config.field_prefixes

    return Table(
        table_name,
        metadata,
        Column("uid", Uuid, primary_key=True, default=uuid.uuid4),
        Column(f"{fp.label}nom", String(255), nullable=False, index=True),
        Column(f"{fp.code}insee", String(2), nullable=False, unique=True, index=True),
        Column(f"{fp.code}chef_lieu", String(5), nullable=True),
        Column(f"{fp.date}creation", Date, nullable=True),
        Column(f"{fp.date}modification", Date, nullable=True),
        Column(
            "geometry", Geometry(geometry_type="MULTIPOLYGON", srid=config.srid), nullable=False
        ),
    )


def create_departement_table(metadata: MetaData, config: SchemaConfig) -> Table:
    """Create the departments table.

    Args:
        metadata: SQLAlchemy MetaData.
        config: Schema configuration.

    Returns:
        SQLAlchemy Table.
    """
    table_name = config.get_full_table_name("departement")
    fp = config.field_prefixes

    return Table(
        table_name,
        metadata,
        Column("uid", Uuid, primary_key=True, default=uuid.uuid4),
        Column(f"{fp.label}nom", String(255), nullable=False, index=True),
        Column(f"{fp.code}insee", String(3), nullable=False, unique=True, index=True),
        Column(f"{fp.code}region", String(2), nullable=False, index=True),
        Column(f"{fp.code}chef_lieu", String(5), nullable=True),
        Column(f"{fp.date}creation", Date, nullable=True),
        Column(f"{fp.date}modification", Date, nullable=True),
        Column(
            "geometry", Geometry(geometry_type="MULTIPOLYGON", srid=config.srid), nullable=False
        ),
    )


def create_epci_table(metadata: MetaData, config: SchemaConfig) -> Table:
    """Create the EPCI table.

    Args:
        metadata: SQLAlchemy MetaData.
        config: Schema configuration.

    Returns:
        SQLAlchemy Table.
    """
    table_name = config.get_full_table_name("epci")
    fp = config.field_prefixes

    return Table(
        table_name,
        metadata,
        Column("uid", Uuid, primary_key=True, default=uuid.uuid4),
        Column(f"{fp.label}nom", String(255), nullable=False, index=True),
        Column(f"{fp.code}siren", String(9), nullable=False, unique=True, index=True),
        Column(f"{fp.label}nature", String(10), nullable=False),
        Column(f"{fp.code}departement", String(3), nullable=True, index=True),
        Column(f"{fp.date}creation", Date, nullable=True),
        Column(f"{fp.date}modification", Date, nullable=True),
        Column(
            "geometry", Geometry(geometry_type="MULTIPOLYGON", srid=config.srid), nullable=False
        ),
    )


def create_commune_table(metadata: MetaData, config: SchemaConfig) -> Table:
    """Create the communes table.

    Args:
        metadata: SQLAlchemy MetaData.
        config: Schema configuration.

    Returns:
        SQLAlchemy Table.
    """
    table_name = config.get_full_table_name("commune")
    fp = config.field_prefixes

    return Table(
        table_name,
        metadata,
        Column("uid", Uuid, primary_key=True, default=uuid.uuid4),
        Column(f"{fp.label}nom", String(255), nullable=False, index=True),
        Column(f"{fp.code}insee", String(5), nullable=False, unique=True, index=True),
        Column(f"{fp.code}postal", String(5), nullable=True),
        Column(f"{fp.code}departement", String(3), nullable=False, index=True),
        Column(f"{fp.code}region", String(2), nullable=False, index=True),
        Column(f"{fp.code}epci", String(9), nullable=True, index=True),
        Column("population", Integer, nullable=True),
        Column("superficie", Float, nullable=True),
        Column(f"{fp.date}creation", Date, nullable=True),
        Column(f"{fp.date}modification", Date, nullable=True),
        Column(
            "geometry", Geometry(geometry_type="MULTIPOLYGON", srid=config.srid), nullable=False
        ),
    )


def create_commune_associee_deleguee_table(metadata: MetaData, config: SchemaConfig) -> Table:
    """Create the associated and delegated communes table.

    Args:
        metadata: SQLAlchemy MetaData.
        config: Schema configuration.

    Returns:
        SQLAlchemy Table.
    """
    table_name = config.get_full_table_name("commune_associee_deleguee")
    fp = config.field_prefixes

    return Table(
        table_name,
        metadata,
        Column("uid", Uuid, primary_key=True, default=uuid.uuid4),
        Column(f"{fp.label}nom", String(255), nullable=False, index=True),
        Column(f"{fp.code}insee", String(5), nullable=False, index=True),
        Column(f"{fp.code}commune_parente", String(5), nullable=False, index=True),
        Column(f"{fp.label}type_entite", String(4), nullable=False),
        Column(f"{fp.date}creation", Date, nullable=True),
        Column(f"{fp.date}modification", Date, nullable=True),
        Column(
            "geometry", Geometry(geometry_type="MULTIPOLYGON", srid=config.srid), nullable=False
        ),
    )


class TableFactory:
    """Factory for creating tables according to the configuration."""

    def __init__(self, config: SchemaConfig) -> None:
        """Initialize the factory.

        Args:
            config: Schema configuration.
        """
        self.config = config
        self.metadata = create_metadata(config)
        self._tables: dict[str, Table] = {}

    @property
    def region(self) -> Table:
        """Return the regions table."""
        if "region" not in self._tables:
            self._tables["region"] = create_region_table(self.metadata, self.config)
        return self._tables["region"]

    @property
    def departement(self) -> Table:
        """Return the departments table."""
        if "departement" not in self._tables:
            self._tables["departement"] = create_departement_table(self.metadata, self.config)
        return self._tables["departement"]

    @property
    def epci(self) -> Table:
        """Return the EPCI table."""
        if "epci" not in self._tables:
            self._tables["epci"] = create_epci_table(self.metadata, self.config)
        return self._tables["epci"]

    @property
    def commune(self) -> Table:
        """Return the communes table."""
        if "commune" not in self._tables:
            self._tables["commune"] = create_commune_table(self.metadata, self.config)
        return self._tables["commune"]

    @property
    def commune_associee_deleguee(self) -> Table:
        """Return the associated/delegated communes table."""
        if "commune_associee_deleguee" not in self._tables:
            self._tables["commune_associee_deleguee"] = create_commune_associee_deleguee_table(
                self.metadata, self.config
            )
        return self._tables["commune_associee_deleguee"]

    def get_all_tables(self) -> dict[str, Table]:
        """Return all tables.

        Returns:
            Dictionary of tables.
        """
        _ = self.region
        _ = self.departement
        _ = self.epci
        _ = self.commune
        _ = self.commune_associee_deleguee
        return self._tables

    def get_column_mapping(self, layer: str) -> dict[str, str]:
        """Return the column mapping from Admin Express to DB columns.

        Args:
            layer: Layer name (REGION, DEPARTEMENT, etc.)

        Returns:
            Mapping dictionary {source_column: target_column}.
        """
        fp = self.config.field_prefixes

        mappings = {
            "REGION": {
                "NOM": f"{fp.label}nom",
                "INSEE_REG": f"{fp.code}insee",
                "CHEF_LIEU": f"{fp.code}chef_lieu",
            },
            "DEPARTEMENT": {
                "NOM": f"{fp.label}nom",
                "INSEE_DEP": f"{fp.code}insee",
                "INSEE_REG": f"{fp.code}region",
                "CHEF_LIEU": f"{fp.code}chef_lieu",
            },
            "EPCI": {
                "NOM": f"{fp.label}nom",
                "CODE_SIREN": f"{fp.code}siren",
                "NATURE": f"{fp.label}nature",
            },
            "COMMUNE": {
                "NOM": f"{fp.label}nom",
                "INSEE_COM": f"{fp.code}insee",
                "CODE_POSTAL": f"{fp.code}postal",
                "INSEE_DEP": f"{fp.code}departement",
                "INSEE_REG": f"{fp.code}region",
                "SIREN_EPCI": f"{fp.code}epci",
                "POPULATION": "population",
                "SUPERFICIE": "superficie",
            },
            "COMMUNE_ASSOCIEE_OU_DELEGUEE": {
                "NOM": f"{fp.label}nom",
                "INSEE_CAD": f"{fp.code}insee",
                "INSEE_COM": f"{fp.code}commune_parente",
                "TYPE": f"{fp.label}type_entite",
            },
        }

        return mappings.get(layer, {})
