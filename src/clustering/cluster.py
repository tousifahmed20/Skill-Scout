"""Fuzzy clustering, labeling, and nearest-neighbour lookup over embedding
vectors (stage 05). Pure Python (stdlib only) so it needs no numpy and is
testable with hand-made vectors; vectors come from embed.py in the CI build.

Membership is fuzzy (CONTEXT.md): a skill belongs to every cluster whose seed it
is within `threshold` cosine of, so one skill can sit in several overlapping
groups. Clustering is global by default; pass a `group` key per item (e.g. a
category, when one exists) to cluster within groups instead.
"""
from __future__ import annotations
import math
from collections import Counter

THRESHOLD = 0.6     # tuned default; cluster membership cosine floor
_STOP = {"the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "your",
         "my", "this", "that", "it", "is", "are", "be", "skill", "use", "using", "help",
         "when", "from", "into", "as", "by", "at", "you", "will", "can", "based"}


def cosine(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def nearest(vectors: dict[str, list[float]], query: list[float], k: int = 30) -> list[tuple[str, float]]:
    scored = [(cid, cosine(query, v)) for cid, v in vectors.items()]
    scored.sort(key=lambda s: (-s[1], s[0]))
    return scored[:k]


def _cluster_one(items: list[tuple[str, list[float]]], threshold: float) -> list[dict]:
    """Seed on dense cores, membership is fuzzy. Seeds are chosen by tightness
    (highest similarity to any neighbour — a group core, not a between-groups
    bridge) and only when not already within `threshold` of an existing seed;
    each cluster is then everything within `threshold` of its seed, computed
    independently, so an item similar to two cores lands in both (overlap).
    ponytail: O(n^2) cosine — fine for a CI build over a few thousand skills;
    use nearest()/ANN if the v2 shared cache grows past that."""
    vecs = dict(items)
    ids = [c for c, _ in items]
    tight = {c: max((cosine(vecs[c], vecs[d]) for d in ids if d != c), default=0.0) for c in ids}
    order = sorted(ids, key=lambda c: (-tight[c], c))
    seeds: list[str] = []
    for c in order:
        if all(cosine(vecs[c], vecs[s]) < threshold for s in seeds):
            seeds.append(c)
    clusters = []
    for s in seeds:
        members = [c for c in ids if cosine(vecs[s], vecs[c]) >= threshold]   # includes s
        clusters.append({"seed": s, "members": members,
                         "similarity": {m: round(cosine(vecs[s], vecs[m]), 4) for m in members}})
    return clusters


def cluster(items: list[tuple[str, list[float]]], threshold: float = THRESHOLD,
            groups: dict[str, str] | None = None) -> list[dict]:
    """items: (candidate_id, vector). groups: optional candidate_id -> group key.
    Returns clusters, each {seed, members, similarity, group}."""
    if not groups:
        return [{**c, "group": None} for c in _cluster_one(items, threshold)]
    out = []
    by_group: dict[str, list] = {}
    for cid, v in items:
        by_group.setdefault(groups.get(cid, ""), []).append((cid, v))
    for g, its in by_group.items():
        out += [{**c, "group": g} for c in _cluster_one(its, threshold)]
    return out


def label(member_ids: list[str], texts: dict[str, str], seed: str | None = None) -> str:
    """3-6 word label from the cluster's members' text (names/descriptions).
    Most frequent content words; falls back to the seed's text."""
    words = []
    for cid in member_ids:
        words += [w for w in _words(texts.get(cid, "")) if w not in _STOP and len(w) > 2]
    top = [w for w, _ in Counter(words).most_common(6)]
    if len(top) >= 3:
        return " ".join(top[:6])
    base = texts.get(seed or (member_ids[0] if member_ids else ""), "")
    return " ".join(base.split()[:6]) or "unlabeled"


def _words(text: str) -> list[str]:
    out, cur = [], []
    for ch in (text or "").lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.append("".join(cur)); cur = []
    if cur:
        out.append("".join(cur))
    return out
