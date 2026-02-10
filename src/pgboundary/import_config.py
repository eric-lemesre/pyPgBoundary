"""Geographic data import configuration.

This module defines the configuration structures for IGN product imports
with historization support.

Decision matrix for geometric similarity:
- [0.95 - 1.00] : IDENTICAL - Automatic merge without verification
- [0.80 - 0.95] : LIKELY_MATCH - Strong match, validation if attributes differ
- [0.50 - 0.80] : SUSPECT - Potential conflict or temporal change
- < 0.50 : DISTINCT - Distinct objects
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field


class SimilarityMethod(StrEnum):
    """Geometric comparison methods for historization."""

    MD5 = "md5"  # Hash MD5 des coordonnées (identité stricte)
    JACCARD = "jaccard"  # Indice de Jaccard / IoU (superposition spatiale)
    HAUSDORFF = "hausdorff"  # Distance de Hausdorff (ressemblance des formes)
    COMBINED = "combined"  # Combinaison IoU + Hausdorff (recommandé)


class SimilarityLevel(StrEnum):
    """Similarity levels according to the decision matrix."""

    IDENTICAL = "identical"  # [0.95 - 1.00] Fusion automatique
    LIKELY_MATCH = "likely_match"  # [0.80 - 0.95] Correspondance forte
    SUSPECT = "suspect"  # [0.50 - 0.80] Conflit potentiel
    DISTINCT = "distinct"  # < 0.50 Objets distincts


@dataclass
class SimilarityResult:
    """Result of a geometric similarity comparison.

    Attributes:
        level: Similarity level according to the decision matrix.
        iou_score: IoU/Jaccard score (0.0 to 1.0).
        hausdorff_distance: Hausdorff distance (in CRS units).
        combined_score: Normalized combined score (0.0 to 1.0).
        needs_validation: Indicates if manual validation is recommended.
        reason: Explanation of the result.
    """

    level: SimilarityLevel
    iou_score: float
    hausdorff_distance: float | None = None
    combined_score: float = 0.0
    needs_validation: bool = False
    reason: str = ""

    def is_match(self) -> bool:
        """Determine if the geometries match.

        Returns:
            True if IDENTICAL or LIKELY_MATCH.
        """
        return self.level in (SimilarityLevel.IDENTICAL, SimilarityLevel.LIKELY_MATCH)

    def is_auto_merge(self) -> bool:
        """Determine if automatic merge is possible.

        Returns:
            True if IDENTICAL (no validation needed).
        """
        return self.level == SimilarityLevel.IDENTICAL


class SimilarityThresholds(BaseModel):
    """Decision matrix thresholds for similarity.

    The thresholds define the boundaries between similarity levels.
    """

    identical_min: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Seuil minimum pour IDENTICAL (IoU >= ce seuil)",
    )
    likely_match_min: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Seuil minimum pour LIKELY_MATCH (IoU >= ce seuil)",
    )
    suspect_min: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Seuil minimum pour SUSPECT (IoU >= ce seuil)",
    )
    hausdorff_max: float = Field(
        default=10.0,
        ge=0.0,
        description="Distance Hausdorff max (mètres) pour confirmer LIKELY_MATCH",
    )


class HistorizationConfig(BaseModel):
    """Historization configuration for a product.

    Historization allows preserving the modification history of geographic
    entities across vintages.

    The recommended method is COMBINED which uses:
    1. IoU calculation first - if very high (>= 0.95), it is identical
    2. If IoU is moderate, Hausdorff verification to confirm contour proximity

    Attributes:
        enabled: Enable historization for this product.
        method: Geometric comparison method (COMBINED recommended).
        thresholds: Decision matrix thresholds.
        key_field: Field used as identification key (e.g., cd_insee).
    """

    enabled: bool = Field(default=False, description="Active l'historisation")
    method: SimilarityMethod = Field(
        default=SimilarityMethod.COMBINED,
        description="Méthode de comparaison (combined recommandé)",
    )
    thresholds: SimilarityThresholds = Field(
        default_factory=SimilarityThresholds,
        description="Seuils de la matrice de décision",
    )
    key_field: str = Field(
        default="cd_insee",
        description="Champ clé pour l'identification des entités",
    )
    # Rétrocompatibilité avec l'ancien champ threshold
    threshold: float | None = Field(
        default=None,
        description="[DEPRECATED] Utilisez thresholds à la place",
    )

    def get_effective_thresholds(self) -> SimilarityThresholds:
        """Return the effective thresholds (with backward compatibility).

        Returns:
            Thresholds to use.
        """
        if self.threshold is not None:
            # Rétrocompatibilité: utiliser l'ancien threshold comme identical_min
            return SimilarityThresholds(identical_min=self.threshold)
        return self.thresholds

    def get_threshold_description(self) -> str:
        """Return a description of thresholds by method.

        Returns:
            Human-readable description.
        """
        if self.method == SimilarityMethod.MD5:
            return "Comparaison exacte (hash MD5)"
        elif self.method == SimilarityMethod.COMBINED:
            t = self.get_effective_thresholds()
            return (
                f"IoU >= {t.identical_min:.0%} (identique), "
                f">= {t.likely_match_min:.0%} + Hausdorff <= {t.hausdorff_max:.0f}m (probable)"
            )
        elif self.method == SimilarityMethod.JACCARD:
            t = self.get_effective_thresholds()
            return f"IoU >= {t.identical_min:.0%}"
        else:  # HAUSDORFF
            t = self.get_effective_thresholds()
            return f"Distance <= {t.hausdorff_max:.0f}m"


class LayerImportConfig(BaseModel):
    """Import configuration for a specific layer.

    Each layer can override the product's default values.
    None fields inherit from the parent product configuration.

    Attributes:
        enabled: If True, the layer will be imported.
        table_name: Target table name (optional, uses default if None).
        territory: Territory code (inherits from product if None).
        format: File format (inherits from product if None).
        editions: Editions to import (inherits from product if None).
        historization: Historization configuration (inherits from product if None).
    """

    enabled: bool = Field(default=True, description="Active l'import de cette couche")
    table_name: str | None = Field(
        default=None,
        description="Nom de la table cible (optionnel)",
    )
    territory: str | None = Field(
        default=None,
        description="Code territoire (hérite du produit si None)",
    )
    format: str | None = Field(
        default=None,
        description="Format de fichier (hérite du produit si None)",
    )
    editions: list[str] | None = Field(
        default=None,
        description="Millésimes à importer (hérite du produit si None)",
    )
    historization: HistorizationConfig | None = Field(
        default=None,
        description="Configuration de l'historisation (hérite du produit si None)",
    )


@dataclass
class EffectiveLayerConfig:
    """Effective layer configuration after inheritance resolution.

    This class represents the final configuration of a layer with all
    values resolved (no None).

    Attributes:
        layer_name: Layer name.
        enabled: If True, the layer will be imported.
        table_name: Target table name.
        territory: Territory code.
        format: File format.
        editions: Editions to import.
        historization: Historization configuration.
    """

    layer_name: str
    enabled: bool
    table_name: str | None
    territory: str
    format: str
    editions: list[str]
    historization: HistorizationConfig


class ProductImportConfig(BaseModel):
    """Import configuration for a specific product.

    Product-level parameters serve as default values for all layers.
    Each layer can override these values.

    Attributes:
        territory: Default territory code (FRA, FXX, GLP, etc.).
        format: Default file format (shp, gpkg).
        editions: Default editions/vintages to import.
        historization: Default historization configuration.
        layers: Per-layer configuration.
    """

    territory: str = Field(default="FRA", description="Code territoire par défaut")
    format: str = Field(default="shp", description="Format de fichier par défaut")
    editions: list[str] = Field(
        default_factory=lambda: ["2024"],
        description="Millésimes par défaut",
    )
    historization: HistorizationConfig = Field(
        default_factory=HistorizationConfig,
        description="Configuration de l'historisation par défaut",
    )
    layers: dict[str, LayerImportConfig] = Field(
        default_factory=dict,
        description="Configuration par couche",
    )

    def get_effective_layer_config(self, layer_name: str) -> EffectiveLayerConfig:
        """Return the effective configuration of a layer.

        Resolve inheritance by combining the layer configuration
        with the product's default values.

        Args:
            layer_name: Layer name.

        Returns:
            Effective configuration with all values resolved.
        """
        layer_config = self.layers.get(layer_name, LayerImportConfig())

        return EffectiveLayerConfig(
            layer_name=layer_name,
            enabled=layer_config.enabled,
            table_name=layer_config.table_name,
            territory=layer_config.territory if layer_config.territory else self.territory,
            format=layer_config.format if layer_config.format else self.format,
            editions=layer_config.editions if layer_config.editions else self.editions,
            historization=(
                layer_config.historization if layer_config.historization else self.historization
            ),
        )

    def get_enabled_layers(self) -> list[str]:
        """Return the list of enabled layers.

        Returns:
            List of layer names with enabled=True.
        """
        return [name for name, cfg in self.layers.items() if cfg.enabled]

    def get_latest_edition(self) -> str | None:
        """Return the latest configured edition (at product level).

        Returns:
            Latest edition or None if none.
        """
        if not self.editions:
            return None
        return sorted(self.editions)[-1]

    def get_layers_display(self) -> str:
        """Return a display of enabled layers.

        Returns:
            List of layers or "aucune".
        """
        enabled = self.get_enabled_layers()
        if not enabled:
            return "aucune"
        return ", ".join(enabled)

    def count_enabled_layers(self) -> int:
        """Count the number of enabled layers.

        Returns:
            Number of layers with enabled=True.
        """
        return sum(1 for cfg in self.layers.values() if cfg.enabled)

    def has_enabled_layers(self) -> bool:
        """Check if at least one layer is enabled.

        Returns:
            True if at least one layer is enabled.
        """
        return any(cfg.enabled for cfg in self.layers.values())


class ImportsConfig(BaseModel):
    """Configuration for all imports.

    Attributes:
        products: Dictionary of configurations per product.
    """

    products: dict[str, ProductImportConfig] = Field(
        default_factory=dict,
        description="Configuration par produit",
    )

    def get_enabled_products(self) -> dict[str, ProductImportConfig]:
        """Return the products that have at least one enabled layer.

        Returns:
            Dictionary of products with at least one layer with enabled=True.
        """
        return {k: v for k, v in self.products.items() if v.has_enabled_layers()}

    def get_product(self, product_id: str) -> ProductImportConfig | None:
        """Return the configuration of a product.

        Args:
            product_id: Product identifier.

        Returns:
            Configuration or None if not found.
        """
        return self.products.get(product_id)

    def add_product(
        self,
        product_id: str,
        config: ProductImportConfig | None = None,
    ) -> None:
        """Add a product to the configuration.

        Args:
            product_id: Product identifier.
            config: Configuration (default if None).
        """
        if config is None:
            config = ProductImportConfig()
        self.products[product_id] = config

    def remove_product(self, product_id: str) -> bool:
        """Remove a product from the configuration.

        Args:
            product_id: Product identifier.

        Returns:
            True if removed, False if not found.
        """
        if product_id in self.products:
            del self.products[product_id]
            return True
        return False

    def count_enabled(self) -> int:
        """Count the products with at least one enabled layer.

        Returns:
            Number of products with at least one enabled layer.
        """
        return sum(1 for p in self.products.values() if p.has_enabled_layers())

    def count_total(self) -> int:
        """Count the total number of products.

        Returns:
            Total number of products.
        """
        return len(self.products)


# Configurations par défaut pour les produits courants
DEFAULT_PRODUCT_CONFIGS: dict[str, ProductImportConfig] = {
    "admin-express-cog": ProductImportConfig(
        territory="FRA",
        format="shp",
        editions=["2024"],
        historization=HistorizationConfig(
            enabled=True,
            method=SimilarityMethod.COMBINED,
            thresholds=SimilarityThresholds(
                identical_min=0.95,
                likely_match_min=0.80,
                suspect_min=0.50,
                hausdorff_max=10.0,
            ),
            key_field="cd_insee",
        ),
        layers={
            "REGION": LayerImportConfig(enabled=True, table_name="region"),
            "DEPARTEMENT": LayerImportConfig(enabled=True, table_name="departement"),
            "EPCI": LayerImportConfig(enabled=True, table_name="epci"),
            "COMMUNE": LayerImportConfig(enabled=True, table_name="commune"),
        },
    ),
    "contours-iris": ProductImportConfig(
        territory="FRA",
        format="shp",
        editions=["2024"],
        historization=HistorizationConfig(
            enabled=True,
            method=SimilarityMethod.COMBINED,
            thresholds=SimilarityThresholds(
                identical_min=0.90,
                likely_match_min=0.75,
                suspect_min=0.50,
                hausdorff_max=15.0,
            ),
            key_field="code_iris",
        ),
        layers={
            "IRIS_GE": LayerImportConfig(enabled=False, table_name="iris"),
        },
    ),
    "codes-postaux-ban": ProductImportConfig(
        territory="FRA",
        format="geojson",
        editions=["2021"],
        historization=HistorizationConfig(enabled=False),
        layers={},
    ),
}


def get_default_key_field(product_id: str, layer_name: str) -> str:  # noqa: ARG001
    """Return the default key field for a product/layer.

    Args:
        product_id: Product identifier.
        layer_name: Layer name.

    Returns:
        Key field name.
    """
    # Mapping des champs clés par couche
    key_fields = {
        "REGION": "cd_insee",
        "DEPARTEMENT": "cd_insee",
        "ARRONDISSEMENT": "cd_insee",
        "EPCI": "cd_siren",
        "COMMUNE": "cd_insee",
        "COMMUNE_ASSOCIEE_OU_DELEGUEE": "cd_insee",
        "IRIS_GE": "code_iris",
    }
    return key_fields.get(layer_name, "cd_insee")
