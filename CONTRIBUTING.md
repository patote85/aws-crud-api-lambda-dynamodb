# Contributing

## Local checks

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # ruff + mypy
# sam CLI required for make check validate target
make verify   # HTTP contracts (prove-it-works)
make check    # lint + typecheck + all tests + sam validate (no deploy)
```

## Pull requests

1. Branch from `main`.
2. Keep PRs small and focused.
3. CI must be green (`lint`, `test`, `verify`, `validate`) before merge.
4. No deploy from CI; production deploy requires CAB.
