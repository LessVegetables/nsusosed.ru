#!/usr/bin/env python3
"""Check the translation files: ru.js and en.js have the same keys, and every
key used in the HTML and JS exists. Run from anywhere:

    python3 frontend/tools/check_i18n.py

Exits with status 1 if something is missing.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY_RE = re.compile(r"^\s*'([a-zA-Z0-9_.]+)':", re.MULTILINE)
LITERAL_RE = re.compile(r"'([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)'")
DATA_I18N_RE = re.compile(r'data-i18n="([^"]+)"')
ATTR_RE = re.compile(r'(?:data-i18n-attr="|\'data-i18n-attr\': \')([^"\']+)')
# Plural forms are nested objects: skip their inner keys (one/few/many/other).
PLURAL_FORMS = {"one", "few", "many", "other"}


def dict_keys(path):
    return {k for k in KEY_RE.findall(path.read_text(encoding="utf-8")) if k not in PLURAL_FORMS}


def used_keys(namespaces):
    used = set()
    for path in list(ROOT.glob("*.html")) + list((ROOT / "js").rglob("*.js")):
        if path.parent.name == "i18n" or path.name == "i18n.js" or "mock" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        used.update(DATA_I18N_RE.findall(text))
        for attr in ATTR_RE.findall(text):
            used.update(pair.split(":", 1)[1].strip() for pair in attr.split(";") if ":" in pair)
        used.update(k for k in LITERAL_RE.findall(text) if k.split(".")[0] in namespaces)
    return used


def main():
    ru = dict_keys(ROOT / "js/i18n/ru.js")
    en = dict_keys(ROOT / "js/i18n/en.js")
    problems = []
    problems += [f"only in ru.js: {k}" for k in sorted(ru - en)]
    problems += [f"only in en.js: {k}" for k in sorted(en - ru)]
    namespaces = {k.split(".")[0] for k in ru | en}
    problems += [f"used but missing: {k}" for k in sorted(used_keys(namespaces) - (ru & en))]
    for p in problems:
        print(p)
    print(f"{len(ru)} keys, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
