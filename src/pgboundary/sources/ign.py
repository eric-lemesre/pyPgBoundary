"""IGN Geoservices data source.

This module implements access to IGN geoportal data,
including downloading, extracting, and discovering data files.
"""

from __future__ import annotations

import logging
import subprocess
import zipfile
from typing import TYPE_CHECKING, Literal

import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from pgboundary.exceptions import DownloadError
from pgboundary.products.catalog import FileFormat, TerritoryCode, validate_department_code
from pgboundary.sources.base import DataSource
from pgboundary.sources.loader import load_territory_crs

if TYPE_CHECKING:
    from pathlib import Path

    from pgboundary.config import Settings
    from pgboundary.products.catalog import IGNProduct

logger = logging.getLogger(__name__)

# Territory → CRS mapping loaded from YAML
_territory_crs: dict[str, str] | None = None


def _get_territory_crs() -> dict[str, str]:
    """Return the territory → CRS mapping, lazily loaded."""
    global _territory_crs
    if _territory_crs is None:
        _territory_crs = load_territory_crs()
    return _territory_crs


# Admin Express data URLs on data.geopf.fr (backward compatibility)
ADMIN_EXPRESS_URLS = {
    "france_metropolitaine": (
        "https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS-COG/"
        "ADMIN-EXPRESS-COG_4-0__GPKG_LAMB93_FXX_{year}/"
        "ADMIN-EXPRESS-COG_4-0__GPKG_LAMB93_FXX_{year}.7z"
    ),
    "france_entiere": (
        "https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS-COG/"
        "ADMIN-EXPRESS-COG_4-0__GPKG_WGS84G_FRA_{year}/"
        "ADMIN-EXPRESS-COG_4-0__GPKG_WGS84G_FRA_{year}.7z"
    ),
}

# Available layers in Admin Express (backward compatibility)
ADMIN_EXPRESS_LAYERS = [
    "REGION",
    "DEPARTEMENT",
    "ARRONDISSEMENT",
    "EPCI",
    "COMMUNE",
    "COMMUNE_ASSOCIEE_OU_DELEGUEE",
]

Territory = Literal["france_metropolitaine", "france_entiere"]

# Mapping from legacy territories to standard codes
TERRITORY_MAPPING: dict[str, TerritoryCode] = {
    "france_metropolitaine": TerritoryCode.FRA,
    "france_entiere": TerritoryCode.FXX,
}

# Reverse mapping
TERRITORY_REVERSE_MAPPING: dict[TerritoryCode, str] = {
    TerritoryCode.FRA: "france_metropolitaine",
    TerritoryCode.FXX: "france_entiere",
}


