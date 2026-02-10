"""Base interface for data sources.

This module defines the abstract interface for geographic data sources,
allowing different sources to be implemented (IGN, OpenStreetMap, etc.).
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
    """Base interface for geographic data sources.

    This abstract class defines the contract that all data sources
    must implement.
    """

    @abstractmethod
    def build_url(
        self,
        product: IGNProduct,
        file_format: FileFormat,
        territory: str,
        year: str,
    ) -> str:
        """Build the download URL for a product.

        Args:
            product: IGN product to download.
            file_format: Desired file format (SHP, GPKG).
            territory: Territory code (FRA, FXX, etc.).
            year: Data year.

        Returns:
            Complete download URL.
        """

    @abstractmethod
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
            force: Force re-download even if the file exists.

        Returns:
            Path to the downloaded file.
        """

    @abstractmethod
    def extract(
        self,
        archive_path: Path,
        dest_dir: Path | None = None,
        force: bool = False,
    ) -> Path:
        """Extract an archive.

        Args:
            archive_path: Path to the archive.
            dest_dir: Destination directory (same directory by default).
            force: Force re-extraction even if already extracted.

        Returns:
            Path to the extracted directory.
        """

    @abstractmethod
    def find_data_files(
        self,
        extract_dir: Path,
        product: IGNProduct,
        file_format: FileFormat,
    ) -> dict[str, Path]:
        """Find data files in an extracted directory.

        Args:
            extract_dir: Directory containing the extracted data.
            product: IGN product to search files for.
            file_format: File format (SHP or GPKG).

        Returns:
            Dictionary {layer_name: file_path}.
        """

    @abstractmethod
    def close(self) -> None:
        """Close resources used by the source."""

    def download_product(
        self,
        product: IGNProduct,
        file_format: FileFormat,
        territory: str,
        year: str,
        dest_dir: Path,
        force: bool = False,
    ) -> tuple[Path, dict[str, Path]]:
        """Download and extract a product, then return the files.

        This method combines the download, extraction, and file search
        steps into a single operation.

        Args:
            product: IGN product to download.
            file_format: Desired file format.
            territory: Territory code.
            year: Data year.
            dest_dir: Destination directory.
            force: Force re-download/extraction.

        Returns:
            Tuple (extracted_directory, files_dict).
        """
        url = self.build_url(product, file_format, territory, year)
        logger.info("Téléchargement depuis: %s", url)

        archive_path = self.download(url, dest_dir, force=force)
        extract_dir = self.extract(archive_path, force=force)
        data_files = self.find_data_files(extract_dir, product, file_format)

        return extract_dir, data_files
