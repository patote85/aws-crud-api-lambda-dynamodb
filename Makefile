# Agent-friendly check: shortest path = correct path.
# No deploy. Lab CORS "*" in template.yaml is intentional for demo.
#
# make check = lint + typecheck + all tests (incl. HTTP contracts) + sam validate

.PHONY: check test lint typecheck validate

test:
	PYTHONPATH=. pytest tests/ -v

lint:
	ruff check src tests

typecheck:
	mypy tests

validate:
	sam validate --lint --template template.yaml

check: lint typecheck test validate