class IGNDataSource(DataSource):
    """IGN Geoservices data source.

    Downloads and extracts geographic data
    from the IGN geoportal (data.geopf.fr).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the IGN data source.

        Args:
            settings: Module configuration.
        """
        from pgboundary.config import Settings

        self.settings = settings or Settings()
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Return the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    # =========================================================================
    # DataSource interface methods
    # =========================================================================

    def build_url(
        self,
        product: IGNProduct,
        file_format: FileFormat,
        territory: str,
        edition: str,
    ) -> str:
        """Build the download URL from the product template.

        Args:
            product: IGN product to download.
            file_format: File format (SHP or GPKG).
            territory: Territory code.
            edition: Data edition (YYYY or YYYY-MM-DD).

        Returns:
            Download URL.
        """
        # Convert format to IGN string (without CRS)
        format_str = self._format_to_ign_string(file_format)

        # Resolve CRS from the territorial mapping
        crs_mapping = _get_territory_crs()
        crs = crs_mapping.get(territory, "WGS84G")

        # Normalize the date: YYYY → YYYY-01-01
        date_str = edition
        if len(edition) == 4 and edition.isdigit():
            date_str = f"{edition}-01-01"

        # Use the product template
        return product.url_template.format(
            version=product.version_pattern,
            format=format_str,
            crs=crs,
            territory=territory,
            date=date_str,
        )

    @staticmethod
    def build_department_url(product: IGNProduct, department: str) -> str:
        """Build the download URL for a specific department.

        Args:
            product: IGN product with department_url_template.
            department: Department code (e.g., "75", "2A", "974").

        Returns:
            Download URL for the department.

        Raises:
            ValueError: If the department code is invalid or the product
                does not support per-department downloads.
        """
        if not product.supports_department_download:
            raise ValueError(
                f"Le produit '{product.id}' ne supporte pas le téléchargement par département."
            )
        if not validate_department_code(department):
            raise ValueError(
                f"Code département invalide: '{department}'. "
                f"Codes valides: 01-19, 2A, 2B, 21-95, 971-976."
            )
        assert product.department_url_template is not None  # guaranteed by the check above
        return product.department_url_template.format(department=department)

    def download(
        self,
        url: str,
        dest_dir: Path,
        filename: str | None = None,
        force: bool = False,
    ) -> Path:
        """Download a file from a URL.

        Args:
            url: URL of the file to download.
            dest_dir: Destination directory.
            filename: File name (inferred from the URL if not provided).
            force: Force re-download.

        Returns:
            Path to the downloaded file.

        Raises:
            DownloadError: If a download error occurs.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            filename = url.split("/")[-1]

        filepath = dest_dir / filename

        if filepath.exists() and not force:
            logger.info("Fichier déjà téléchargé: %s", filepath)
            return filepath

        logger.info("Téléchargement depuis: %s", url)

        try:
            with self.client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))

                with Progress(
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                ) as progress:
                    task = progress.add_task("Téléchargement", total=total)

                    with filepath.open("wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))

            logger.info("Téléchargement terminé: %s", filepath)
            return filepath

        except httpx.HTTPStatusError as e:
            raise DownloadError(f"Erreur HTTP {e.response.status_code}: {url}") from e
        except httpx.RequestError as e:
            raise DownloadError(f"Erreur de requête: {e}") from e

    def extract(
        self,
        archive_path: Path,
        dest_dir: Path | None = None,
        force: bool = False,
    ) -> Path:
        """Extract the downloaded archive.

        Args:
            archive_path: Path to the archive.
            dest_dir: Destination directory (inferred from the archive name if not provided).
            force: Force re-extraction.

        Returns:
            Path to the extracted directory.

        Raises:
            DownloadError: If the archive does not exist or an extraction error occurs.
        """
        if not archive_path.exists():
            raise DownloadError(f"Archive introuvable: {archive_path}")

        if dest_dir is None:
            dest_dir = archive_path.parent / archive_path.stem

        if dest_dir.exists() and not force:
            logger.info("Données déjà extraites: %s", dest_dir)
            return dest_dir

        logger.info("Extraction de: %s", archive_path)

        try:
            if archive_path.suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(dest_dir)
            elif archive_path.suffix == ".7z":
                subprocess.run(
                    ["7z", "x", "-y", f"-o{dest_dir}", str(archive_path)],
                    check=True,
                    capture_output=True,
                )
            else:
                raise DownloadError(f"Format d'archive non supporté: {archive_path.suffix}")

            logger.info("Extraction terminée: %s", dest_dir)
            return dest_dir

        except subprocess.CalledProcessError as e:
            raise DownloadError(f"Erreur d'extraction 7z: {e.stderr.decode()}") from e
        except Exception as e:
            raise DownloadError(f"Erreur d'extraction: {e}") from e

    def find_data_files(
        self,
        extract_dir: Path,
        product: IGNProduct,
        file_format: FileFormat,
    ) -> dict[str, Path]:
        """Find data files matching the format and product.

        Args:
            extract_dir: Directory containing the extracted data.
            product: IGN product to search files for.
            file_format: File format (SHP or GPKG).

        Returns:
            Dictionary {layer_name: file_path}.
        """
        files: dict[str, Path] = {}

        if file_format == FileFormat.GPKG:
            # GPKG: a single file containing all layers
            gpkg_files = list(extract_dir.glob("**/*.gpkg"))
            if gpkg_files:
                gpkg_path = gpkg_files[0]
                for layer in product.layers:
                    files[layer.name] = gpkg_path
        else:
            # SHP: one file per layer
            for layer in product.layers:
                pattern = f"**/{layer.name}.shp"
                matches = list(extract_dir.glob(pattern))
                if matches:
                    files[layer.name] = matches[0]
                    logger.debug("Shapefile trouvé: %s -> %s", layer.name, matches[0])

        return files

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    # =========================================================================
    # Backward compatibility methods (legacy)
    # =========================================================================

    def get_download_url(
        self,
        territory: Territory = "france_metropolitaine",
        edition: str = "2024",
    ) -> str:
        """Build the download URL (legacy method).

        Args:
            territory: Territory to download.
            edition: Data edition.

        Returns:
            Download URL.
        """
        template = ADMIN_EXPRESS_URLS[territory]
        return template.format(year=edition)

    def download_legacy(
        self,
        territory: Territory = "france_metropolitaine",
        edition: str = "2024",
        force: bool = False,
    ) -> Path:
        """Download Admin Express data (legacy method).

        Args:
            territory: Territory to download.
            edition: Data edition.
            force: Force re-download even if the file already exists.

        Returns:
            Path to the downloaded file.

        Raises:
            DownloadError: If a download error occurs.
        """
        data_dir = self.settings.ensure_data_dir()
        filename = f"admin_express_{territory}_{edition}.7z"
        url = self.get_download_url(territory, edition)

        return self.download(url, data_dir, filename, force)

    def find_shapefiles(self, extract_dir: Path) -> dict[str, Path]:
        """Find shapefiles in the extracted directory (legacy method).

        Args:
            extract_dir: Directory containing the extracted data.

        Returns:
            Dictionary {layer_name: shapefile_path}.
        """
        shapefiles: dict[str, Path] = {}

        for layer in ADMIN_EXPRESS_LAYERS:
            pattern = f"**/{layer}.shp"
            matches = list(extract_dir.glob(pattern))
            if matches:
                shapefiles[layer] = matches[0]
                logger.debug("Shapefile trouvé: %s -> %s", layer, matches[0])

        return shapefiles

    # =========================================================================
    # Utility methods
    # =========================================================================

    @staticmethod
    def _format_to_ign_string(file_format: FileFormat) -> str:
        """Convert a FileFormat to an IGN string.

        The CRS is now handled separately in build_url() via the territorial
        mapping, so this format no longer contains the CRS suffix.

        Args:
            file_format: File format.

        Returns:
            String for the IGN URL (e.g., "SHP", "GPKG").
        """
        if file_format == FileFormat.SHP:
            return "SHP"
        return "GPKG"

    @staticmethod
    def territory_to_code(territory: Territory) -> TerritoryCode:
        """Convert a legacy territory to a TerritoryCode.

        Args:
            territory: Legacy territory.

        Returns:
            Territory code.
        """
        return TERRITORY_MAPPING.get(territory, TerritoryCode.FRA)

    @staticmethod
    def code_to_territory(code: TerritoryCode) -> str:
        """Convert a TerritoryCode to a legacy territory.

        Args:
            code: Territory code.

        Returns:
            Legacy territory.
        """
        return TERRITORY_REVERSE_MAPPING.get(code, "france_metropolitaine")
