# API Serverless CRUD com API Gateway + Lambda + DynamoDB

API REST completa de **CRUD** (Create, Read, Update, Delete) para entidades `Item`, exposta via **Amazon API Gateway (HTTP API)** e implementada em **AWS Lambda** (Python 3.12). Todos os dados são persistidos no **Amazon DynamoDB**.

Projeto intencionalmente minimalista, focado em clareza, facilidade de deploy e testes unitários isolados (sem depender de AWS real).

---

## Como este projeto foi criado

Este repositório foi gerado **inteiramente por conversa** com o agente Grok (xAI), **sem uso de IDE**, editor local ou geração de scaffolding por CLI.

Fluxo real:

1. Pedido em linguagem natural: “crie uma API acessada via AWS API Gateway que faça um CRUD e grave tudo no DynamoDB…”
2. O agente aplicou duas skills explícitas de disciplina:
   - **karpathy-code-implementation** → simplicidade máxima, diffs cirúrgicos, zero over-engineering, verificação antes de apresentar.
   - **ai-agents-architecture** → análise se um *agent* era necessário. Conclusão: **não**. O fluxo é 100% determinístico (method + path → função). Adicionar loop de agente, planning ou multi-agent seria anti-padrão e violaria a regra “Is an agent actually required?”.
3. Código + testes + template SAM + README foram escritos e revisados em turnos sucessivos de conversa.
4. Publicação neste repositório via tools conectadas do próprio agente.

Resultado: um projeto que um engenheiro sênior respeitaria sem reescrever, nascido de diálogo puro.

---

## Arquitetura

```
Cliente (curl / Postman / frontend)
        │
        ▼
┌───────────────────────┐
│  API Gateway          │  HTTP API (pay-per-request)
│  (prod stage)         │  CORS habilitado
└──────────┬────────────┘
           │  proxy integration
           ▼
┌───────────────────────┐
│  Lambda               │  Python 3.12
│  crud-items-api       │  128 MB / 10s timeout
│  (uma única função)   │  roteamento por method + path
└──────────┬────────────┘
           │  IAM role com DynamoDBCrudPolicy
           ▼
┌───────────────────────┐
│  DynamoDB             │  Table: Items
│  (on-demand)          │  PK: id (String)
└───────────────────────┘
```

- **Uma única Lambda** recebe todas as requisições e faz o roteamento interno (simples e barato).
- **HTTP API** (API Gateway v2) em vez de REST API clássica → menor custo e latência.
- **Pay-per-request** no DynamoDB → zero custo quando ocioso.
- Suporta tanto payload format 1.0 (REST) quanto 2.0 (HTTP API).

---

## Modelo de dados (Item)

| Campo        | Tipo     | Obrigatório | Descrição                          |
|--------------|----------|-------------|------------------------------------|
| `id`         | String   | Sim (auto)  | UUID v4 gerado pelo backend        |
| `name`       | String   | Sim         | Nome do item                       |
| `description`| String   | Não         | Descrição livre                    |
| `price`      | Number   | Não         | Preço (Decimal no DynamoDB)        |
| `createdAt`  | String   | Sim (auto)  | ISO-8601 UTC                       |
| `updatedAt`  | String   | Sim (auto)  | ISO-8601 UTC (atualizado no PUT)   |

---

## Endpoints

Base URL (após deploy):  
`https://{api-id}.execute-api.{region}.amazonaws.com/prod`

| Método   | Path            | Descrição                     | Status de sucesso |
|----------|-----------------|-------------------------------|-------------------|
| `POST`   | `/items`        | Cria um novo item             | `201 Created`     |
| `GET`    | `/items`        | Lista todos os itens          | `200 OK`          |
| `GET`    | `/items/{id}`   | Busca um item pelo ID         | `200 OK`          |
| `PUT`    | `/items/{id}`   | Atualiza campos do item       | `200 OK`          |
| `DELETE` | `/items/{id}`   | Remove o item                 | `204 No Content`  |
| `OPTIONS`| qualquer        | Preflight CORS                | `200 OK`          |

