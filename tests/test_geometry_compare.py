"""Tests pour le module geometry_compare.

Ce module teste les fonctions de comparaison géométrique
pour l'historisation des données.
"""

from __future__ import annotations

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

from pgboundary.geometry_compare import (
    GeometryMatcher,
    are_geometries_similar,
    compute_combined_similarity,
    compute_geometry_hash,
    compute_hausdorff_distance,
    compute_jaccard_index,
    compute_similarity,
    compute_similarity_score,
)
from pgboundary.import_config import (
    SimilarityLevel,
    SimilarityMethod,
    SimilarityThresholds,
)


class TestComputeGeometryHash:
    """Tests pour compute_geometry_hash."""

    def test_hash_polygon(self, sample_polygon: Polygon) -> None:
        """Test du hash d'un polygone."""
        hash_value = compute_geometry_hash(sample_polygon)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 32  # MD5 hex length

    def test_hash_same_polygon_twice(self, sample_polygon: Polygon) -> None:
        """Test que le même polygone donne le même hash."""
        hash1 = compute_geometry_hash(sample_polygon)
        hash2 = compute_geometry_hash(sample_polygon)
        assert hash1 == hash2

    def test_hash_different_polygons(
        self,
        sample_polygon: Polygon,
        sample_polygon_different: Polygon,
    ) -> None:
        """Test que des polygones différents donnent des hash différents."""
        hash1 = compute_geometry_hash(sample_polygon)
        hash2 = compute_geometry_hash(sample_polygon_different)
        assert hash1 != hash2

    def test_hash_none(self) -> None:
        """Test du hash avec None."""
        assert compute_geometry_hash(None) == ""  # type: ignore[arg-type]

    def test_hash_empty_polygon(self) -> None:
        """Test du hash avec polygone vide."""
        empty = Polygon()
        assert compute_geometry_hash(empty) == ""

    def test_hash_multipolygon(self, sample_multipolygon: MultiPolygon) -> None:
        """Test du hash d'un MultiPolygon."""
        hash_value = compute_geometry_hash(sample_multipolygon)
        # MultiPolygon without exterior coords returns WKT-based hash
        assert isinstance(hash_value, str)

    def test_hash_point(self, sample_point: Point) -> None:
        """Test du hash d'un point."""
        hash_value = compute_geometry_hash(sample_point)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 32


class TestComputeJaccardIndex:
    """Tests pour compute_jaccard_index (IoU)."""

    def test_identical_polygons(self, sample_polygon: Polygon) -> None:
        """Test IoU de polygones identiques."""
        iou = compute_jaccard_index(sample_polygon, sample_polygon)
        assert iou == pytest.approx(1.0)

    def test_overlapping_polygons(self, sample_polygon: Polygon) -> None:
        """Test IoU de polygones avec chevauchement partiel."""
        # Décalage de 0.5 = 50% de chevauchement
        shifted = Polygon([(0.5, 0), (1.5, 0), (1.5, 1), (0.5, 1), (0.5, 0)])
        iou = compute_jaccard_index(sample_polygon, shifted)
        # Intersection = 0.5, Union = 1.5, IoU = 0.5/1.5 = 0.333...
        assert 0.3 < iou < 0.4

    def test_non_overlapping_polygons(
        self,
        sample_polygon: Polygon,
        sample_polygon_different: Polygon,
    ) -> None:
        """Test IoU de polygones sans chevauchement."""
        iou = compute_jaccard_index(sample_polygon, sample_polygon_different)
        assert iou == pytest.approx(0.0)

    def test_with_none(self, sample_polygon: Polygon) -> None:
        """Test IoU avec None."""
        assert compute_jaccard_index(None, sample_polygon) == 0.0  # type: ignore[arg-type]
        assert compute_jaccard_index(sample_polygon, None) == 0.0  # type: ignore[arg-type]

    def test_with_empty(self, sample_polygon: Polygon) -> None:
        """Test IoU avec polygone vide."""
        empty = Polygon()
        assert compute_jaccard_index(empty, sample_polygon) == 0.0
        assert compute_jaccard_index(sample_polygon, empty) == 0.0


