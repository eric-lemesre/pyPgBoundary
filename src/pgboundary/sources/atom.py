"""Client pour l'API Atom IGN (data.geopf.fr).

Ce module parse les flux Atom XML exposés par la plateforme de
téléchargement IGN pour découvrir dynamiquement les produits
et leurs éditions disponibles.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from pydantic import BaseModel, Field

from pgboundary.exceptions import AtomApiError

logger = logging.getLogger(__name__)

BASE_URL = "https://data.geopf.fr/telechargement"


class AtomProduct(BaseModel):
    """Produit découvert via l'API Atom."""

    name: str = Field(..., description="Nom du produit (ex: ADMIN-EXPRESS-COG)")
    title: str = Field(default="", description="Titre lisible")
    description: str = Field(default="", description="Description du produit")
    resource_url: str = Field(default="", description="URL du flux des éditions")


class AtomEdition(BaseModel):
    """Édition d'un produit découverte via l'API Atom."""

    title: str = Field(..., description="Titre de l'édition")
    edition_date: str = Field(default="", description="Date de l'édition")
    format: str = Field(default="", description="Format (GPKG, SHP, ...)")
    zone: str = Field(default="", description="Zone/territoire (FRA, FXX, ...)")
    crs: str = Field(default="", description="Système de coordonnées")
    download_url: str = Field(default="", description="URL de téléchargement")


def _extract_namespaces(root: ET.Element) -> dict[str, str]:
    """Extrait les namespaces depuis l'élément racine.

    Args:
        root: Élément racine XML.

    Returns:
        Dictionnaire des préfixes de namespace.
    """
    ns: dict[str, str] = {}
    tag = root.tag
    if tag.startswith("{"):
        default_ns = tag[1 : tag.index("}")]
        ns["atom"] = default_ns
    # Namespaces courants dans les flux Atom IGN
    for prefix, uri in [
        ("georss", "http://www.georss.org/georss"),
        ("inspire_dls", "http://inspire.ec.europa.eu/schemas/inspire_dls/1.0"),
        ("os", "http://a9.com/-/spec/opensearch/1.1/"),
    ]:
        ns.setdefault(prefix, uri)
    return ns


def _parse_product_entry(entry: ET.Element, ns: dict[str, str]) -> AtomProduct | None:
    """Parse une entrée Atom de niveau capabilities en AtomProduct.

    Args:
        entry: Élément XML <entry>.
        ns: Namespaces.

    Returns:
        AtomProduct ou None si le parsing échoue.
    """
    title_el = entry.find("atom:title", ns)
    title = title_el.text.strip() if title_el is not None and title_el.text else ""

    summary_el = entry.find("atom:summary", ns)
    description = summary_el.text.strip() if summary_el is not None and summary_el.text else ""

    # Chercher le lien vers le flux des éditions
    resource_url = ""
    for link in entry.findall("atom:link", ns):
        href = link.get("href", "")
        rel = link.get("rel", "")
        if rel == "alternate" or (not rel and href):
            resource_url = href
            break

    # Extraire le nom du produit depuis l'ID ou le titre
    id_el = entry.find("atom:id", ns)
    entry_id = id_el.text.strip() if id_el is not None and id_el.text else ""

    # Le nom est généralement dans l'ID ou dans l'URL
    name = ""
    if resource_url:
        # URL typique : .../resource/ADMIN-EXPRESS-COG
        parts = resource_url.rstrip("/").split("/")
        if parts:
            name = parts[-1]
    if not name and entry_id:
        name = entry_id.rstrip("/").split("/")[-1]
    if not name:
        name = title

    if not name:
        return None

    return AtomProduct(
        name=name,
        title=title,
        description=description,
        resource_url=resource_url,
    )


