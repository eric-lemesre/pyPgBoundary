"""Interface de base pour les sources de données.

Ce module définit l'interface abstraite pour les sources de données
géographiques, permettant d'implémenter différentes sources
(IGN, OpenStreetMap, etc.).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from pgboundary.products.catalog import FileFormat, IGNProduct

logger = logging.getLogger(__name__)


class DataSource(ABC):
    """Interface de base pour les sources de données géographiques.

    Cette classe abstraite définit le contrat que toutes les sources
    de données doivent implémenter.
    """

    @abstractmethod
    def build_url(
        self,
        product: IGNProduct,
        file_format: FileFormat,
        territory: str,
        year: str,
    ) -> str:
        """Construit l'URL de téléchargement pour un produit.

        Args:
            product: Produit IGN à télécharger.
            file_format: Format de fichier souhaité (SHP, GPKG).
            territory: Code du territoire (FRA, FXX, etc.).
            year: Année des données.

        Returns:
            URL de téléchargement complète.
        """

    @abstractmethod
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
            force: Force le re-téléchargement même si le fichier existe.

        Returns:
            Chemin vers le fichier téléchargé.
        """

    @abstractmethod
    def extract(
        self,
        archive_path: Path,
        dest_dir: Path | None = None,
        force: bool = False,
    ) -> Path:
        """Extrait une archive.

        Args:
            archive_path: Chemin vers l'archive.
            dest_dir: Répertoire de destination (même répertoire par défaut).
            force: Force la ré-extraction même si déjà extraite.

        Returns:
            Chemin vers le répertoire extrait.
        """

    @abstractmethod
    def find_data_files(
        self,
        extract_dir: Path,
        product: IGNProduct,
        file_format: FileFormat,
    ) -> dict[str, Path]:
        """Trouve les fichiers de données dans un répertoire extrait.

        Args:
            extract_dir: Répertoire contenant les données extraites.
            product: Produit IGN pour lequel chercher les fichiers.
            file_format: Format de fichier (SHP ou GPKG).

        Returns:
            Dictionnaire {nom_couche: chemin_fichier}.
        """

    @abstractmethod
    def close(self) -> None:
        """Ferme les ressources utilisées par la source."""

    def download_product(
        self,
        product: IGNProduct,
        file_format: FileFormat,
        territory: str,
        year: str,
        dest_dir: Path,
        force: bool = False,
    ) -> tuple[Path, dict[str, Path]]:
        """Télécharge et extrait un produit, puis retourne les fichiers.

        Cette méthode combine les étapes de téléchargement, extraction
        et recherche de fichiers en une seule opération.

        Args:
            product: Produit IGN à télécharger.
            file_format: Format de fichier souhaité.
            territory: Code du territoire.
            year: Année des données.
            dest_dir: Répertoire de destination.
            force: Force le re-téléchargement/extraction.

        Returns:
            Tuple (répertoire_extrait, dict_fichiers).
        """
        url = self.build_url(product, file_format, territory, year)
        logger.info("Téléchargement depuis: %s", url)

        archive_path = self.download(url, dest_dir, force=force)
        extract_dir = self.extract(archive_path, force=force)
        data_files = self.find_data_files(extract_dir, product, file_format)

        return extract_dir, data_files
