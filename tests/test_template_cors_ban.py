"""Mechanical ban: SAM template and src must not use CORS origin wildcard *."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Literal "*" / '*' as a string (CORS AllowOrigins / Allow-Origin wildcard).
_STAR_STRING = re.compile(r"""(['"])\*\1""")
# YAML bare list item: - *
_STAR_YAML_ITEM = re.compile(r"^\s*-\s*\*\s*$")


def _scan(paths: list[Path]) -> list[str]:
    offenders: list[str] = []
    for path in paths:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if _STAR_STRING.search(code) or _STAR_YAML_ITEM.match(code):
                offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
    return offenders


def test_no_cors_allow_origins_star_in_template_or_src():
    paths = [ROOT / "template.yaml"] + sorted((ROOT / "src").rglob("*.py"))
    offenders = _scan(paths)
    assert not offenders, (
        "Must not use CORS AllowOrigins / Access-Control-Allow-Origin '*'. Offenders:\n"
        + "\n".join(offenders)
    )
