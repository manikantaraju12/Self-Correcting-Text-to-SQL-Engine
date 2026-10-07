# Self-Correcting Text-to-SQL Engine

A simple Text-to-SQL service that converts natural language questions into SQL queries, executes them safely, detects errors, and automatically attempts to correct incorrect queries.

The system uses a controlled execution loop with SQL validation, error classification, and limited query repairs.

## Features

- Converts natural language questions into SQL.
- Allows only safe, read-only `SELECT` queries.
- Validates SQL using an AST-based guardrail.
- Detects syntax, schema, and semantic errors.
- Automatically repairs incorrect SQL queries.
- Supports up to **3 attempts** for each question.
- Uses PostgreSQL with Docker.
- Provides a FastAPI REST API.
- Includes an evaluation dataset and test suite.
- Supports an optional OpenAI-compatible LLM.

## Tech Stack

- **Python 3.10+**
- **FastAPI**
- **SQLAlchemy**
- **PostgreSQL**
- **SQLite** for local testing
- **SQLGlot** for SQL parsing and validation
- **Docker & Docker Compose**
- **Pytest**

## How It Works

```text
User Question
      ↓
SQL Generator
      ↓
SQL Validation
      ↓
Safe SELECT Query
      ↓
Database Execution
      ↓
Check Result
      ↓
Error Feedback → SQL Repair
```

The system generates a SQL query, validates it, and executes it only if it satisfies the safety rules. If an error occurs, the system identifies the error type and sends feedback to the SQL generator for correction.

## Database

The PostgreSQL database contains:

- `customers` – 150 records
- `orders` – 750 records
- `line_items` – 1,500 records

The database is initialized using:

```text
sql/init.sql
```

The schema is intentionally designed with some differences between tables. For example, `customers` uses `customer_id`, while `orders` references customers using `cust_id`.

## Run with Docker

Copy the environment file:

```powershell
copy .env.example .env
```

Then start the application:

```powershell
docker compose up --build -d
```

After the containers start, open:

```text
http://localhost:8000/docs
```

API health check:

```text
http://localhost:8000/health
```

## Query API

Send a POST request to:

```text
POST /api/query
```

Example request:

```json
{
  "question": "Show me all customers in New York"
}
```

Example response:

```json
{
  "status": "success",
  "final_sql": "SELECT customer_id, name, region FROM customers WHERE region = 'New York' ORDER BY customer_id",
  "results": [],
  "iterations": 1,
  "repair_history": []
}
```

The actual results depend on the database records.

## Error Handling

The system classifies failures into three types:

- **Syntax** – Invalid SQL or failed SQL parsing.
- **Schema** – Invalid tables, columns, or database execution errors.
- **Semantic** – Results that appear suspicious or do not match expected behavior.

Unsafe SQL statements are rejected before they reach the database.

The system allows a maximum of **3 attempts** to generate and repair a query.

## LLM Configuration

The project includes a built-in deterministic SQL generator, so it can run without an API key.

For an OpenAI-compatible LLM provider, configure:

```text
LLM_API_KEY=your_api_key
LLM_BASE_URL=your_base_url
LLM_MODEL=your_model
```

Do not commit `.env` files or real API credentials to GitHub.

## Local Development

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Set up the local SQLite database:

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///./local.db"
```

```powershell
python -c "from app.database import make_engine, seed_sqlite; seed_sqlite(make_engine('sqlite+pysqlite:///./local.db'))"
```

Start the application:

```powershell
python -m uvicorn app.main:app --reload
```

## Testing

Run the test suite:

```powershell
pytest -q
```

Run the evaluation:

```powershell
python scripts/evaluate.py
```

The evaluator tests different configurations and stores the evaluation results in:

```text
results/evaluation_metrics.json
```

Accuracy is measured by comparing the generated results with the expected results from the evaluation dataset.

## Project Structure

```text
Self-Correcting-Text-to-SQL-Engine/
│
├── app/
│   ├── generator.py
│   ├── guardrails.py
│   ├── service.py
│   └── main.py
│
├── data/
│   └── eval_set.json
│
├── sql/
│   └── init.sql
│
├── scripts/
│   └── evaluate.py
│
├── results/
│   └── evaluation_metrics.json
│
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Architecture

```text
                    ┌─────────────────┐
                    │  User Question  │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ SQL Generator   │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ SQL Guardrails  │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Database        │
                    │ Execution       │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Error / Result  │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Repair Feedback │
                    └────────┬────────┘
                             │
                             └──→ SQL Generator
```

## Conclusion

The **Self-Correcting Text-to-SQL Engine** provides a safe and reliable approach to converting natural language into SQL. Instead of simply generating a query and executing it, the system validates the SQL, detects failures, provides meaningful feedback, and automatically attempts to correct the query.

This project demonstrates how **LLMs, SQL validation, database execution, error handling, and automated self-correction** can be combined to build a practical and safer Text-to-SQL system.
