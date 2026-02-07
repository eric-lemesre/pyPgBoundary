"""Source de données IGN Admin Express."""

import logging
import zipfile
from pathlib import Path
from typing import Literal

import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from pgboundary.config import Settings
from pgboundary.exceptions import DownloadError

logger = logging.getLogger(__name__)

# URLs des données Admin Express sur data.gouv.fr
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

# Couches disponibles dans Admin Express
ADMIN_EXPRESS_LAYERS = [
    "REGION",
    "DEPARTEMENT",
    "ARRONDISSEMENT",
    "EPCI",
    "COMMUNE",
    "COMMUNE_ASSOCIEE_OU_DELEGUEE",
]

Territory = Literal["france_metropolitaine", "france_entiere"]


class IGNDataSource:
    """Source de données IGN Admin Express.

    Permet de télécharger et extraire les données Admin Express COG
    depuis le géoservice de l'IGN.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialise la source de données IGN.

        Args:
            settings: Configuration du module.
        """
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

    def get_download_url(
        self,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
    ) -> str:
        """Construit l'URL de téléchargement.

        Args:
            territory: Territoire à télécharger.
            year: Année des données.

        Returns:
            URL de téléchargement.
        """
        template = ADMIN_EXPRESS_URLS[territory]
        return template.format(year=year)

    def download(
        self,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        force: bool = False,
    ) -> Path:
        """Télécharge les données Admin Express.

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
        filepath = data_dir / filename

        if filepath.exists() and not force:
            logger.info("Fichier déjà téléchargé: %s", filepath)
            return filepath

        url = self.get_download_url(territory, year)
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

    def extract(self, archive_path: Path, force: bool = False) -> Path:
        """Extrait l'archive téléchargée.

        Args:
            archive_path: Chemin vers l'archive.
            force: Force la ré-extraction.

        Returns:
            Chemin vers le répertoire extrait.

        Raises:
            DownloadError: Si l'archive n'existe pas ou erreur d'extraction.
        """
        if not archive_path.exists():
            raise DownloadError(f"Archive introuvable: {archive_path}")

        extract_dir = archive_path.parent / archive_path.stem

        if extract_dir.exists() and not force:
            logger.info("Données déjà extraites: %s", extract_dir)
            return extract_dir

        logger.info("Extraction de: %s", archive_path)

        try:
            if archive_path.suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(extract_dir)
            elif archive_path.suffix == ".7z":
                import subprocess

                subprocess.run(
                    ["7z", "x", "-y", f"-o{extract_dir}", str(archive_path)],
                    check=True,
                    capture_output=True,
                )
            else:
                raise DownloadError(f"Format d'archive non supporté: {archive_path.suffix}")

            logger.info("Extraction terminée: %s", extract_dir)
            return extract_dir

        except Exception as e:
            raise DownloadError(f"Erreur d'extraction: {e}") from e

    def find_shapefiles(self, extract_dir: Path) -> dict[str, Path]:
        """Trouve les shapefiles dans le répertoire extrait.

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

    def close(self) -> None:
        """Ferme le client HTTP."""
        if self._client is not None:
            self._client.close()
            self._client = None
