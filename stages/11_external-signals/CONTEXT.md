# 11 · external-signals (Layer 2)

**Release: v2.** Not part of the free launch: the classifier uses owner LLM spend, and Reddit's API terms must be checked first.

**Job:** for ranked finalists only, find unsolicited firsthand reports outside GitHub, and detect coordinated launches. Fill the `external_reports` slot that ranking already reads.

## Inputs
| Load | Section | Why |
|---|---|---|
| `stages/08_ranking/references/scoring.md` | `#signal-slots` | the `external_reports` table to fill |

## Process
1. Sources, in order: Hacker News (Algolia search API), then relevant Reddit communities. Add niche sources later, only for categories where users ask often.
2. Search by repo URL and by skill name plus repo owner. Keep only posts that clearly refer to this skill.
3. Classify each post with the smallest capable model on a short snippet (server budget): `firsthand` (the author says they used it) and `sentiment`.
4. Coordinated launch: many mentions within 48 h of the first commit or release, and no organic mentions after 30 days → set `launch_window: true` on those rows.
5. Run for finalists of popular queries; refresh monthly. Log the spend in the ledger.

## Outputs
| Path | What |
|---|---|
| `src/external/` | fetchers, classifier, launch detector (writes `external_reports`) |
| `tests/external/` | tests |

## Done when
- On 10 golden-set finalists, rows marked `firsthand` are correct in ≥ 80% (manual check).
- A seeded coordinated-launch pattern gets `launch_window: true`.
- Launch-window mentions do not change any score.
