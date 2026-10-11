"""Clustering/labeling logic over synthetic vectors (no model needed)."""
from src.clustering.cluster import cluster, cosine, label, nearest

# Two tight cores (A near x-axis, B near y-axis) plus a bridge similar to both.
A1, A2, A3 = [1, 0, 0], [1, 0.05, 0], [1, 0.1, 0]
B1, B2, B3 = [0, 1, 0], [0, 1, 0.05], [0, 1, 0.1]
BRIDGE = [0.7, 0.7, 0]
ITEMS = [("a1", A1), ("a2", A2), ("a3", A3), ("b1", B1), ("b2", B2), ("b3", B3), ("bridge", BRIDGE)]


def _members(clusters, seed):
    return next(set(c["members"]) for c in clusters if c["seed"] == seed)


def test_cosine_basic():
    assert cosine([1, 0], [1, 0]) == 1.0
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine([1, 0], [0, 0]) == 0.0      # zero vector safe


def test_nearest_orders_by_similarity():
    got = nearest({"a1": A1, "b1": B1, "bridge": BRIDGE}, A1, k=2)
    assert got[0][0] == "a1" and got[0][1] == 1.0
    assert got[1][0] == "bridge"              # closer to A1 than B1 is


def test_fuzzy_overlap_two_cores_share_the_bridge():
    clusters = cluster(ITEMS, threshold=0.6)
    assert len(clusters) == 2, [c["seed"] for c in clusters]   # one core per group, bridge doesn't swallow
    groups = [set(c["members"]) for c in clusters]
    a = next(g for g in groups if "a1" in g)
    b = next(g for g in groups if "b1" in g)
    assert {"a1", "a2", "a3"} <= a and {"b1", "b2", "b3"} <= b
    assert "bridge" in a and "bridge" in b     # fuzzy: in both clusters
    assert all(c["seed"] in ("a1", "a2", "a3", "b1", "b2", "b3") for c in clusters)  # a core, not the bridge


def test_outlier_is_its_own_cluster():
    items = ITEMS + [("lone", [0, 0, 1])]
    clusters = cluster(items, threshold=0.6)
    lone = next(c for c in clusters if c["seed"] == "lone")
    assert lone["members"] == ["lone"]


def test_label_from_member_text_3_to_6_words():
    texts = {"a1": "PDF report generator create", "a2": "generate PDF document report",
             "a3": "PDF report export printing"}
    lab = label(["a1", "a2", "a3"], texts, "a1")
    assert 3 <= len(lab.split()) <= 6
    assert "pdf" in lab and "report" in lab    # frequent content words, stopwords dropped