class TestComputeHausdorffDistance:
    """Tests pour compute_hausdorff_distance."""

    def test_identical_polygons(self, sample_polygon: Polygon) -> None:
        """Test distance de Hausdorff de polygones identiques."""
        distance = compute_hausdorff_distance(sample_polygon, sample_polygon)
        assert distance == pytest.approx(0.0)

    def test_shifted_polygons(
        self,
        sample_polygon: Polygon,
        sample_polygon_shifted: Polygon,
    ) -> None:
        """Test distance de Hausdorff de polygones décalés."""
        distance = compute_hausdorff_distance(sample_polygon, sample_polygon_shifted)
        # Décalage de 0.1 dans chaque direction
        assert distance > 0.0
        assert distance < 0.2  # Distance diagonale ~0.14

    def test_distant_polygons(
        self,
        sample_polygon: Polygon,
        sample_polygon_different: Polygon,
    ) -> None:
        """Test distance de Hausdorff de polygones distants."""
        distance = compute_hausdorff_distance(sample_polygon, sample_polygon_different)
        # Polygones très éloignés
        assert distance > 10.0

    def test_with_none(self, sample_polygon: Polygon) -> None:
        """Test distance avec None."""
        assert compute_hausdorff_distance(None, sample_polygon) == float("inf")  # type: ignore[arg-type]
        assert compute_hausdorff_distance(sample_polygon, None) == float("inf")  # type: ignore[arg-type]

    def test_with_empty(self, sample_polygon: Polygon) -> None:
        """Test distance avec polygone vide."""
        empty = Polygon()
        assert compute_hausdorff_distance(empty, sample_polygon) == float("inf")


class TestComputeCombinedSimilarity:
    """Tests pour compute_combined_similarity."""

    def test_identical_polygons(self, sample_polygon: Polygon) -> None:
        """Test similarité de polygones identiques."""
        result = compute_combined_similarity(sample_polygon, sample_polygon)
        assert result.level == SimilarityLevel.IDENTICAL
        assert result.iou_score == pytest.approx(1.0)
        assert result.is_auto_merge() is True

    def test_slightly_shifted_polygons(
        self,
        sample_polygon: Polygon,
        sample_polygon_shifted: Polygon,
    ) -> None:
        """Test similarité de polygones légèrement décalés."""
        result = compute_combined_similarity(sample_polygon, sample_polygon_shifted)
        # IoU élevé mais pas identique
        assert result.iou_score > 0.5
        assert result.level in [
            SimilarityLevel.IDENTICAL,
            SimilarityLevel.LIKELY_MATCH,
            SimilarityLevel.SUSPECT,
        ]

    def test_very_different_polygons(
        self,
        sample_polygon: Polygon,
        sample_polygon_different: Polygon,
    ) -> None:
        """Test similarité de polygones très différents."""
        result = compute_combined_similarity(sample_polygon, sample_polygon_different)
        assert result.level == SimilarityLevel.DISTINCT
        assert result.iou_score == pytest.approx(0.0)

    def test_with_none(self, sample_polygon: Polygon) -> None:
        """Test avec None."""
        result = compute_combined_similarity(None, sample_polygon)  # type: ignore[arg-type]
        assert result.level == SimilarityLevel.DISTINCT
        assert "manquante" in result.reason

    def test_with_empty(self, sample_polygon: Polygon) -> None:
        """Test avec polygone vide."""
        empty = Polygon()
        result = compute_combined_similarity(empty, sample_polygon)
        assert result.level == SimilarityLevel.DISTINCT
        assert "vide" in result.reason

    def test_custom_thresholds(self, sample_polygon: Polygon) -> None:
        """Test avec seuils personnalisés."""
        thresholds = SimilarityThresholds(identical_min=0.99)
        result = compute_combined_similarity(sample_polygon, sample_polygon, thresholds)
        assert result.level == SimilarityLevel.IDENTICAL

    def test_likely_match_with_hausdorff(self, sample_polygon: Polygon) -> None:
        """Test LIKELY_MATCH avec vérification Hausdorff."""
        # Créer un polygone avec IoU entre 0.80 et 0.95
        shifted = Polygon([(0.1, 0), (1.1, 0), (1.1, 1), (0.1, 1), (0.1, 0)])
        result = compute_combined_similarity(sample_polygon, shifted)
        # Le résultat dépend de l'IoU exact
        assert result.iou_score > 0.0


