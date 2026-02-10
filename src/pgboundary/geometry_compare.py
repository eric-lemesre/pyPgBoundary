"""Geometry comparison module for historization.

This module provides functions for comparing geometries
and determining if they represent the same geographic entity.

Combined computation logic (recommended):
1. Compute IoU (Jaccard) first
   - If IoU >= 0.95: IDENTICAL, automatic merge
2. If medium IoU [0.80 - 0.95]: Hausdorff verification
   - If Hausdorff <= threshold: LIKELY_MATCH, strong match
3. If IoU [0.50 - 0.80]: SUSPECT, potential conflict
4. If IoU < 0.50: DISTINCT, different objects

Uses Shapely for geometric operations.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from shapely.geometry import MultiPolygon, Polygon

from pgboundary.import_config import (
    SimilarityLevel,
    SimilarityMethod,
    SimilarityResult,
    SimilarityThresholds,
)

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry


def compute_geometry_hash(geom: BaseGeometry) -> str:
    """Compute the MD5 hash of a geometry's coordinates.

    Args:
        geom: Geometry to hash.

    Returns:
        Hexadecimal MD5 hash of the coordinates.
    """
    if geom is None or geom.is_empty:
        return ""

    coords_str = _normalize_coords(geom)
    return hashlib.md5(coords_str.encode()).hexdigest()


def _normalize_coords(geom: BaseGeometry, precision: int = 6) -> str:
    """Normalize a geometry's coordinates to a string.

    Args:
        geom: Geometry to normalize.
        precision: Number of decimal places.

    Returns:
        String representing the normalized coordinates.
    """
    if isinstance(geom, Polygon | MultiPolygon):
        coords = []
        for coord in geom.exterior.coords if isinstance(geom, Polygon) else []:
            coords.append(f"{coord[0]:.{precision}f},{coord[1]:.{precision}f}")
        return ";".join(sorted(coords))
    else:
        return str(geom.wkt)


def compute_jaccard_index(geom1: BaseGeometry, geom2: BaseGeometry) -> float:
    """Compute the Jaccard index (IoU) between two geometries.

    Jaccard index = Intersection / Union
    - 1.0 = identical geometries
    - 0.0 = no overlap

    Args:
        geom1: First geometry.
        geom2: Second geometry.

    Returns:
        Jaccard index (0.0 to 1.0).
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
    """Compute the Hausdorff distance between two geometries.

    The Hausdorff distance measures the maximum distance between
    the nearest points of two sets.

    The smaller the distance, the more similar the shapes are.

    Args:
        geom1: First geometry.
        geom2: Second geometry.

    Returns:
        Hausdorff distance in the coordinate system's unit.
    """
    if geom1 is None or geom2 is None:
        return float("inf")
    if geom1.is_empty or geom2.is_empty:
        return float("inf")

    try:
        return float(geom1.hausdorff_distance(geom2))
    except Exception:
        return float("inf")


