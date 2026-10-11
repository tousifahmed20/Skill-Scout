# Anti-gaming detectors

| Flag | Trigger | Effect (applied in stage 08) |
|---|---|---|
| `star_burst` | Large star gain within 48 h where most new stargazers are not established accounts (see signals.md) | Star signals set to 0; answer shows "suspicious popularity" |
| `commit_padding` | High commit count with a very low `median_diff_lines` | Commit signal discounted |
| `sock_puppets` | Contributor accounts created in a cluster with no outside activity | Not counted as independent contributors |
| `self_filed_issues` | Issues opened by the author's or contributors' accounts | Not counted as independent reports |

Each detector needs a seeded positive and a clean control in `data/fixtures/gaming/`. Tune thresholds there, not in production.

Coordinated launches across external sites are detected in stage 11, not here.
