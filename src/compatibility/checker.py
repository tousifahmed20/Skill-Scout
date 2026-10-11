"""Static compatibility checker (stage 03). No execution, no LLM.

For each harness in harness-profiles.json, apply rules R1-R11
(stages/03_compatibility/references/compat-rules.md) to a skill's frontmatter,
body and file list, yielding one level + reasons per harness, plus the skill's
runtime requirements and the author's declared-compatibility claim.

Tested results are NOT produced here (that is stage 07).
"""
from __future__ import annotations
import json
import re
from pathlib import Path

import yaml

# Frontmatter split is a lower-stage helper (reads go one way; collector = 02).
from src.collector.membership import split_frontmatter, NAME_RE

PROFILES_PATH = Path(__file__).resolve().parents[2] / "skills" / "skill-scout" / "references" / "harness-profiles.json"

CC_EXTENSION_KEYS = {
    "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
    "user-invocable", "disallowed-tools", "model", "effort", "paths", "shell", "background",
}
LEVEL_RANK = {"compatible": 0, "partial": 1, "incompatible": 2, "unknown": -1}
# Commands we recognize as external system tools when named in text/scripts.
KNOWN_TOOLS = ["ffmpeg", "ffprobe", "docker", "docker-compose", "git", "gh", "curl",
               "wget", "pandoc", "yt-dlp", "youtube-dl", "pdftotext", "pdfinfo",
               "tesseract", "soffice", "libreoffice", "terraform", "kubectl",
               "npm", "npx", "node", "uv", "poetry", "jq", "rg", "osascript",
               "weasyprint", "playwright", "markitdown", "scrapling"]
# ponytail: "make" dropped — the English verb matches everywhere. Add command-
# position detection if a tool name ever needs to stay despite being a common word.
# Services known to be paid (prefix before _API_KEY/_TOKEN/_KEY).
PAID_SERVICES = {"OPENAI", "ANTHROPIC", "GEMINI", "GOOGLE", "COHERE", "MISTRAL",
                 "GROQ", "REPLICATE", "HUGGINGFACE", "HF", "STRIPE", "TWILIO",
                 "BIGDATA", "RAVENPACK", "TAVILY", "SERPAPI", "FIRECRAWL"}