### Exemplos de request / response

#### 1. Criar item

```bash
curl -X POST https://{api-id}.execute-api.us-east-1.amazonaws.com/prod/items \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Notebook Gamer",
    "description": "RTX 4070, 32GB RAM",
    "price": 7899.90
  }'
```

**Resposta 201:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Notebook Gamer",
  "description": "RTX 4070, 32GB RAM",
  "price": 7899.9,
  "createdAt": "2026-07-23T15:12:34.567890+00:00",
  "updatedAt": "2026-07-23T15:12:34.567890+00:00"
}
```

#### 2. Listar todos

```bash
curl https://{api-id}.execute-api.us-east-1.amazonaws.com/prod/items
```

**Resposta 200:**
```json
{
  "items": [ ... ],
  "count": 2
}
```

#### 3. Buscar por ID

```bash
curl https://{api-id}.execute-api.us-east-1.amazonaws.com/prod/items/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

#### 4. Atualizar (parcial)

```bash
curl -X PUT https://{api-id}.execute-api.us-east-1.amazonaws.com/prod/items/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Notebook Gamer Pro",
    "price": 7499.00
  }'
```

Campos permitidos no body: `name`, `description`, `price`.  
Campos não enviados permanecem inalterados. `updatedAt` é sempre atualizado.

#### 5. Deletar

```bash
curl -X DELETE https://{api-id}.execute-api.us-east-1.amazonaws.com/prod/items/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Resposta:** `204 No Content` (body vazio).

### Códigos de erro comuns

| Status | Situação                                      |
|--------|-----------------------------------------------|
| 400    | Body inválido / campo `name` ausente          |
| 404    | Item não encontrado (GET/PUT/DELETE)          |
| 500    | Erro interno (DynamoDB, etc.)                 |

---

## Pré-requisitos

- Conta AWS com permissões para CloudFormation, Lambda, API Gateway, DynamoDB e IAM
- [AWS CLI](https://aws.amazon.com/cli/) configurado (`aws configure`)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) ≥ 1.100
- Python 3.12+ (para testes locais)
- Docker (opcional, para `sam local`)

---

## Deploy

```bash
# 1. Clone / entre na pasta do projeto
cd aws-crud-api

# 2. Build (empacota a Lambda)
sam build

# 3. Deploy guiado (primeira vez)
sam deploy --guided

# Responda:
#   Stack Name: crud-api-demo
#   AWS Region: us-east-1 (ou a sua)
#   Confirm changes: Y
#   Allow SAM CLI IAM role creation: Y
#   Disable rollback: N
#   Save arguments to config: Y
```

Após o deploy, o SAM imprime o **ApiEndpoint** nos Outputs. Use esse valor como base URL.

Para deploys subsequentes:

```bash
sam build && sam deploy
```

### Destruir a stack (quando não precisar mais)

```bash
sam delete --stack-name crud-api-demo
```

---

## Testes unitários

Os testes usam **pytest** + **moto** (mock completo do DynamoDB).  
Nenhum recurso real da AWS é tocado.

Atalho agent-friendly: `make check` (ver [docs/make-check.md](docs/make-check.md)). Lab CORS `*` no template é intencional.

### Instalação e execução

```bash
# Na raiz do projeto
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

pip install -r requirements.txt

