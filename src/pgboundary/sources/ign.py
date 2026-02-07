"""Source de données IGN Geoservices.

Ce module implémente l'accès aux données du géoportail IGN,
incluant le téléchargement, l'extraction et la découverte de fichiers.
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
from pgboundary.products.catalog import FileFormat, TerritoryCode
from pgboundary.sources.base import DataSource

if TYPE_CHECKING:
    from pathlib import Path

    from pgboundary.config import Settings
    from pgboundary.products.catalog import IGNProduct

logger = logging.getLogger(__name__)

# URLs des données Admin Express sur data.geopf.fr (rétrocompatibilité)
ADMIN_EXPRESS_URLS = {
    "france_metropolitaine": (
        "https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS-COG/"
        "ADMIN-EXPRESS-COG_3-2__SHP_WGS84G_FRA_{year}/"
        "ADMIN-EXPRESS-COG_3-2__SHP_WGS84G_FRA_{year}.7z"
    ),
    "france_entiere": (
        "https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS-COG/"
        "ADMIN-EXPRESS-COG_3-2__SHP_WGS84G_FXX_{year}/"
        "ADMIN-EXPRESS-COG_3-2__SHP_WGS84G_FXX_{year}.7z"
    ),
}

# Couches disponibles dans Admin Express (rétrocompatibilité)
ADMIN_EXPRESS_LAYERS = [
    "REGION",
    "DEPARTEMENT",
    "ARRONDISSEMENT",
    "EPCI",
    "COMMUNE",
    "COMMUNE_ASSOCIEE_OU_DELEGUEE",
]

Territory = Literal["france_metropolitaine", "france_entiere"]

# Mapping des territoires legacy vers les codes standards
TERRITORY_MAPPING: dict[str, TerritoryCode] = {
    "france_metropolitaine": TerritoryCode.FRA,
    "france_entiere": TerritoryCode.FXX,
}

# Mapping inverse
TERRITORY_REVERSE_MAPPING: dict[TerritoryCode, str] = {
    TerritoryCode.FRA: "france_metropolitaine",
    TerritoryCode.FXX: "france_entiere",
}


class IGNDataSource(DataSource):
    """Source de données IGN Geoservices.

    Permet de télécharger et extraire les données géographiques
    depuis le géoportail de l'IGN (data.geopf.fr).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialise la source de données IGN.

        Args:
            settings: Configuration du module.
        """
        from pgboundary.config import Settings

        self.settings = settings or Settings()
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Retourne le client HTTP."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    # =========================================================================
    # Méthodes de l'interface DataSource
    # =========================================================================

    def build_url(
        self,
        product: IGNProduct,
        file_format: FileFormat,
        territory: str,
        year: str,
    ) -> str:
        """Construit l'URL de téléchargement selon le template du produit.

        Args:
            product: Produit IGN à télécharger.
            file_format: Format de fichier (SHP ou GPKG).
            territory: Code du territoire.
            year: Année des données.

        Returns:
            URL de téléchargement.
        """
        # Conversion du format en string IGN
        format_str = self._format_to_ign_string(file_format)

        # Utiliser le template du produit
        return product.url_template.format(
            version=product.version_pattern,
            format=format_str,
            crs="WGS84G",
            territory=territory,
            date=year,
        )

    def download(
        self,
        url: str,
        dest_dir: Path,
        filename: str | None = None,
        force: bool = False,
    ) -> Path:
        """Télécharge un fichier depuis une URL.

        Args:
            url: URL du fichier à télécharger.
            dest_dir: Répertoire de destination.
            filename: Nom du fichier (déduit de l'URL si non fourni).
            force: Force le re-téléchargement.

        Returns:
            Chemin vers le fichier téléchargé.

        Raises:
            DownloadError: En cas d'erreur de téléchargement.
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
        """Extrait l'archive téléchargée.

        Args:
            archive_path: Chemin vers l'archive.
            dest_dir: Répertoire de destination (déduit du nom d'archive si non fourni).
            force: Force la ré-extraction.

        Returns:
            Chemin vers le répertoire extrait.

        Raises:
            DownloadError: Si l'archive n'existe pas ou erreur d'extraction.
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
        """Trouve les fichiers de données selon le format et le produit.

        Args:
            extract_dir: Répertoire contenant les données extraites.
            product: Produit IGN pour lequel chercher les fichiers.
            file_format: Format de fichier (SHP ou GPKG).

        Returns:
            Dictionnaire {nom_couche: chemin_fichier}.
        """
        files: dict[str, Path] = {}

        if file_format == FileFormat.GPKG:
            # GPKG: un seul fichier contenant toutes les couches
            gpkg_files = list(extract_dir.glob("**/*.gpkg"))
            if gpkg_files:
                gpkg_path = gpkg_files[0]
                for layer in product.layers:
                    files[layer.name] = gpkg_path
        else:
            # SHP: un fichier par couche
            for layer in product.layers:
                pattern = f"**/{layer.name}.shp"
                matches = list(extract_dir.glob(pattern))
                if matches:
                    files[layer.name] = matches[0]
                    logger.debug("Shapefile trouvé: %s -> %s", layer.name, matches[0])

        return files

    def close(self) -> None:
        """Ferme le client HTTP."""
        if self._client is not None:
            self._client.close()
            self._client = None

    # =========================================================================
    # Méthodes de rétrocompatibilité (legacy)
    # =========================================================================

    def get_download_url(
        self,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
    ) -> str:
        """Construit l'URL de téléchargement (méthode legacy).

        Args:
            territory: Territoire à télécharger.
            year: Année des données.

        Returns:
            URL de téléchargement.
        """
        template = ADMIN_EXPRESS_URLS[territory]
        return template.format(year=year)

    def download_legacy(
        self,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        force: bool = False,
    ) -> Path:
        """Télécharge les données Admin Express (méthode legacy).

        Args:
            territory: Territoire à télécharger.
            year: Année des données.
            force: Force le re-téléchargement même si le fichier existe.

        Returns:
            Chemin vers le fichier téléchargé.

        Raises:
            DownloadError: En cas d'erreur de téléchargement.
        """
        data_dir = self.settings.ensure_data_dir()
        filename = f"admin_express_{territory}_{year}.7z"
        url = self.get_download_url(territory, year)

        return self.download(url, data_dir, filename, force)

    def find_shapefiles(self, extract_dir: Path) -> dict[str, Path]:
        """Trouve les shapefiles dans le répertoire extrait (méthode legacy).

        Args:
            extract_dir: Répertoire contenant les données extraites.

        Returns:
            Dictionnaire {nom_couche: chemin_shapefile}.
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
    # Méthodes utilitaires
    # =========================================================================

    @staticmethod
    def _format_to_ign_string(file_format: FileFormat) -> str:
        """Convertit un FileFormat en string IGN.

        Args:
            file_format: Format de fichier.

        Returns:
            String pour l'URL IGN (ex: "SHP_WGS84G").
        """
        if file_format == FileFormat.SHP:
            return "SHP_WGS84G"
        return "GPKG_WGS84G"

    @staticmethod
    def territory_to_code(territory: Territory) -> TerritoryCode:
        """Convertit un territoire legacy en TerritoryCode.

        Args:
            territory: Territoire legacy.

        Returns:
            Code de territoire.
        """
        return TERRITORY_MAPPING.get(territory, TerritoryCode.FRA)

    @staticmethod
    def code_to_territory(code: TerritoryCode) -> str:
        """Convertit un TerritoryCode en territoire legacy.

        Args:
            code: Code de territoire.

        Returns:
            Territoire legacy.
        """
        return TERRITORY_REVERSE_MAPPING.get(code, "france_metropolitaine")
