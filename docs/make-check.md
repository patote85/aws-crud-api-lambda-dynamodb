# make check / make verify (agent-friendly)

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # ruff + mypy
make verify  # HTTP contracts via lambda_handler (CRUD routes)
make check   # lint + typecheck + test + sam validate (no deploy)
```

- **`make verify`** = `tests/test_http_contract.py` (status/body contracts).
- **`make check`** = lint + typecheck + `pytest tests/` + `sam validate --lint`.

CORS lab origins: `http://localhost:3000` and `http://127.0.0.1:3000` (no `*`). Ban: `tests/test_template_cors_ban.py`.
