# make check / make verify (agent-friendly)

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # ruff + mypy
make verify  # HTTP contracts via lambda_handler (CRUD routes)
make check   # lint + typecheck + test + sam validate (no deploy)
```

- **`make verify`** = `tests/test_http_contract.py` (status/body contracts).
- **`make check`** = lint + typecheck + `pytest tests/` + `sam validate --lint`.

Lab CORS `*` in `template.yaml` / handler remains intentional for the SAM demo (tightened in a later PR).
