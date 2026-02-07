"""Configuration des imports de données géographiques.

Ce module définit les structures de configuration pour les imports
de produits IGN avec support de l'historisation.

Matrice de décision pour la similarité géométrique:
- [0.95 - 1.00] : IDENTICAL - Fusion automatique sans vérification
- [0.80 - 0.95] : LIKELY_MATCH - Correspondance forte, validation si attributs diffèrent
- [0.50 - 0.80] : SUSPECT - Conflit potentiel ou changement temporel
- < 0.50 : DISTINCT - Objets distincts
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field


class SimilarityMethod(StrEnum):
    """Méthodes de comparaison géométrique pour l'historisation."""

    MD5 = "md5"  # Hash MD5 des coordonnées (identité stricte)
    JACCARD = "jaccard"  # Indice de Jaccard / IoU (superposition spatiale)
    HAUSDORFF = "hausdorff"  # Distance de Hausdorff (ressemblance des formes)
    COMBINED = "combined"  # Combinaison IoU + Hausdorff (recommandé)


class SimilarityLevel(StrEnum):
    """Niveaux de similarité selon la matrice de décision."""

    IDENTICAL = "identical"  # [0.95 - 1.00] Fusion automatique
    LIKELY_MATCH = "likely_match"  # [0.80 - 0.95] Correspondance forte
    SUSPECT = "suspect"  # [0.50 - 0.80] Conflit potentiel
    DISTINCT = "distinct"  # < 0.50 Objets distincts


@dataclass
class SimilarityResult:
    """Résultat d'une comparaison de similarité géométrique.

    Attributes:
        level: Niveau de similarité selon la matrice de décision.
        iou_score: Score IoU/Jaccard (0.0 à 1.0).
        hausdorff_distance: Distance de Hausdorff (en unités du CRS).
        combined_score: Score combiné normalisé (0.0 à 1.0).
        needs_validation: Indique si une validation manuelle est recommandée.
        reason: Explication du résultat.
    """

    level: SimilarityLevel
    iou_score: float
    hausdorff_distance: float | None = None
    combined_score: float = 0.0
    needs_validation: bool = False
    reason: str = ""

    def is_match(self) -> bool:
        """Détermine si les géométries correspondent.

        Returns:
            True si IDENTICAL ou LIKELY_MATCH.
        """
        return self.level in (SimilarityLevel.IDENTICAL, SimilarityLevel.LIKELY_MATCH)

    def is_auto_merge(self) -> bool:
        """Détermine si la fusion automatique est possible.

        Returns:
            True si IDENTICAL (pas de validation nécessaire).
        """
        return self.level == SimilarityLevel.IDENTICAL


