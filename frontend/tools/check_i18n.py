#!/usr/bin/env python3
"""Checks that can't wait for a browser: run before every commit and in CI.

  1. ru, en and zh dictionaries have exactly the same keys and the same {parameters};
  2. every key used in HTML (data-i18n, data-i18n-attr) or in JS (t('…'), i18n: '…') exists;
  3. no dictionary key is unused (keys built at run time are listed in DYNAMIC_PREFIXES);
  4. frontend/css/nsusosed.css is an exact copy of design/nsusosed.css;
  5. no inline styles or scripts in HTML (the CSP would block them).

    python3 frontend/tools/check_i18n.py
"""

from __future__ import annotations
import json
import re
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent
LANGS = ("ru", "en", "zh")
# Keys assembled in code, e.g. t(`error.${code}`).
DYNAMIC_PREFIXES = ("error.",)

ENTRY = re.compile(r'^\s*("(?:[^"\\]|\\.)+"):\s*("(?:[^"\\]|\\.)*"),\s*$')


def load(lang: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for n, line in enumerate((FRONTEND / "js" / "i18n" / f"{lang}.js").read_text(encoding="utf-8").splitlines(), 1):
        m = ENTRY.match(line)
        if m:
            key = json.loads(m.group(1))
            if key in entries:
                sys.exit(f"{lang}.js:{n}: duplicate key {key}")
            entries[key] = json.loads(m.group(2))
        elif line.strip() and not line.strip().startswith(("//", "export default {", "};")):
            sys.exit(f"{lang}.js:{n}: not a `\"key\": \"text\",` line: {line.strip()[:60]}")
    return entries


def used_keys() -> dict[str, str]:
    used: dict[str, str] = {}
    for path in sorted(FRONTEND.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for key in re.findall(r'data-i18n="([^"]+)"', text):
            used.setdefault(key, path.name)
        for attr in re.findall(r'data-i18n-attr="([^"]+)"', text):
            for pair in attr.split(";"):
                if ":" in pair:
                    used.setdefault(pair.split(":", 1)[1].strip(), path.name)
    for path in sorted((FRONTEND / "js").rglob("*.js")):
        if path.parent.name == "i18n":
            continue
        text = path.read_text(encoding="utf-8")
        for key in re.findall(r"""\bt\(\s*['"]([\w.]+)['"]""", text) + re.findall(r"""\bi18n:\s*['"]([\w.]+)['"]""", text):
            used.setdefault(key, path.name)
        for attr in re.findall(r"""['"]data-i18n-attr['"]:\s*['"]([^'"]+)['"]""", text):
            for pair in attr.split(";"):
                if ":" in pair:
                    used.setdefault(pair.split(":", 1)[1].strip(), path.name)
    return used


def main() -> int:
    problems: list[str] = []
    dicts = {lang: load(lang) for lang in LANGS}
    ru = dicts["ru"]

    for lang in LANGS[1:]:
        for key in ru.keys() - dicts[lang].keys():
            problems.append(f"{lang}.js: missing {key}")
        for key in dicts[lang].keys() - ru.keys():
            problems.append(f"{lang}.js: extra {key}")
        for key in ru.keys() & dicts[lang].keys():
            if set(re.findall(r"\{(\w+)\}", ru[key])) != set(re.findall(r"\{(\w+)\}", dicts[lang][key])):
                problems.append(f"{lang}.js: {key} has different {{parameters}} than ru")

    used = used_keys()
    for key, where in used.items():
        if key not in ru:
            problems.append(f"{where}: key {key} is not in the dictionaries")
    for key in ru:
        if key not in used and not key.startswith(DYNAMIC_PREFIXES):
            problems.append(f"ru.js: {key} is never used")

    design = FRONTEND.parent / "design" / "nsusosed.css"
    if design.is_file() and design.read_bytes() != (FRONTEND / "css" / "nsusosed.css").read_bytes():
        problems.append("css/nsusosed.css differs from design/nsusosed.css (edit design/, then copy)")

    for path in sorted(FRONTEND.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"<style\b|\sstyle=|\son\w+=\"", text):
            problems.append(f"{path.name}: inline style or event handler (blocked by the CSP)")
        for m in re.finditer(r"<script\b([^>]*)>", text):
            if "src=" not in m.group(1):
                problems.append(f"{path.name}: inline <script> (blocked by the CSP)")

    for p in problems:
        print("✕", p)
    print(f"{'FAILED' if problems else 'ok'}: {len(ru)} keys × {len(LANGS)} languages, {len(used)} used")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
