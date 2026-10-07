# Self-Correcting Text-to-SQL Engine

A small, runnable Text-to-SQL service that treats SQL generation as a guarded execution loop: parse the candidate AST, execute only a single read-only `SELECT`, classify failures, and feed typed execution feedback into up to two repairs. Semantic checks catch suspiciously large results and unexpected empty entity queries.

## Run with Docker

Copy `.env.example` to `.env` and adjust credentials if needed, then run:

```powershell
docker compose up --build -d
```

PostgreSQL initializes `customers` (150 rows), `orders` (750 rows), and `line_items` (1,500 rows) from `sql/init.sql`. Compose waits for PostgreSQL's health check before starting the API. Visit `http://localhost:8000/docs` or check `http://localhost:8000/health`.

The schema is intentionally imperfect for learning and evaluation: customers use `customer_id`, orders reference them through `cust_id`, customer regions can be `NULL`, orders store denormalized totals, and line items contain quantity and unit-price details. When reasoning about spend, choose the requested grain to avoid counting an order total once per line item.

## Query API

`POST /api/query` accepts `{"question":"Show me all customers in New York"}` and returns:

```json
{
  "status": "success",
  "final_sql": "SELECT customer_id, name, region FROM customers WHERE region = 'New York' ORDER BY customer_id",
  "results": [],
  "iterations": 1,
  "repair_history": []
}
```

The response's `results` depend on the seeded database. History failures are typed as `syntax` (AST guardrail or parse), `schema` (database execution), or `semantic` (heuristic). Unsafe statements are rejected before database execution. The loop is clamped to at most three attempts.

## SQL generator configuration

Without an API key, a deterministic built-in generator supports the documented examples, local tests, and evaluation corpus. Set `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` to enable an OpenAI-compatible chat completions provider. The prompt supplies the schema and the previous SQL plus typed error feedback on repair attempts. Do not commit `.env` or real credentials.

## Local development

Python 3.10+ is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "sqlite+pysqlite:///./local.db"
python -c "from app.database import make_engine, seed_sqlite; seed_sqlite(make_engine('sqlite+pysqlite:///./local.db'))"
python -m uvicorn app.main:app --reload
```

For tests and evaluation, no external database is needed:

```powershell
pytest -q
python scripts/evaluate.py
```

The evaluator runs zero-shot, syntax/schema-repair-only, and full-pipeline configurations against `data/eval_set.json`, then writes `results/evaluation_metrics.json`. Accuracy is exact ordered-row equality against each gold query on the reproducibly seeded SQLite fixture; iteration count is the mean over questions.

## Architecture

```text
Question -> SQL generator -> sqlglot single-SELECT guard -> SQLAlchemy execution
    ^                                                        |
    |---- typed syntax / schema / semantic feedback ----------|
```

`app/generator.py` owns generation, `app/guardrails.py` owns AST policy, and `app/service.py` owns execution feedback, heuristics, and the hard attempt limit. `sql/init.sql` is the canonical PostgreSQL fixture.