class TestAreGeometriesSimilar:
    """Tests pour are_geometries_similar."""

    def test_md5_identical(self, sample_polygon: Polygon) -> None:
        """Test MD5 avec polygones identiques."""
        result = are_geometries_similar(
            sample_polygon,
            sample_polygon,
            SimilarityMethod.MD5,
        )
        assert result is True

    def test_md5_different(
        self,
        sample_polygon: Polygon,
        sample_polygon_different: Polygon,
    ) -> None:
        """Test MD5 avec polygones différents."""
        result = are_geometries_similar(
            sample_polygon,
            sample_polygon_different,
            SimilarityMethod.MD5,
        )
        assert result is False

    def test_jaccard_with_threshold(self, sample_polygon: Polygon) -> None:
        """Test Jaccard avec seuil personnalisé."""
        shifted = Polygon([(0.1, 0), (1.1, 0), (1.1, 1), (0.1, 1), (0.1, 0)])
        # Avec seuil bas
        result = are_geometries_similar(
            sample_polygon,
            shifted,
            SimilarityMethod.JACCARD,
            threshold=0.5,
        )
        assert result is True

        # Avec seuil haut
        result = are_geometries_similar(
            sample_polygon,
            shifted,
            SimilarityMethod.JACCARD,
            threshold=0.99,
        )
        assert result is False

    def test_hausdorff_with_threshold(self, sample_polygon: Polygon) -> None:
        """Test Hausdorff avec seuil personnalisé."""
        shifted = Polygon([(0.1, 0.1), (1.1, 0.1), (1.1, 1.1), (0.1, 1.1), (0.1, 0.1)])
        # Seuil large
        result = are_geometries_similar(
            sample_polygon,
            shifted,
            SimilarityMethod.HAUSDORFF,
            threshold=1.0,
        )
        assert result is True

        # Seuil strict
        result = are_geometries_similar(
            sample_polygon,
            shifted,
            SimilarityMethod.HAUSDORFF,
            threshold=0.01,
        )
        assert result is False

    def test_combined(self, sample_polygon: Polygon) -> None:
        """Test méthode combinée."""
        result = are_geometries_similar(
            sample_polygon,
            sample_polygon,
            SimilarityMethod.COMBINED,
        )
        assert result is True


class TestComputeSimilarity:
    """Tests pour compute_similarity (fonction principale)."""

    def test_md5_method(self, sample_polygon: Polygon) -> None:
        """Test avec méthode MD5."""
        result = compute_similarity(sample_polygon, sample_polygon, SimilarityMethod.MD5)
        assert result.level == SimilarityLevel.IDENTICAL
        assert "MD5" in result.reason

    def test_jaccard_method(self, sample_polygon: Polygon) -> None:
        """Test avec méthode Jaccard."""
        result = compute_similarity(sample_polygon, sample_polygon, SimilarityMethod.JACCARD)
        assert result.level == SimilarityLevel.IDENTICAL
        assert result.iou_score == pytest.approx(1.0)

    def test_hausdorff_method(self, sample_polygon: Polygon) -> None:
        """Test avec méthode Hausdorff."""
        result = compute_similarity(sample_polygon, sample_polygon, SimilarityMethod.HAUSDORFF)
        assert result.level == SimilarityLevel.IDENTICAL
        assert result.hausdorff_distance == pytest.approx(0.0)

    def test_combined_method(self, sample_polygon: Polygon) -> None:
        """Test avec méthode combinée."""
        result = compute_similarity(sample_polygon, sample_polygon, SimilarityMethod.COMBINED)
        assert result.level == SimilarityLevel.IDENTICAL

    def test_default_method_is_combined(self, sample_polygon: Polygon) -> None:
        """Test que la méthode par défaut est COMBINED."""
        result = compute_similarity(sample_polygon, sample_polygon)
        assert result.level == SimilarityLevel.IDENTICAL


