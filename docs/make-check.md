# make check (agent-friendly)

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # ruff + mypy
make check   # lint + typecheck + test + sam validate (no deploy)
```

Lab CORS `*` in `template.yaml` / handler remains intentional for the SAM demo.
