"""Configuration des imports de données géographiques.

Ce module définit les structures de configuration pour les imports
de produits IGN avec support de l'historisation.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SimilarityMethod(StrEnum):
    """Méthodes de comparaison géométrique pour l'historisation."""

    MD5 = "md5"  # Hash MD5 des coordonnées (identité stricte)
    JACCARD = "jaccard"  # Indice de Jaccard / IoU (superposition spatiale)
    HAUSDORFF = "hausdorff"  # Distance de Hausdorff (ressemblance des formes)


class HistorizationConfig(BaseModel):
    """Configuration de l'historisation pour un produit.

    L'historisation permet de conserver l'historique des modifications
    des entités géographiques au fil des millésimes.

    Attributes:
        enabled: Active l'historisation pour ce produit.
        method: Méthode de comparaison géométrique.
        threshold: Seuil de similarité (interprétation selon la méthode).
        key_field: Champ utilisé comme clé d'identification (ex: cd_insee).
    """

    enabled: bool = Field(default=False, description="Active l'historisation")
    method: SimilarityMethod = Field(
        default=SimilarityMethod.JACCARD,
        description="Méthode de comparaison géométrique",
    )
    threshold: float = Field(
        default=0.95,
        description="Seuil de similarité (ratio pour Jaccard, mètres pour Hausdorff)",
    )
    key_field: str = Field(
        default="cd_insee",
        description="Champ clé pour l'identification des entités",
    )

    def get_threshold_description(self) -> str:
        """Retourne une description du seuil selon la méthode.

        Returns:
            Description lisible du seuil.
        """
        if self.method == SimilarityMethod.MD5:
            return "N/A (comparaison exacte)"
        elif self.method == SimilarityMethod.JACCARD:
            return f"{self.threshold:.0%} de superposition minimum"
        else:  # HAUSDORFF
            return f"{self.threshold:.0f}m de distance maximum"


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
            method=SimilarityMethod.JACCARD,
            threshold=0.95,
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
            method=SimilarityMethod.JACCARD,
            threshold=0.90,
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