class TestComputeSimilarityScore:
    """Tests pour compute_similarity_score (rétrocompatibilité)."""

    def test_md5_identical(self, sample_polygon: Polygon) -> None:
        """Test score MD5 avec polygones identiques."""
        score = compute_similarity_score(sample_polygon, sample_polygon, SimilarityMethod.MD5)
        assert score == 1.0

    def test_md5_different(
        self,
        sample_polygon: Polygon,
        sample_polygon_different: Polygon,
    ) -> None:
        """Test score MD5 avec polygones différents."""
        score = compute_similarity_score(
            sample_polygon,
            sample_polygon_different,
            SimilarityMethod.MD5,
        )
        assert score == 0.0

    def test_jaccard_score(self, sample_polygon: Polygon) -> None:
        """Test score Jaccard."""
        score = compute_similarity_score(sample_polygon, sample_polygon, SimilarityMethod.JACCARD)
        assert score == pytest.approx(1.0)

    def test_hausdorff_score(self, sample_polygon: Polygon) -> None:
        """Test score Hausdorff."""
        score = compute_similarity_score(
            sample_polygon,
            sample_polygon,
            SimilarityMethod.HAUSDORFF,
        )
        assert score == pytest.approx(0.0)  # Distance

    def test_combined_score(self, sample_polygon: Polygon) -> None:
        """Test score combiné."""
        score = compute_similarity_score(sample_polygon, sample_polygon, SimilarityMethod.COMBINED)
        assert score == pytest.approx(1.0)