def compute_combined_similarity(
    geom1: BaseGeometry,
    geom2: BaseGeometry,
    thresholds: SimilarityThresholds | None = None,
) -> SimilarityResult:
    """Compute the combined IoU + Hausdorff similarity.

    Sequential logic:
    1. Compute IoU - if very high (>= identical_min), stop: IDENTICAL
    2. If medium IoU (>= likely_match_min), verify Hausdorff:
       - If Hausdorff <= hausdorff_max: LIKELY_MATCH
       - Otherwise: SUSPECT (IoU ok but different contours)
    3. If low IoU (>= suspect_min): SUSPECT
    4. If very low IoU (< suspect_min): DISTINCT

    Args:
        geom1: First geometry.
        geom2: Second geometry.
        thresholds: Decision matrix thresholds.

    Returns:
        Detailed comparison result.
    """
    if thresholds is None:
        thresholds = SimilarityThresholds()

    # Cas spéciaux
    if geom1 is None or geom2 is None:
        return SimilarityResult(
            level=SimilarityLevel.DISTINCT,
            iou_score=0.0,
            reason="Géométrie manquante",
        )

    if geom1.is_empty or geom2.is_empty:
        return SimilarityResult(
            level=SimilarityLevel.DISTINCT,
            iou_score=0.0,
            reason="Géométrie vide",
        )

    # Étape 1: Calcul IoU
    iou = compute_jaccard_index(geom1, geom2)

    # IoU très élevé => IDENTICAL
    if iou >= thresholds.identical_min:
        return SimilarityResult(
            level=SimilarityLevel.IDENTICAL,
            iou_score=iou,
            combined_score=iou,
            reason=f"IoU élevé ({iou:.1%}), fusion automatique",
        )

    # IoU moyen => vérification Hausdorff
    if iou >= thresholds.likely_match_min:
        # Étape 2: Calcul Hausdorff pour confirmation
        hausdorff = compute_hausdorff_distance(geom1, geom2)

        if hausdorff <= thresholds.hausdorff_max:
            # Contours proches malgré différence d'aire
            combined = _compute_combined_score(iou, hausdorff, thresholds)
            return SimilarityResult(
                level=SimilarityLevel.LIKELY_MATCH,
                iou_score=iou,
                hausdorff_distance=hausdorff,
                combined_score=combined,
                needs_validation=True,
                reason=(
                    f"IoU moyen ({iou:.1%}) mais contours proches (Hausdorff: {hausdorff:.2f}m)"
                ),
            )
        else:
            # IoU ok mais contours différents => SUSPECT
            combined = _compute_combined_score(iou, hausdorff, thresholds)
            return SimilarityResult(
                level=SimilarityLevel.SUSPECT,
                iou_score=iou,
                hausdorff_distance=hausdorff,
                combined_score=combined,
                needs_validation=True,
                reason=(
                    f"IoU moyen ({iou:.1%}) mais contours distants "
                    f"(Hausdorff: {hausdorff:.2f}m > {thresholds.hausdorff_max}m)"
                ),
            )

    # IoU faible => SUSPECT
    if iou >= thresholds.suspect_min:
        hausdorff = compute_hausdorff_distance(geom1, geom2)
        combined = _compute_combined_score(iou, hausdorff, thresholds)
        return SimilarityResult(
            level=SimilarityLevel.SUSPECT,
            iou_score=iou,
            hausdorff_distance=hausdorff,
            combined_score=combined,
            needs_validation=True,
            reason=f"IoU faible ({iou:.1%}), changement temporel possible",
        )

    # IoU très faible => DISTINCT
    return SimilarityResult(
        level=SimilarityLevel.DISTINCT,
        iou_score=iou,
        combined_score=iou,
        reason=f"IoU très faible ({iou:.1%}), objets distincts",
    )


def _compute_combined_score(
    iou: float,
    hausdorff: float,
    thresholds: SimilarityThresholds,
) -> float:
    """Compute a normalized combined score.

    Combines IoU and Hausdorff into a single score [0, 1].

    Args:
        iou: IoU score (0 to 1).
        hausdorff: Hausdorff distance.
        thresholds: Configuration thresholds.

    Returns:
        Combined score (0 to 1).
    """
    # Normaliser Hausdorff inversé (plus petit = meilleur)
    # On utilise une fonction exponentielle décroissante
    hausdorff_normalized = max(0.0, 1.0 - (hausdorff / (thresholds.hausdorff_max * 2)))

    # Pondération: 70% IoU, 30% Hausdorff
    return 0.7 * iou + 0.3 * hausdorff_normalized


def are_geometries_similar(
    geom1: BaseGeometry,
    geom2: BaseGeometry,
    method: SimilarityMethod,
    threshold: float | None = None,
    thresholds: SimilarityThresholds | None = None,
) -> bool:
    """Determine if two geometries are similar according to the chosen method.

    Args:
        geom1: First geometry.
        geom2: Second geometry.
        method: Comparison method.
        threshold: Simple threshold (backward compatibility).
        thresholds: Decision matrix thresholds.

    Returns:
        True if the geometries are considered similar.
    """
    if method == SimilarityMethod.MD5:
        hash1 = compute_geometry_hash(geom1)
        hash2 = compute_geometry_hash(geom2)
        return hash1 == hash2 and hash1 != ""

    elif method == SimilarityMethod.COMBINED:
        result = compute_combined_similarity(geom1, geom2, thresholds)
        return result.is_match()

    elif method == SimilarityMethod.JACCARD:
        jaccard = compute_jaccard_index(geom1, geom2)
        effective_threshold = threshold if threshold is not None else 0.95
        return jaccard >= effective_threshold

    elif method == SimilarityMethod.HAUSDORFF:
        distance = compute_hausdorff_distance(geom1, geom2)
        effective_threshold = threshold if threshold is not None else 10.0
        return distance <= effective_threshold

    return False