def _parse_edition_entry(
    entry: ET.Element,
    ns: dict[str, str],
    product_name: str,
) -> AtomEdition | None:
    """Parse une entrée Atom de niveau édition en AtomEdition.

    Args:
        entry: Élément XML <entry>.
        ns: Namespaces.
        product_name: Nom du produit parent.

    Returns:
        AtomEdition ou None si le parsing échoue.
    """
    title_el = entry.find("atom:title", ns)
    title = title_el.text.strip() if title_el is not None and title_el.text else ""

    if not title:
        return None

    # Date de mise à jour
    updated_el = entry.find("atom:updated", ns)
    edition_date = ""
    if updated_el is not None and updated_el.text:
        edition_date = updated_el.text.strip()[:10]  # YYYY-MM-DD

    # Parser le titre pour extraire format, zone, CRS
    # Titre typique : ADMIN-EXPRESS-COG_4-0__GPKG_LAMB93_FXX_2025-01-01
    fmt = ""
    zone = ""
    crs = ""
    parts = title.split("_")
    # Chercher les patterns connus dans les parties du titre
    known_formats = {"GPKG", "SHP", "CSV"}
    known_crs = {
        "LAMB93",
        "WGS84G",
        "UTM",
        "RGAF09UTM20",
        "RGR92UTM40S",
        "RGSPM06U21",
        "RGFG95UTM22",
        "RGM04UTM38S",
    }
    known_zones = {"FRA", "FXX", "GLP", "MTQ", "GUF", "REU", "MYT"}

    for part in parts:
        part_upper = part.upper()
        if part_upper in known_formats:
            fmt = part_upper
        elif part_upper in known_crs:
            crs = part_upper
        elif part_upper in known_zones:
            zone = part_upper

    # Construire l'URL de téléchargement
    download_url = f"{BASE_URL}/download/{product_name}/{title}/{title}.7z"

    return AtomEdition(
        title=title,
        edition_date=edition_date,
        format=fmt,
        zone=zone,
        crs=crs,
        download_url=download_url,
    )


class AtomClient:
    """Client pour l'API Atom IGN.

    Scrape les flux Atom XML pour découvrir les produits
    et leurs éditions disponibles.
    """

    def __init__(self, base_url: str = BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> AtomClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _fetch_xml(self, url: str) -> ET.Element:
        """Récupère et parse un flux XML.

        Args:
            url: URL du flux.

        Returns:
            Élément racine XML.

        Raises:
            AtomApiError: En cas d'erreur réseau ou de parsing.
        """
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except httpx.HTTPStatusError as e:
            raise AtomApiError(f"Erreur HTTP {e.response.status_code} pour {url}") from e
        except httpx.RequestError as e:
            raise AtomApiError(f"Erreur réseau pour {url}: {e}") from e
        except ET.ParseError as e:
            raise AtomApiError(f"Erreur de parsing XML pour {url}: {e}") from e

    def fetch_capabilities(self) -> list[AtomProduct]:
        """Scrape le niveau capabilities pour obtenir la liste des produits.

        Returns:
            Liste des produits disponibles.
        """
        url = f"{self.base_url}/capabilities"
        logger.info("Scraping capabilities: %s", url)

        root = self._fetch_xml(url)
        ns = _extract_namespaces(root)

        products: list[AtomProduct] = []
        for entry in root.findall("atom:entry", ns):
            product = _parse_product_entry(entry, ns)
            if product:
                products.append(product)

        logger.info("Produits découverts: %d", len(products))
        return products

    def fetch_product_editions(
        self,
        product_name: str,
        format_filter: str | None = None,
        zone_filter: str | None = None,
    ) -> list[AtomEdition]:
        """Scrape les éditions d'un produit.

        Args:
            product_name: Nom du produit (ex: ADMIN-EXPRESS-COG).
            format_filter: Filtrer par format (ex: GPKG).
            zone_filter: Filtrer par zone (ex: FRA).

        Returns:
            Liste des éditions disponibles.
        """
        url = f"{self.base_url}/resource/{product_name}"
        logger.info("Scraping éditions de %s: %s", product_name, url)

        all_editions: list[AtomEdition] = []
        page = 1

        while url:
            root = self._fetch_xml(url)
            ns = _extract_namespaces(root)

            for entry in root.findall("atom:entry", ns):
                edition = _parse_edition_entry(entry, ns, product_name)
                if edition:
                    all_editions.append(edition)

            # Gestion de la pagination
            next_url = None
            for link in root.findall("atom:link", ns):
                if link.get("rel") == "next":
                    next_url = link.get("href", "")
                    break

            url = next_url  # type: ignore[assignment]
            if url:
                page += 1
                logger.debug("Page %d: %s", page, url)

        # Appliquer les filtres
        editions = all_editions
        if format_filter:
            fmt_upper = format_filter.upper()
            editions = [e for e in editions if e.format == fmt_upper]
        if zone_filter:
            zone_upper = zone_filter.upper()
            editions = [e for e in editions if e.zone == zone_upper]

        logger.info(
            "Éditions découvertes pour %s: %d (filtrées: %d)",
            product_name,
            len(all_editions),
            len(editions),
        )
        return editions