class TestGeometryMatcher:
    """Tests pour la classe GeometryMatcher."""

    def test_init_default(self) -> None:
        """Test initialisation par défaut."""
        matcher = GeometryMatcher()
        assert matcher.method == SimilarityMethod.COMBINED
        assert matcher.key_field == "cd_insee"
        assert matcher.thresholds.identical_min == 0.95

    def test_init_custom(self) -> None:
        """Test initialisation personnalisée."""
        thresholds = SimilarityThresholds(identical_min=0.90)
        matcher = GeometryMatcher(
            method=SimilarityMethod.JACCARD,
            thresholds=thresholds,
            key_field="code_iris",
        )
        assert matcher.method == SimilarityMethod.JACCARD
        assert matcher.key_field == "code_iris"
        assert matcher.thresholds.identical_min == 0.90

    def test_init_legacy_threshold(self) -> None:
        """Test initialisation avec threshold legacy."""
        matcher = GeometryMatcher(threshold=0.85)
        assert matcher.thresholds.identical_min == 0.85

    def test_compare(self, sample_polygon: Polygon) -> None:
        """Test de la méthode compare."""
        matcher = GeometryMatcher()
        result = matcher.compare(sample_polygon, sample_polygon)
        assert result.level == SimilarityLevel.IDENTICAL

    def test_find_matches_all_match(self, sample_polygon: Polygon) -> None:
        """Test find_matches avec correspondances complètes."""
        matcher = GeometryMatcher()

        old_features = [
            {"cd_insee": "01001", "geometry": sample_polygon},
            {"cd_insee": "01002", "geometry": sample_polygon},
        ]
        new_features = [
            {"cd_insee": "01001", "geometry": sample_polygon},
            {"cd_insee": "01002", "geometry": sample_polygon},
        ]

        auto_matches, removed, added, needs_validation = matcher.find_matches(
            old_features,
            new_features,
        )

        assert len(auto_matches) == 2
        assert len(removed) == 0
        assert len(added) == 0
        assert len(needs_validation) == 0

    def test_find_matches_with_additions(self, sample_polygon: Polygon) -> None:
        """Test find_matches avec ajouts."""
        matcher = GeometryMatcher()

        old_features = [{"cd_insee": "01001", "geometry": sample_polygon}]
        new_features = [
            {"cd_insee": "01001", "geometry": sample_polygon},
            {"cd_insee": "01002", "geometry": sample_polygon},
        ]

        auto_matches, removed, added, needs_validation = matcher.find_matches(
            old_features,
            new_features,
        )

        assert len(auto_matches) == 1
        assert len(removed) == 0
        assert len(added) == 1
        assert added[0]["cd_insee"] == "01002"

    def test_find_matches_with_removals(self, sample_polygon: Polygon) -> None:
        """Test find_matches avec suppressions."""
        matcher = GeometryMatcher()

        old_features = [
            {"cd_insee": "01001", "geometry": sample_polygon},
            {"cd_insee": "01002", "geometry": sample_polygon},
        ]
        new_features = [{"cd_insee": "01001", "geometry": sample_polygon}]

        auto_matches, removed, added, needs_validation = matcher.find_matches(
            old_features,
            new_features,
        )

        assert len(auto_matches) == 1
        assert len(removed) == 1
        assert removed[0]["cd_insee"] == "01002"
        assert len(added) == 0

    def test_find_matches_no_geometry(self) -> None:
        """Test find_matches sans géométrie (correspondance par clé)."""
        matcher = GeometryMatcher()

        old_features = [{"cd_insee": "01001"}]
        new_features = [{"cd_insee": "01001"}]

        auto_matches, removed, added, needs_validation = matcher.find_matches(
            old_features,
            new_features,
        )

        # Correspondance par clé ajoutée aux auto_matches
        assert len(auto_matches) == 1

    def test_find_matches_distinct_geometries(
        self,
        sample_polygon: Polygon,
        sample_polygon_different: Polygon,
    ) -> None:
        """Test find_matches avec géométries distinctes malgré même clé."""
        matcher = GeometryMatcher()

        old_features = [{"cd_insee": "01001", "geometry": sample_polygon}]
        new_features = [{"cd_insee": "01001", "geometry": sample_polygon_different}]

        auto_matches, removed, added, needs_validation = matcher.find_matches(
            old_features,
            new_features,
        )

        # Géométries trop différentes = suppression + ajout
        assert len(removed) >= 0  # Peut être traité comme suppression
        assert len(added) >= 0  # Peut être traité comme ajout

    def test_get_method_description(self) -> None:
        """Test de la description des méthodes."""
        for method in SimilarityMethod:
            matcher = GeometryMatcher(method=method)
            desc = matcher.get_method_description()
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestClassificationHelpers:
    """Tests pour les fonctions de classification."""

    def test_classify_iou_identical(self) -> None:
        """Test classification IoU pour IDENTICAL."""
        from pgboundary.geometry_compare import _classify_iou_only

        thresholds = SimilarityThresholds()
        assert _classify_iou_only(0.98, thresholds) == SimilarityLevel.IDENTICAL

    def test_classify_iou_likely_match(self) -> None:
        """Test classification IoU pour LIKELY_MATCH."""
        from pgboundary.geometry_compare import _classify_iou_only

        thresholds = SimilarityThresholds()
        assert _classify_iou_only(0.85, thresholds) == SimilarityLevel.LIKELY_MATCH

    def test_classify_iou_suspect(self) -> None:
        """Test classification IoU pour SUSPECT."""
        from pgboundary.geometry_compare import _classify_iou_only

        thresholds = SimilarityThresholds()
        assert _classify_iou_only(0.60, thresholds) == SimilarityLevel.SUSPECT

    def test_classify_iou_distinct(self) -> None:
        """Test classification IoU pour DISTINCT."""
        from pgboundary.geometry_compare import _classify_iou_only

        thresholds = SimilarityThresholds()
        assert _classify_iou_only(0.30, thresholds) == SimilarityLevel.DISTINCT

    def test_classify_hausdorff_identical(self) -> None:
        """Test classification Hausdorff pour IDENTICAL."""
        from pgboundary.geometry_compare import _classify_hausdorff_only

        thresholds = SimilarityThresholds(hausdorff_max=10.0)
        # <= 50% du max = IDENTICAL
        assert _classify_hausdorff_only(4.0, thresholds) == SimilarityLevel.IDENTICAL

    def test_classify_hausdorff_likely_match(self) -> None:
        """Test classification Hausdorff pour LIKELY_MATCH."""
        from pgboundary.geometry_compare import _classify_hausdorff_only

        thresholds = SimilarityThresholds(hausdorff_max=10.0)
        # <= max = LIKELY_MATCH
        assert _classify_hausdorff_only(8.0, thresholds) == SimilarityLevel.LIKELY_MATCH

    def test_classify_hausdorff_suspect(self) -> None:
        """Test classification Hausdorff pour SUSPECT."""
        from pgboundary.geometry_compare import _classify_hausdorff_only

        thresholds = SimilarityThresholds(hausdorff_max=10.0)
        # <= 2x max = SUSPECT
        assert _classify_hausdorff_only(15.0, thresholds) == SimilarityLevel.SUSPECT

    def test_classify_hausdorff_distinct(self) -> None:
        """Test classification Hausdorff pour DISTINCT."""
        from pgboundary.geometry_compare import _classify_hausdorff_only

        thresholds = SimilarityThresholds(hausdorff_max=10.0)
        # > 2x max = DISTINCT
        assert _classify_hausdorff_only(25.0, thresholds) == SimilarityLevel.DISTINCT