def compute_similarity(
    geom1: BaseGeometry,
    geom2: BaseGeometry,
    method: SimilarityMethod = SimilarityMethod.COMBINED,
    thresholds: SimilarityThresholds | None = None,
) -> SimilarityResult:
    """Compute the similarity between two geometries with detailed result.

    This is the main function to use for comparison.

    Args:
        geom1: First geometry.
        geom2: Second geometry.
        method: Comparison method (COMBINED recommended).
        thresholds: Decision matrix thresholds.

    Returns:
        Detailed result with level, scores, and explanation.
    """
    if thresholds is None:
        thresholds = SimilarityThresholds()

    if method == SimilarityMethod.MD5:
        hash1 = compute_geometry_hash(geom1)
        hash2 = compute_geometry_hash(geom2)
        is_identical = hash1 == hash2 and hash1 != ""
        return SimilarityResult(
            level=SimilarityLevel.IDENTICAL if is_identical else SimilarityLevel.DISTINCT,
            iou_score=1.0 if is_identical else 0.0,
            combined_score=1.0 if is_identical else 0.0,
            reason="Hash MD5 identique" if is_identical else "Hash MD5 différent",
        )

    elif method == SimilarityMethod.COMBINED:
        return compute_combined_similarity(geom1, geom2, thresholds)

    elif method == SimilarityMethod.JACCARD:
        iou = compute_jaccard_index(geom1, geom2)
        level = _classify_iou_only(iou, thresholds)
        return SimilarityResult(
            level=level,
            iou_score=iou,
            combined_score=iou,
            reason=f"IoU: {iou:.1%}",
        )

    else:  # HAUSDORFF
        hausdorff = compute_hausdorff_distance(geom1, geom2)
        level = _classify_hausdorff_only(hausdorff, thresholds)
        return SimilarityResult(
            level=level,
            iou_score=0.0,
            hausdorff_distance=hausdorff,
            combined_score=max(0.0, 1.0 - hausdorff / (thresholds.hausdorff_max * 2)),
            reason=f"Hausdorff: {hausdorff:.2f}m",
        )


def _classify_iou_only(iou: float, thresholds: SimilarityThresholds) -> SimilarityLevel:
    """Classify by IoU only."""
    if iou >= thresholds.identical_min:
        return SimilarityLevel.IDENTICAL
    elif iou >= thresholds.likely_match_min:
        return SimilarityLevel.LIKELY_MATCH
    elif iou >= thresholds.suspect_min:
        return SimilarityLevel.SUSPECT
    return SimilarityLevel.DISTINCT


def _classify_hausdorff_only(hausdorff: float, thresholds: SimilarityThresholds) -> SimilarityLevel:
    """Classify by Hausdorff only."""
    if hausdorff <= thresholds.hausdorff_max * 0.5:
        return SimilarityLevel.IDENTICAL
    elif hausdorff <= thresholds.hausdorff_max:
        return SimilarityLevel.LIKELY_MATCH
    elif hausdorff <= thresholds.hausdorff_max * 2:
        return SimilarityLevel.SUSPECT
    return SimilarityLevel.DISTINCT


# Rétrocompatibilité
def compute_similarity_score(
    geom1: BaseGeometry,
    geom2: BaseGeometry,
    method: SimilarityMethod,
) -> float:
    """Compute a similarity score between two geometries.

    DEPRECATED: Use compute_similarity() for a detailed result.

    Args:
        geom1: First geometry.
        geom2: Second geometry.
        method: Comparison method.

    Returns:
        Similarity score (interpretation depends on the method).
    """
    if method == SimilarityMethod.MD5:
        hash1 = compute_geometry_hash(geom1)
        hash2 = compute_geometry_hash(geom2)
        return 1.0 if hash1 == hash2 and hash1 != "" else 0.0

    elif method == SimilarityMethod.COMBINED:
        result = compute_combined_similarity(geom1, geom2)
        return result.combined_score

    elif method == SimilarityMethod.JACCARD:
        return compute_jaccard_index(geom1, geom2)

    elif method == SimilarityMethod.HAUSDORFF:
        return compute_hausdorff_distance(geom1, geom2)

    return 0.0


