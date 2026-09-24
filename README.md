# AWS CRUD API (API Gateway + Lambda + DynamoDB)

Minimal serverless CRUD for `Item` entities via **Amazon API Gateway (HTTP API)** and **AWS Lambda** (Python 3.12), persisted in **Amazon DynamoDB**.

See [CONTRIBUTING.md](CONTRIBUTING.md) for `make verify` / `make check`.

## Architecture

```
Client → API Gateway (HTTP API, prod) → Lambda (crud-items-api) → DynamoDB (Items, PK=id)
```

- Single Lambda routes by method + path.
- HTTP API (payload 2.0; also accepts REST v1 events).
- DynamoDB on-demand.

## Data model (Item)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | String | yes (auto) | UUID v4 |
| `name` | String | yes | non-empty |
| `description` | String | no | |
| `price` | Number | no | Decimal in DynamoDB |
| `createdAt` / `updatedAt` | String | yes (auto) | ISO-8601 UTC |

## Endpoints

Base (after deploy): `https://{api-id}.execute-api.{region}.amazonaws.com/prod`

| Method | Path | Success |
|--------|------|---------|
| `POST` | `/items` | `201` |
| `GET` | `/items` | `200` |
| `GET` | `/items/{id}` | `200` |
| `PUT` | `/items/{id}` | `200` |
| `DELETE` | `/items/{id}` | `204` |
| `OPTIONS` | any | `200` (CORS preflight) |

Create example:

```bash
curl -X POST https://{api-id}.execute-api.us-east-1.amazonaws.com/prod/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Notebook", "description": "lab", "price": 10.5}'
```

Errors: `400` invalid body / missing name; `404` not found; `500` internal.

## Prerequisites

- AWS account (CloudFormation, Lambda, API Gateway, DynamoDB, IAM)
- AWS CLI configured; SAM CLI >= 1.100
- Python 3.12+ for local tests

## Deploy

```bash
sam build
sam deploy --guided
# later: sam build && sam deploy
# destroy: sam delete --stack-name crud-api-demo
```

## Tests / verify / check

Uses **pytest** + **moto** (no real AWS).

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
make verify   # HTTP contracts via lambda_handler
make check    # lint + typecheck + all tests + sam validate (no deploy)
```

Details: [docs/make-check.md](docs/make-check.md).

## CI

GitHub Actions (`.github/workflows/ci.yml`) on every PR / push to `main`:

- **lint** — ruff + mypy (same as Makefile)
- **test** — `PYTHONPATH=. pytest tests/ -v`
- **verify** — `make verify`
- **validate** — `sam validate --lint` (no AWS credentials / no deploy)

## Project layout

```
aws-crud-api/
├── Makefile                 # make verify / make check
├── template.yaml            # SAM
├── src/app.py               # Lambda handler (CRUD)
├── tests/
│   ├── test_app.py          # unit tests (moto)
│   ├── test_http_contract.py
│   └── test_readme_no_self_report.py
├── events/
├── requirements.txt
├── CONTRIBUTING.md
└── README.md
```

## Design notes

1. One Lambda for all methods — small surface, fewer cold starts.
2. HTTP API over REST API — cheaper for this pattern.
3. `scan` for list — fine for demo; production should use Query + pagination.
4. `ConditionExpression` on update/delete — distinguish not-found.
5. `Decimal` for price — avoid float precision issues.
6. No web framework — easy to audit.
7. Lab CORS may still use `*` until the CORS-ban PR; production must lock origins.

## License

Demo code — use freely.
