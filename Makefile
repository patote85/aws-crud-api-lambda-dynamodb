# Agent-friendly check: shortest path = correct path.
# No deploy. Lab CORS "*" in template.yaml is intentional for demo.
#
# make verify = prove-it-works (HTTP contracts via lambda_handler)
# make check  = lint + typecheck + all tests + sam validate

.PHONY: check test lint typecheck validate verify

verify:
	PYTHONPATH=. pytest tests/test_http_contract.py -v

test:
	PYTHONPATH=. pytest tests/ -v

lint:
	ruff check src tests

typecheck:
	mypy

validate:
	sam validate --lint --template template.yaml

check: lint typecheck test validate