class GeometryMatcher:
    """Class for geometry matching between vintages.

    This class finds matches between entities from two different vintages
    using an identification key and the similarity decision matrix.
    """

    def __init__(
        self,
        method: SimilarityMethod = SimilarityMethod.COMBINED,
        thresholds: SimilarityThresholds | None = None,
        key_field: str = "cd_insee",
        # Rétrocompatibilité
        threshold: float | None = None,
    ) -> None:
        """Initialize the matcher.

        Args:
            method: Geometric comparison method (COMBINED recommended).
            thresholds: Decision matrix thresholds.
            key_field: Field used as the identification key.
            threshold: [DEPRECATED] Use thresholds instead.
        """
        self.method = method
        self.key_field = key_field

        # Gestion de la rétrocompatibilité
        if thresholds is not None:
            self.thresholds = thresholds
        elif threshold is not None:
            self.thresholds = SimilarityThresholds(identical_min=threshold)
        else:
            self.thresholds = SimilarityThresholds()

    def compare(self, geom1: BaseGeometry, geom2: BaseGeometry) -> SimilarityResult:
        """Compare two geometries and return the detailed result.

        Args:
            geom1: First geometry.
            geom2: Second geometry.

        Returns:
            Comparison result with level and scores.
        """
        return compute_similarity(geom1, geom2, self.method, self.thresholds)

    def find_matches(
        self,
        old_features: list[dict[str, Any]],
        new_features: list[dict[str, Any]],
    ) -> tuple[
        list[tuple[dict[str, Any], dict[str, Any], SimilarityResult]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[tuple[dict[str, Any], dict[str, Any], SimilarityResult]],
    ]:
        """Find matches between two sets of features.

        Args:
            old_features: Features from the old vintage.
            new_features: Features from the new vintage.

        Returns:
            Tuple containing:
            - List of automatic matches (old, new, result)
            - List of deleted features
            - List of added features
            - List of matches requiring validation (old, new, result)
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

        # Correspondances avec classification
        auto_matches: list[tuple[dict[str, Any], dict[str, Any], SimilarityResult]] = []
        needs_validation: list[tuple[dict[str, Any], dict[str, Any], SimilarityResult]] = []

        for key in common_keys:
            old_f = old_by_key[key]
            new_f = new_by_key[key]

            old_geom = old_f.get("geometry")
            new_geom = new_f.get("geometry")

            if old_geom is not None and new_geom is not None:
                result = self.compare(old_geom, new_geom)

                if result.level == SimilarityLevel.IDENTICAL:
                    # Fusion automatique
                    auto_matches.append((old_f, new_f, result))
                elif result.level == SimilarityLevel.LIKELY_MATCH:
                    # Correspondance probable, à valider
                    needs_validation.append((old_f, new_f, result))
                elif result.level == SimilarityLevel.SUSPECT:
                    # Conflit potentiel, à valider
                    needs_validation.append((old_f, new_f, result))
                else:  # DISTINCT
                    # Objets distincts malgré même clé => suppression + ajout
                    removed_keys.add(key)
                    added_keys.add(key)
            else:
                # Pas de géométrie, correspondance par clé
                result = SimilarityResult(
                    level=SimilarityLevel.LIKELY_MATCH,
                    iou_score=0.0,
                    reason="Correspondance par clé (pas de géométrie)",
                )
                auto_matches.append((old_f, new_f, result))

        removed = [old_by_key[k] for k in removed_keys if k in old_by_key]
        added = [new_by_key[k] for k in added_keys if k in new_by_key]

        return auto_matches, removed, added, needs_validation

    def get_method_description(self) -> str:
        """Return a description of the method used.

        Returns:
            Human-readable description.
        """
        t = self.thresholds
        descriptions = {
            SimilarityMethod.MD5: "Hash MD5 (identité stricte)",
            SimilarityMethod.COMBINED: (
                f"Combiné IoU + Hausdorff: "
                f"identique >= {t.identical_min:.0%}, "
                f"probable >= {t.likely_match_min:.0%} & <= {t.hausdorff_max:.0f}m"
            ),
            SimilarityMethod.JACCARD: f"IoU >= {t.identical_min:.0%}",
            SimilarityMethod.HAUSDORFF: f"Hausdorff <= {t.hausdorff_max:.0f}m",
        }
        return descriptions.get(self.method, str(self.method))
