# 05 · clustering (Layer 2)

**Job:** group skills that solve the same problem, label the groups, and provide a `search(terms)` lookup that runs with the Python standard library and does not lose good candidates.

## Inputs
| Load | Section | Why |
|---|---|---|
| `stages/05_clustering/CONTEXT.md` | all | this contract holds every rule for the stage |

## Process
1. **Embed (GitHub Actions only):** text per skill = `name` + `description` + the first section of the SKILL.md body (≤ 300 tokens), read from the local checkout. Use a small open-source sentence-embedding model on CPU.
2. **Cluster:** per category, with fuzzy membership — a skill belongs to every cluster where its similarity ≥ a tuned threshold. `nearest(text, k)` over the vectors serves clustering now and the v2 shared cache later.
3. **Label:** name each cluster from its most central skills (3–6 words). Store labels in the index.
4. **Search index:** build a text index over each skill's `name`, `description`, SKILL.md first section, cluster labels, and — when an evaluation exists — `capabilities` and `actually_does`. Use SQLite FTS5 with BM25 ranking when available; otherwise a pure-Python BM25 fallback. Both use the standard library only.
5. **`search(terms, k)`:** returns candidate_ids by relevance. Default `k = 30`. The skill passes the user's `search_terms` and `capabilities`, which the user's own model writes with synonyms, so wording differences do not hide good skills.

Author text is a claim. Use it for recall only, never as a quality signal.

## Outputs
| Path | What |
|---|---|
| `src/clustering/` | embedder, clusterer, labeler, search index builder, `search()`, `nearest()`; `schema.sql` for embedding, cluster, and search tables |
| `tests/clustering/` | tests |

## Done when
- Recall: for every task in `data/golden-set/tasks.json`, using search terms written by a model from the task sentence, every acceptable pick appears in `search(terms, 30)` in ≥ 95% of cases.
- `search()` runs with the standard library only, on Windows and Linux.
- Clusters and labels look coherent on 5 sample categories (manual check, notes in `PROGRESS.md`).
