"""Ban self-report / fake-review fluff in README (agent-friendly L2-3)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")

# Phrases that previously oversold the repo as self-approved AI output.
_BANNED = [
    "Como este projeto foi criado",
    "Aplicação explícita das skills",
    "diálogo puro",
    "engenheiro sênior respeitaria",
]


def test_readme_has_no_self_report_fluff():
    offenders = [p for p in _BANNED if p in README]
    assert not offenders, f"README must not contain self-report fluff: {offenders}"