class SimilarityThresholds(BaseModel):
    """Seuils de la matrice de décision pour la similarité.

    Les seuils définissent les limites entre les niveaux de similarité.
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
    """Configuration de l'historisation pour un produit.

    L'historisation permet de conserver l'historique des modifications
    des entités géographiques au fil des millésimes.

    La méthode recommandée est COMBINED qui utilise:
    1. Calcul IoU d'abord - si très élevé (>= 0.95), c'est identique
    2. Si IoU moyen, vérification Hausdorff pour confirmer la proximité des contours

    Attributes:
        enabled: Active l'historisation pour ce produit.
        method: Méthode de comparaison géométrique (COMBINED recommandé).
        thresholds: Seuils de la matrice de décision.
        key_field: Champ utilisé comme clé d'identification (ex: cd_insee).
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
        """Retourne les seuils effectifs (avec rétrocompatibilité).

        Returns:
            Seuils à utiliser.
        """
        if self.threshold is not None:
            # Rétrocompatibilité: utiliser l'ancien threshold comme identical_min
            return SimilarityThresholds(identical_min=self.threshold)
        return self.thresholds

    def get_threshold_description(self) -> str:
        """Retourne une description des seuils selon la méthode.

        Returns:
            Description lisible.
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


class ProductImportConfig(BaseModel):
    """Configuration d'import pour un produit spécifique.

    Attributes:
        enabled: Si True, le produit sera importé.
        layers: Liste des couches à importer (toutes si vide).
        territory: Code territoire (FRA, FXX, GLP, etc.).
        format: Format de fichier (shp, gpkg).
        years: Liste des années/millésimes à importer.
        historization: Configuration de l'historisation.
    """

    enabled: bool = Field(default=True, description="Active l'import de ce produit")
    layers: list[str] = Field(
        default_factory=list,
        description="Couches à importer (toutes si vide)",
    )
    territory: str = Field(default="FRA", description="Code territoire")
    format: str = Field(default="shp", description="Format de fichier")
    years: list[str] = Field(
        default_factory=lambda: ["2024"],
        description="Années/millésimes à importer",
    )
    historization: HistorizationConfig = Field(
        default_factory=HistorizationConfig,
        description="Configuration de l'historisation",
    )

    def get_latest_year(self) -> str | None:
        """Retourne la dernière année configurée.

        Returns:
            Dernière année ou None si aucune.
        """
        if not self.years:
            return None
        return sorted(self.years)[-1]

    def get_layers_display(self) -> str:
        """Retourne un affichage des couches.

        Returns:
            Liste des couches ou "toutes".
        """
        if not self.layers:
            return "toutes"
        return ", ".join(self.layers)


class ImportsConfig(BaseModel):
    """Configuration de tous les imports.

    Attributes:
        products: Dictionnaire des configurations par produit.
    """

    products: dict[str, ProductImportConfig] = Field(
        default_factory=dict,
        description="Configuration par produit",
    )

    def get_enabled_products(self) -> dict[str, ProductImportConfig]:
        """Retourne les produits activés.

        Returns:
            Dictionnaire des produits avec enabled=True.
        """
        return {k: v for k, v in self.products.items() if v.enabled}

    def get_product(self, product_id: str) -> ProductImportConfig | None:
        """Retourne la configuration d'un produit.

        Args:
            product_id: Identifiant du produit.

        Returns:
            Configuration ou None si non trouvé.
        """
        return self.products.get(product_id)

    def add_product(
        self,
        product_id: str,
        config: ProductImportConfig | None = None,
    ) -> None:
        """Ajoute un produit à la configuration.

        Args:
            product_id: Identifiant du produit.
            config: Configuration (défaut si None).
        """
        if config is None:
            config = ProductImportConfig()
        self.products[product_id] = config

    def remove_product(self, product_id: str) -> bool:
        """Supprime un produit de la configuration.

        Args:
            product_id: Identifiant du produit.

        Returns:
            True si supprimé, False si non trouvé.
        """
        if product_id in self.products:
            del self.products[product_id]
            return True
        return False

    def count_enabled(self) -> int:
        """Compte les produits activés.

        Returns:
            Nombre de produits activés.
        """
        return sum(1 for p in self.products.values() if p.enabled)

    def count_total(self) -> int:
        """Compte le total de produits.

        Returns:
            Nombre total de produits.
        """
        return len(self.products)


# Configurations par défaut pour les produits courants
DEFAULT_PRODUCT_CONFIGS: dict[str, ProductImportConfig] = {
    "admin-express-cog": ProductImportConfig(
        enabled=True,
        layers=["REGION", "DEPARTEMENT", "EPCI", "COMMUNE"],
        territory="FRA",
        format="shp",
        years=["2024"],
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
    ),
    "contours-iris": ProductImportConfig(
        enabled=False,
        layers=["IRIS_GE"],
        territory="FRA",
        format="shp",
        years=["2024"],
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
    ),
    "codes-postaux-ban": ProductImportConfig(
        enabled=False,
        layers=[],
        territory="FRA",
        format="geojson",
        years=["2021"],
        historization=HistorizationConfig(enabled=False),
    ),
}


def get_default_key_field(product_id: str, layer_name: str) -> str:  # noqa: ARG001
    """Retourne le champ clé par défaut pour un produit/couche.

    Args:
        product_id: Identifiant du produit.
        layer_name: Nom de la couche.

    Returns:
        Nom du champ clé.
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
