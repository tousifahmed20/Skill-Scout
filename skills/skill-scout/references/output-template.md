# Output template

```
Top picks for: "<task_text>"        Your harness: <host_harness name>

1. <skill_name> — <repo>/<skill_path>
   [<Established | Hidden Gem — less battle-tested>]  [<Verified | Tested once | Inspected>]
   Does: <actually_does>
   Fit: <Full | Partial — missing: …>
   Strengths: <up to 3 features>
   Limitations: <text> (<evidence>); …
   Claims: <n> supported · <n> unsupported (<top_unsupported>) · <n> unverifiable
   Works in: Claude Code ✓ · Codex ✓ · Gemini CLI ◐ <short reason> · Antigravity ✓ · Cursor ✓ · GitHub Copilot ?
   Tested on: <tested_on harness names | not tested>
   Needs: <runtimes · OS · system tools · services/API keys (paid?) · network>
   Install: <install.command>
   Sources: <files, issues, URLs>
   Flags: <suspicious popularity | popular but unproven>

2. …
3. …

Why #1 over #2: <one line from differentiator>
Set aside: <skill_name> — <reason>
<Offer: "Want a with/without test of #1? Estimated cost: <n> tokens.">

✓ works · ◐ works with limits · ✗ won't work · ? unknown
```

## Rules
- Omit a line when it has no content (no flags → no Flags line; nothing set aside → no Set aside line).
- Show at most one Set aside line: the strongest one.
- Use display names from `harness_names`, never ids.
- The ◐ reason is the first reason from the compatibility record, shortened to a few words.