# Rode os testes
PYTHONPATH=. pytest tests/ -v
```

### O que é coberto

| Cenário                              | Arquivo / função                  |
|--------------------------------------|-----------------------------------|
| Criação com sucesso + validação de campos | `test_create_item_success`       |
| Criação sem `name` (400)             | `test_create_item_missing_name`   |
| Body vazio / JSON inválido           | `test_create_item_empty_body` etc.|
| Listagem vazia e com dados           | `test_list_items_*`               |
| Get por ID (sucesso + 404)           | `test_get_item_*`                 |
| Update parcial + ConditionExpression | `test_update_item_success`        |
| Update de item inexistente (404)     | `test_update_item_not_found`      |
| Delete (204 + confirmação de remoção)| `test_delete_item_success`        |
| Rota desconhecida + OPTIONS CORS     | `test_unknown_route`, `test_options_cors` |
| Compatibilidade payload v1 (REST)    | `test_v1_payload_format`          |

Todos os testes passam em < 2 segundos e são determinísticos.

---

## CI

GitHub Actions (`.github/workflows/ci.yml`) roda **lint** (ruff + mypy), **pytest + moto**, e **sam validate --lint** em Python 3.12 em todo push na `main` e em todo pull request.

- Sem credenciais AWS no runner (DynamoDB mockado pelo moto).
- Dependências: `pip install -r requirements.txt` (com cache pip).
- Localmente: os mesmos comandos da seção [Testes unitários](#testes-unitários).
- Job `validate`: `sam validate --lint` no `template.yaml` (setup-sam; sem credenciais AWS / sem deploy).


---

## Testes locais com SAM

Você pode invocar a Lambda localmente sem deploy:

```bash
# Build primeiro
sam build

# Invocar com evento de exemplo
sam local invoke CrudFunction -e events/create_item.json

# Ou subir a API completa localmente (precisa Docker)
sam local start-api
# Depois:
curl -X POST http://127.0.0.1:3000/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Teste local", "price": 10}'
```

---

## Estrutura do projeto

```
aws-crud-api/
├── template.yaml          # SAM / CloudFormation
├── src/
│   └── app.py             # Handler Lambda (todo o CRUD)
├── tests/
│   └── test_app.py        # Testes unitários com moto
├── events/
│   ├── create_item.json
│   └── get_item.json
├── requirements.txt
└── README.md              # Este arquivo
```

---

## Decisões de design (e por quê)

1. **Uma única Lambda** em vez de uma por método → menos recursos, menos cold starts, código coeso.
2. **HTTP API** em vez de REST API → custo ~70% menor e latência menor para este padrão.
3. **Scan** no list → aceitável para demo e tabelas pequenas. Em produção real troque por GSI + Query + paginação.
4. **ConditionExpression** no update/delete → distingue “não existe” de “erro genérico” sem race condition.
5. **Decimal** para preço → evita problemas de precisão de float no DynamoDB.
6. **Sem framework** (Flask, FastAPI, Powertools) → superfície mínima, fácil de auditar e manter.
7. **CORS liberado** (`*`) → facilita testes de frontend. Em produção restrinja a origem real.

### Aplicação explícita das skills

**ai-agents-architecture**  
Antes de escrever qualquer linha, o agente respondeu à pergunta-chave da skill: “Is an agent actually required?”.  
Resposta: **não**. O problema tem fluxo fixo e determinístico (HTTP method + path → operação).  
Portanto foi mantido como *predefined workflow* puro. Qualquer loop de agente, planning step ou multi-agent teria sido rejeitado por aumentar latência, custo e superfície de falha sem ganho mensurável.

**karpathy-code-implementation**  
- Simplicity First: zero abstração prematura, zero framework, código mínimo que resolve o pedido.
- Surgical changes: cada alteração (ex.: validação de `price`) foi o menor diff possível.
- Goal-driven + self-critique: testes unitários cobrindo happy path + edge cases foram escritos antes de considerar o trabalho pronto.
- Read-before-write e verificação empírica (py_compile + estrutura de testes) precederam a publicação.

---

## Próximos passos possíveis (não implementados de propósito)

- Autenticação (Cognito JWT ou API Key)
- Paginação real no list (LastEvaluatedKey)
- Validação mais rica (Pydantic ou jsonschema)
- CloudWatch Alarms + X-Ray
- CI/CD com GitHub Actions + `sam deploy`
- Soft delete + TTL

---

## Licença

Código de demonstração — use livremente.
