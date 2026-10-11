"""Seeding-cost estimator for Skill Scout v1 (stage 01).

Implements the cost model in
`stages/01_golden-set/references/cost-model.md`:

    seeding_cost = evaluations * tokens_per_evaluation * price_per_token

v1 has ONE owner-side LLM cost: a one-time seeding run (stage 06 evaluation of
the golden set plus the top candidates per category). There are no recurring
jobs, no server LLM jobs, and no user keys — spot checks / audits / external
classification are v2 (stages 10-11). (Budget single home: CLAUDE.md.)

The cheapest path is $0: the owner seeds using their own Claude Code
subscription. The API fallback is bounded by the v1 seeding budget (<= $5).

Rules honored here:
- Prices are NEVER hardcoded. They are read live from the provider's pricing
  page each run (Claude Haiku 4.5 = the smallest capable model). `--price-in` /
  `--price-out` override only for offline use and the self-check.
- `tokens_per_evaluation` is an ASSUMPTION. The real per-eval token budget is
  owned by stage 06 (evidence budget); stage 01 cannot read forward to it, so
  the default below is a placeholder stage 06 will replace. Prices are already
  live.

Run:  python -m src.cost.estimate              # live prices
      python -m src.cost.estimate --selfcheck   # offline arithmetic check
"""
from __future__ import annotations
import argparse
import re
import urllib.request

PRICING_URL = "https://docs.anthropic.com/en/docs/about-claude/pricing"
PRICED_MODEL = "Claude Haiku 4.5"  # smallest capable model (cost-model.md)
SEEDING_BUDGET_USD = 5.0           # v1 one-time seeding cap (single home: CLAUDE.md)
GOLDEN_SET_SIZE = 40               # seeded first (data/golden-set/golden_set.json)

# ASSUMPTION pending stage 06's evidence budget: one evaluation reads a skill's
# SKILL.md + a sampled evidence slice + prompt, and emits a structured verdict.
TOKENS_IN_PER_EVAL = 12_000
TOKENS_OUT_PER_EVAL = 1_500


def fetch_prices(url: str = PRICING_URL, model: str = PRICED_MODEL):
    """Return (input_$_per_MTok, output_$_per_MTok) read live from the page.

    Raises RuntimeError if the row cannot be parsed, so a scrape break surfaces
    loudly instead of silently using a stale number.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 skill-scout"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    # First "<model> $IN / MTok $OUT / MTok" is the standard (non-batch) row.
    m = re.search(
        re.escape(model) + r"\s*\$?([\d.]+)\s*/\s*MTok\s*\$?([\d.]+)\s*/\s*MTok",
        text,
    )
    if not m:
        raise RuntimeError(
            f"Could not parse {model} pricing from {url}. "
            f"Pass --price-in and --price-out (read them from the page)."
        )
    return float(m.group(1)), float(m.group(2))


def eval_cost(price_in, price_out, tokens_in=TOKENS_IN_PER_EVAL, tokens_out=TOKENS_OUT_PER_EVAL):
    """Cost of a single evaluation. Prices are $/MTok."""
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def estimate(price_in, price_out, budget=SEEDING_BUDGET_USD, golden=GOLDEN_SET_SIZE):
    unit = eval_cost(price_in, price_out)
    evals_that_fit = int(budget // unit)
    golden_cost = golden * unit
    return {
        "price_in": price_in, "price_out": price_out, "budget": budget,
        "cost_per_eval": unit,
        "evals_that_fit_budget": evals_that_fit,
        "golden_set_size": golden,
        "golden_set_cost": golden_cost,
        "golden_set_fits": golden_cost <= budget,
        # After the 40 golden skills, this many more candidate evals fit.
        "extra_candidate_evals": max(0, evals_that_fit - golden),
    }


def _fmt(r):
    return "\n".join([
        f"Model: {PRICED_MODEL}   price ${r['price_in']:.2f}/MTok in, "
        f"${r['price_out']:.2f}/MTok out",
        f"v1 seeding budget: ${r['budget']:.2f} one-time (or $0 via the owner's "
        f"Claude Code subscription). No recurring or server LLM jobs in v1.",
        "",
        f"Cost per evaluation      : ${r['cost_per_eval']:.4f}  "
        f"({TOKENS_IN_PER_EVAL} in + {TOKENS_OUT_PER_EVAL} out tokens, stage-01 assumption)",
        f"Evaluations that fit ${r['budget']:.0f} : {r['evals_that_fit_budget']}",
        f"Golden set ({r['golden_set_size']} skills) : ${r['golden_set_cost']:.2f}  "
        f"({'FITS' if r['golden_set_fits'] else 'OVER'} budget)",
        f"Headroom for more candidates: {r['extra_candidate_evals']} evals "
        f"(seed golden set first, then top pre-score candidates per category until budget is used)",
        "",
        "tokens_per_evaluation is a stage-01 assumption (owner: stage 06 evidence "
        "budget). Prices are read live, never hardcoded.",
    ])


def _selfcheck():
    # Fixed prices, no network: lock the arithmetic.
    pin, pout = 1.0, 5.0
    assert abs(eval_cost(pin, pout) - 0.0195) < 1e-9
    r = estimate(pin, pout)
    assert r["evals_that_fit_budget"] == int(5.0 // 0.0195) == 256
    assert abs(r["golden_set_cost"] - 40 * 0.0195) < 1e-9
    assert r["golden_set_fits"]
    assert r["extra_candidate_evals"] == 256 - 40 == 216
    print("selfcheck OK:", f"${r['cost_per_eval']:.4f}/eval,",
          f"{r['evals_that_fit_budget']} evals fit $5,",
          f"golden set ${r['golden_set_cost']:.2f} (+{r['extra_candidate_evals']} more)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Skill Scout v1 seeding-cost estimator")
    ap.add_argument("--selfcheck", action="store_true", help="offline arithmetic check")
    ap.add_argument("--price-in", type=float, help="override $/MTok input")
    ap.add_argument("--price-out", type=float, help="override $/MTok output")
    ap.add_argument("--budget", type=float, default=SEEDING_BUDGET_USD)
    a = ap.parse_args(argv)
    if a.selfcheck:
        _selfcheck()
        return
    if a.price_in is not None and a.price_out is not None:
        pin, pout = a.price_in, a.price_out
    else:
        pin, pout = fetch_prices()
    print(_fmt(estimate(pin, pout, budget=a.budget)))


if __name__ == "__main__":
    main()