def load_profiles(path: Path = PROFILES_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_skill(skill_md_text: str) -> tuple[dict, str]:
    fm_text, body = split_frontmatter(skill_md_text)
    fm = {}
    if fm_text is not None:
        try:
            loaded = yaml.safe_load(fm_text)
            if isinstance(loaded, dict):
                fm = loaded
        except yaml.YAMLError:
            fm = {}
    return fm, body


def _corpus(body: str, file_texts: dict[str, str] | None) -> str:
    extra = "\n".join(file_texts.values()) if file_texts else ""
    return body + "\n" + extra


def _prose(text: str) -> str:
    """Body with fenced blocks and inline code spans removed. Shell/awk examples
    ($1 field refs, `cd .. ../out.x` build paths) live in code, not prose, so
    rules about authored instructions (R5 positionals, R10 refs) run on this."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    return text


def detect_signals(fm: dict, body: str, files: list[str], folder_name: str,
                   file_texts: dict[str, str] | None = None) -> dict:
    corpus = _corpus(body, file_texts)
    name = fm.get("name") if isinstance(fm.get("name"), str) else ""
    mcp = set(re.findall(r"mcp__([a-z0-9][a-z0-9_-]*)__", corpus))
    if isinstance(fm.get("mcp_servers"), list):
        mcp |= {str(s) for s in fm["mcp_servers"]}
    services = {}
    for pref, kind in re.findall(r"\b([A-Z][A-Z0-9_]{1,})_(API_KEY|TOKEN|SECRET|KEY)\b", corpus):
        env = f"{pref}_{kind}"
        root = pref.split("_")[0]
        services[env] = root in PAID_SERVICES
    prose = _prose(body)
    return {
        "cc_ext_keys": sorted(set(fm) & CC_EXTENSION_KEYS),
        "has_fork": fm.get("context") == "fork" or "agent" in fm,
        "has_hooks": "hooks" in fm,
        # R4 injection: `!` that opens a command span, not the closing backtick of
        # inline code ending in `!` (e.g. `#VALUE!`, `!!`).
        "has_injection": bool(re.search(r"(?<![\w`!])!`[^`]*[A-Za-z][^`]*`", body)),
        # R5: $ARGUMENTS anywhere (unambiguous); bare positionals $0-$9 only in
        # prose (awk/shell $1 live in code). Lookahead drops money ($5/mo, $12.50).
        "has_args": bool(re.search(r"\$\{?ARGUMENTS\}?", body))
                    or bool(re.search(r"(?<![\w$])\$\{?[0-9]{1,2}\}?(?![\w/.,])", prose)),
        "has_plugin_root": bool(re.search(r"\$\{CLAUDE_[A-Z_]*\}", corpus)),
        "has_allowed_tools": "allowed-tools" in fm,
        # R10: a `../` file reference in authored prose, or a `../` path in the
        # file list (symlink escape). Shell `../` build paths in code don't count.
        "outside_ref": bool(re.search(r"(?:^|[\s(\[\"'])\.\./", prose))
                       or any("../" in f for f in files),
        "name_warn": bool(name) and (name != folder_name or not NAME_RE.match(name)),
        "mcp_servers": sorted(mcp),
        "services": services,
        "name": name,
    }


def _verified_lexicons(profiles: dict) -> dict[str, set[str]]:
    out = {}
    for h in profiles["harnesses"]:
        if "tool_lexicon" not in h.get("unverified", []):
            out[h["id"]] = set(h.get("tool_lexicon", []))
    return out


def evaluate_harness(h: dict, sig: dict, corpus: str, lexicons: dict[str, set[str]]) -> dict:
    sup = h["supports"]
    reasons: list[tuple[str, str]] = []  # (level, "Rx: text")

    if sig["cc_ext_keys"] and not sup.get("claude_code_extensions"):
        reasons.append(("partial", f"R1: Claude Code keys {sig['cc_ext_keys']} ignored; activation/invocation may differ"))
    if sig["has_fork"] and not sup.get("context_fork"):
        reasons.append(("partial", "R2: context:fork/agent runs inline, not in a subagent"))
    if sig["has_hooks"] and not sup.get("hooks"):
        reasons.append(("partial", "R3: hooks will not run"))
    if sig["has_injection"] and not sup.get("body_injection"):
        reasons.append(("partial", "R4: the agent sees the raw !`command`, not its output"))
    if sig["has_args"] and not sup.get("argument_substitution"):
        reasons.append(("partial", "R5: argument substitution unavailable; infer args from the conversation"))
    if sig["has_plugin_root"] and not sup.get("claude_code_extensions"):
        reasons.append(("incompatible", "R6: ${CLAUDE_*} paths do not resolve"))
    if sig["has_allowed_tools"] and not sup.get("allowed_tools"):
        reasons.append(("partial", "R7: no tool pre-approval; the user gets prompts"))
    # R8: body needs a tool from another harness's verified lexicon that this one lacks.
    own = lexicons.get(h["id"], set())
    for owner_id, tools in lexicons.items():
        if owner_id == h["id"]:
            continue
        for tool in tools:
            if tool not in own and re.search(r"\b" + re.escape(tool) + r"\b", corpus):
                reasons.append(("partial", f"R8: step uses '{tool}' (from {owner_id}); needs a substitute here"))
    # R9: MCP servers -> requirement; incompatible if the harness lacks MCP.
    if sig["mcp_servers"] and not sup.get("mcp"):
        reasons.append(("incompatible", f"R9: needs MCP server(s) {sig['mcp_servers']}, not supported"))
    if sig["outside_ref"]:
        reasons.append(("partial", "R10: '../' references are not copied by a single-skill install"))
    if sig["name_warn"]:
        reasons.append(("partial", "R11: name/folder or name characters may trip strict loaders"))

    if not reasons:
        return {"level": "compatible", "reasons": []}
    level = max((lvl for lvl, _ in reasons), key=lambda l: LEVEL_RANK[l])
    return {"level": level, "reasons": [txt for _, txt in reasons]}


def extract_requirements(sig: dict, files: list[str], body: str,
                         file_texts: dict[str, str] | None) -> dict:
    corpus = _corpus(body, file_texts)
    exts = {Path(f).suffix.lower() for f in files}
    runtimes = set()
    if {".py"} & exts or re.search(r"\bpython3?\b", corpus):
        m = re.search(r"python\s*(>=?\s*\d+\.\d+)", corpus)
        runtimes.add(f"python{m.group(1).replace(' ', '')}" if m else "python")
    if {".js", ".mjs", ".cjs", ".ts"} & exts or re.search(r"\bnode\b", corpus):
        runtimes.add("node")
    if {".sh", ".bash"} & exts:
        runtimes.add("bash")
    os_set = set()
    if {".sh", ".bash"} & exts or re.search(r"\bosascript\b", corpus):
        os_set |= {"macos", "linux"}
    if {".ps1"} & exts:
        os_set.add("windows")
    os_list = sorted(os_set) if os_set else ["any"]
    tools = sorted({t for t in KNOWN_TOOLS if re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", corpus)})
    network = bool(re.search(r"https?://|\bcurl\b|\bwget\b|requests\.|urllib|httpx|\bfetch\(", corpus))
    services = [{"name": env, "key_env": env, "paid": paid} for env, paid in sorted(sig["services"].items())]
    return {
        "runtimes": sorted(runtimes),
        "os": os_list,
        "system_tools": tools,
        "mcp_servers": sig["mcp_servers"],
        "services": services,
        "network": network or bool(services) or bool(sig["mcp_servers"]),
    }


def _declared(fm: dict, harness_levels: dict) -> tuple[object, bool]:
    decl = fm.get("compatibility")
    if decl is None:
        return None, False
    # Names mentioned in the claim; conflict if any named harness is incompatible.
    text = json.dumps(decl).lower()
    conflict = any(hid in text and lv["level"] == "incompatible"
                   for hid, lv in harness_levels.items())
    return decl, conflict


def check_skill(skill_md_text: str, files: list[str], folder_name: str,
                profiles: dict, file_texts: dict[str, str] | None = None) -> dict:
    fm, body = parse_skill(skill_md_text)
    sig = detect_signals(fm, body, files, folder_name, file_texts)
    corpus = _corpus(body, file_texts)
    lexicons = _verified_lexicons(profiles)
    harness = {h["id"]: evaluate_harness(h, sig, corpus, lexicons) for h in profiles["harnesses"]}
    declared, conflict = _declared(fm, harness)
    return {
        "harness": harness,
        "requirements": extract_requirements(sig, files, body, file_texts),
        "declared_compatibility": declared,
        "declared_conflict": conflict,
    }


def check_candidate(candidate: dict, skill_md_text: str, files: list[str],
                    profiles: dict, file_texts: dict[str, str] | None = None) -> dict:
    folder_name = (candidate["repo"].split("/")[-1] if candidate["skill_path"] == "."
                   else candidate["skill_path"].rsplit("/", 1)[-1])
    rec = check_skill(skill_md_text, files, folder_name, profiles, file_texts)
    rec = {"candidate_id": candidate["candidate_id"],
           "content_hash": candidate.get("content_hash", ""), **rec}
    return rec
