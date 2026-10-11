from src.collector import membership as m

GOOD = """---
name: pdf-helper
description: Do real things with PDF files, merge split and extract text.
license: MIT
---

# PDF Helper

Step one: read the file.
Step two: extract the text.
Step three: write the output.
Step four: verify the result.
"""


def ev(text, files=("SKILL.md",), folder="pdf-helper"):
    return m.evaluate(list(files), text, folder)


def test_accept_good_skill():
    r = ev(GOOD)
    assert r.accepted
    assert r.name == "pdf-helper"
    assert "license" in r.frontmatter_keys
    assert r.spec_warnings == []


def test_reject_no_skill_md():
    r = m.evaluate(["README.md", "main.py"], None, "thing")
    assert not r.accepted and r.reason == "no_skill_md"


def test_reject_wrong_filename():
    r = m.evaluate(["skill.md"], None, "thing")
    assert not r.accepted and r.reason == "wrong_filename"


def test_reject_bad_frontmatter_unparseable():
    bad = "---\nname: x\n  description: : : broken\n\t- junk\n---\nbody line\n" * 1
    r = ev(bad)
    assert not r.accepted and r.reason == "bad_frontmatter"


def test_reject_bad_frontmatter_missing_fields():
    r = ev("---\nname: only-name\n---\nreal instructions here\nand more\n")
    assert not r.accepted and r.reason == "bad_frontmatter"


def test_reject_no_frontmatter():
    r = ev("# Title\n\njust prose, no frontmatter at all\nmore\n")
    assert not r.accepted and r.reason == "bad_frontmatter"


def test_reject_placeholder():
    body = ("---\nname: stub\ndescription: a stub skill\n---\n"
            "# Stub\n\nTODO\nTODO\nDescribe your skill here\n")
    r = ev(body)
    assert not r.accepted and r.reason == "placeholder"


def test_warning_name_differs_and_nonspec_key():
    text = GOOD.replace("name: pdf-helper", "name: PDF_Helper").replace(
        "license: MIT", "license: MIT\nrandomkey: 1")
    r = m.evaluate(["SKILL.md"], text, "pdf-helper")
    assert r.accepted
    assert "name_differs_from_folder" in r.spec_warnings
    assert "name_breaks_spec_chars" in r.spec_warnings
    assert any(w.startswith("nonspec_frontmatter_keys:") for w in r.spec_warnings)


def test_block_scalar_description_parses():
    text = ("---\nname: block\ndescription: >-\n  a multi-line description that\n"
            "  folds onto one line and is clearly non-empty\n---\n"
            "line1\nline2\nline3\nline4\nline5\n")
    r = m.evaluate(["SKILL.md"], text, "block")
    assert r.accepted and r.description.startswith("a multi-line")
