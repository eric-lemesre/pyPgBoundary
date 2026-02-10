"""Client for the IGN Atom API (data.geopf.fr).

This module parses the Atom XML feeds exposed by the IGN
download platform to dynamically discover products
and their available editions.
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
    """Product discovered via the Atom API."""

    name: str = Field(..., description="Product name (e.g. ADMIN-EXPRESS-COG)")
    title: str = Field(default="", description="Human-readable title")
    description: str = Field(default="", description="Product description")
    resource_url: str = Field(default="", description="URL of the editions feed")


class AtomEdition(BaseModel):
    """Product edition discovered via the Atom API."""

    title: str = Field(..., description="Edition title")
    edition_date: str = Field(default="", description="Edition date")
    format: str = Field(default="", description="Format (GPKG, SHP, ...)")
    zone: str = Field(default="", description="Zone/territory (FRA, FXX, ...)")
    crs: str = Field(default="", description="Coordinate reference system")
    download_url: str = Field(default="", description="Download URL")


def _extract_namespaces(root: ET.Element) -> dict[str, str]:
    """Extract namespaces from the root element.

    Args:
        root: XML root element.

    Returns:
        Dictionary of namespace prefixes.
    """
    ns: dict[str, str] = {}
    tag = root.tag
    if tag.startswith("{"):
        default_ns = tag[1 : tag.index("}")]
        ns["atom"] = default_ns
    # Common namespaces in IGN Atom feeds
    for prefix, uri in [
        ("georss", "http://www.georss.org/georss"),
        ("inspire_dls", "http://inspire.ec.europa.eu/schemas/inspire_dls/1.0"),
        ("os", "http://a9.com/-/spec/opensearch/1.1/"),
    ]:
        ns.setdefault(prefix, uri)
    return ns


def _parse_product_entry(entry: ET.Element, ns: dict[str, str]) -> AtomProduct | None:
    """Parse a capabilities-level Atom entry into an AtomProduct.

    Args:
        entry: XML <entry> element.
        ns: Namespaces.

    Returns:
        AtomProduct or None if parsing fails.
    """
    title_el = entry.find("atom:title", ns)
    title = title_el.text.strip() if title_el is not None and title_el.text else ""

    summary_el = entry.find("atom:summary", ns)
    description = summary_el.text.strip() if summary_el is not None and summary_el.text else ""

    # Find the link to the editions feed
    resource_url = ""
    for link in entry.findall("atom:link", ns):
        href = link.get("href", "")
        rel = link.get("rel", "")
        if rel == "alternate" or (not rel and href):
            resource_url = href
            break

    # Extract the product name from the ID or title
    id_el = entry.find("atom:id", ns)
    entry_id = id_el.text.strip() if id_el is not None and id_el.text else ""

    # The name is usually in the ID or in the URL
    name = ""
    if resource_url:
        # Typical URL: .../resource/ADMIN-EXPRESS-COG
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
    """Parse an edition-level Atom entry into an AtomEdition.

    Args:
        entry: XML <entry> element.
        ns: Namespaces.
        product_name: Parent product name.

    Returns:
        AtomEdition or None if parsing fails.
    """
    title_el = entry.find("atom:title", ns)
    title = title_el.text.strip() if title_el is not None and title_el.text else ""

    if not title:
        return None

    # Update date
    updated_el = entry.find("atom:updated", ns)
    edition_date = ""
    if updated_el is not None and updated_el.text:
        edition_date = updated_el.text.strip()[:10]  # YYYY-MM-DD

    # Parse the title to extract format, zone, CRS
    # Typical title: ADMIN-EXPRESS-COG_4-0__GPKG_LAMB93_FXX_2025-01-01
    fmt = ""
    zone = ""
    crs = ""
    parts = title.split("_")
    # Look for known patterns in the title parts
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

    # Build the download URL
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
    """Client for the IGN Atom API.

    Scrapes Atom XML feeds to discover products
    and their available editions.
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
        """Fetch and parse an XML feed.

        Args:
            url: Feed URL.

        Returns:
            XML root element.

        Raises:
            AtomApiError: On network or parsing error.
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
        """Scrape the capabilities level to obtain the product list.

        Returns:
            List of available products.
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
        """Scrape the editions of a product.

        Args:
            product_name: Product name (e.g. ADMIN-EXPRESS-COG).
            format_filter: Filter by format (e.g. GPKG).
            zone_filter: Filter by zone (e.g. FRA).

        Returns:
            List of available editions.
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

            # Pagination handling
            next_url = None
            for link in root.findall("atom:link", ns):
                if link.get("rel") == "next":
                    next_url = link.get("href", "")
                    break

            url = next_url  # type: ignore[assignment]
            if url:
                page += 1
                logger.debug("Page %d: %s", page, url)

        # Apply filters
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
