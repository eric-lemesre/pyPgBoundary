"""Module de comparaison géométrique pour l'historisation.

Ce module fournit des fonctions pour comparer des géométries
et déterminer si elles représentent la même entité géographique.

Méthodes supportées:
- MD5: Hash des coordonnées (identité stricte)
- Jaccard: Indice de Jaccard / IoU (superposition spatiale)
- Hausdorff: Distance de Hausdorff (ressemblance des formes)
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from shapely.geometry import MultiPolygon, Polygon

from pgboundary.import_config import SimilarityMethod

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry


def compute_geometry_hash(geom: BaseGeometry) -> str:
    """Calcule le hash MD5 des coordonnées d'une géométrie.

    Args:
        geom: Géométrie à hasher.

    Returns:
        Hash MD5 hexadécimal des coordonnées.
    """
    if geom is None or geom.is_empty:
        return ""

    # Extraire les coordonnées sous forme de chaîne normalisée
    # Arrondir à 6 décimales pour éviter les problèmes de précision flottante
    coords_str = _normalize_coords(geom)
    return hashlib.md5(coords_str.encode()).hexdigest()


def _normalize_coords(geom: BaseGeometry, precision: int = 6) -> str:
    """Normalise les coordonnées d'une géométrie en chaîne.

    Args:
        geom: Géométrie à normaliser.
        precision: Nombre de décimales.

    Returns:
        Chaîne représentant les coordonnées normalisées.
    """
    if isinstance(geom, Polygon | MultiPolygon):
        # Pour les polygones, utiliser le WKT simplifié
        # Arrondir les coordonnées
        coords = []
        for coord in geom.exterior.coords if isinstance(geom, Polygon) else []:
            coords.append(f"{coord[0]:.{precision}f},{coord[1]:.{precision}f}")
        return ";".join(sorted(coords))
    else:
        # Fallback sur WKT
        return str(geom.wkt)


def compute_jaccard_index(geom1: BaseGeometry, geom2: BaseGeometry) -> float:
    """Calcule l'indice de Jaccard (IoU) entre deux géométries.

    L'indice de Jaccard = Intersection / Union
    - 1.0 = géométries identiques
    - 0.0 = aucune superposition

    Args:
        geom1: Première géométrie.
        geom2: Deuxième géométrie.

    Returns:
        Indice de Jaccard (0.0 à 1.0).
    """
    if geom1 is None or geom2 is None:
        return 0.0
    if geom1.is_empty or geom2.is_empty:
        return 0.0

    try:
        intersection = geom1.intersection(geom2)
        union = geom1.union(geom2)

        if union.is_empty or union.area == 0:
            return 0.0

        return float(intersection.area / union.area)
    except Exception:
        return 0.0


def compute_hausdorff_distance(geom1: BaseGeometry, geom2: BaseGeometry) -> float:
    """Calcule la distance de Hausdorff entre deux géométries.

    La distance de Hausdorff mesure la distance maximale entre
    les points les plus proches de deux ensembles.

    Plus la distance est petite, plus les formes sont similaires.

    Args:
        geom1: Première géométrie.
        geom2: Deuxième géométrie.

    Returns:
        Distance de Hausdorff dans l'unité du système de coordonnées.
    """
    if geom1 is None or geom2 is None:
        return float("inf")
    if geom1.is_empty or geom2.is_empty:
        return float("inf")

    try:
        return float(geom1.hausdorff_distance(geom2))
    except Exception:
        return float("inf")


def are_geometries_similar(
    geom1: BaseGeometry,
    geom2: BaseGeometry,
    method: SimilarityMethod,
    threshold: float,
) -> bool:
    """Détermine si deux géométries sont similaires selon la méthode choisie.

    Args:
        geom1: Première géométrie.
        geom2: Deuxième géométrie.
        method: Méthode de comparaison.
        threshold: Seuil de similarité.

    Returns:
        True si les géométries sont considérées similaires.
    """
    if method == SimilarityMethod.MD5:
        hash1 = compute_geometry_hash(geom1)
        hash2 = compute_geometry_hash(geom2)
        return hash1 == hash2 and hash1 != ""

    elif method == SimilarityMethod.JACCARD:
        jaccard = compute_jaccard_index(geom1, geom2)
        return jaccard >= threshold

    elif method == SimilarityMethod.HAUSDORFF:
        distance = compute_hausdorff_distance(geom1, geom2)
        return distance <= threshold

    return False


def compute_similarity_score(
    geom1: BaseGeometry,
    geom2: BaseGeometry,
    method: SimilarityMethod,
) -> float:
    """Calcule un score de similarité entre deux géométries.

    Args:
        geom1: Première géométrie.
        geom2: Deuxième géométrie.
        method: Méthode de comparaison.

    Returns:
        Score de similarité (interprétation selon la méthode).
    """
    if method == SimilarityMethod.MD5:
        hash1 = compute_geometry_hash(geom1)
        hash2 = compute_geometry_hash(geom2)
        return 1.0 if hash1 == hash2 and hash1 != "" else 0.0

    elif method == SimilarityMethod.JACCARD:
        return compute_jaccard_index(geom1, geom2)

    elif method == SimilarityMethod.HAUSDORFF:
        return compute_hausdorff_distance(geom1, geom2)

    return 0.0


class GeometryMatcher:
    """Classe pour la correspondance de géométries entre millésimes.

    Cette classe permet de trouver les correspondances entre les entités
    de deux millésimes différents en utilisant une clé d'identification
    et une méthode de comparaison géométrique.
    """

    def __init__(
        self,
        method: SimilarityMethod = SimilarityMethod.JACCARD,
        threshold: float = 0.95,
        key_field: str = "cd_insee",
    ) -> None:
        """Initialise le matcher.

        Args:
            method: Méthode de comparaison géométrique.
            threshold: Seuil de similarité.
            key_field: Champ utilisé comme clé d'identification.
        """
        self.method = method
        self.threshold = threshold
        self.key_field = key_field

    def find_matches(
        self,
        old_features: list[dict[str, Any]],
        new_features: list[dict[str, Any]],
    ) -> tuple[
        list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]
    ]:
        """Trouve les correspondances entre deux ensembles de features.

        Args:
            old_features: Features de l'ancien millésime.
            new_features: Features du nouveau millésime.

        Returns:
            Tuple contenant:
            - Liste des correspondances (old, new)
            - Liste des features supprimées (présentes dans old, absentes dans new)
            - Liste des features ajoutées (absentes dans old, présentes dans new)
        """
        # Indexer par clé
        old_by_key = {f.get(self.key_field): f for f in old_features}
        new_by_key = {f.get(self.key_field): f for f in new_features}

        old_keys = set(old_by_key.keys())
        new_keys = set(new_by_key.keys())

        # Clés communes, supprimées, ajoutées
        common_keys = old_keys & new_keys
        removed_keys = old_keys - new_keys
        added_keys = new_keys - old_keys

        # Correspondances avec vérification géométrique
        matches = []
        for key in common_keys:
            old_f = old_by_key[key]
            new_f = new_by_key[key]

            old_geom = old_f.get("geometry")
            new_geom = new_f.get("geometry")

            if old_geom is not None and new_geom is not None:
                if are_geometries_similar(old_geom, new_geom, self.method, self.threshold):
                    matches.append((old_f, new_f))
                else:
                    # Géométrie modifiée : considérer comme suppression + ajout
                    removed_keys.add(key)
                    added_keys.add(key)
            else:
                matches.append((old_f, new_f))

        removed = [old_by_key[k] for k in removed_keys if k in old_by_key]
        added = [new_by_key[k] for k in added_keys if k in new_by_key]

        return matches, removed, added

    def get_method_description(self) -> str:
        """Retourne une description de la méthode utilisée.

        Returns:
            Description lisible.
        """
        descriptions = {
            SimilarityMethod.MD5: "Hash MD5 des coordonnées (identité stricte)",
            SimilarityMethod.JACCARD: f"Indice de Jaccard >= {self.threshold:.0%}",
            SimilarityMethod.HAUSDORFF: f"Distance de Hausdorff <= {self.threshold:.0f}m",
        }
        return descriptions.get(self.method, str(self.method))
