from collections import deque

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.database import seed_sqlite
from app.generator import RuleBasedGenerator
from app.guardrails import GuardrailViolation, validate_read_only_select
from app.main import app
from app.service import TextToSQLEngine, semantic_issue


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    seed_sqlite(engine)
    yield engine
    engine.dispose()


def test_read_only_guardrail_blocks_mutations():
    for statement in (
        "DROP TABLE customers",
        "DELETE FROM customers",
        "UPDATE customers SET name = 'x'",
        "INSERT INTO customers VALUES (999, 'x', NULL)",
        "ALTER TABLE customers ADD COLUMN x INTEGER",
        "TRUNCATE TABLE customers",
        "SELECT * INTO customer_backup FROM customers",
        "SELECT * FROM customers FOR UPDATE",
        "SELECT 1; DROP TABLE customers",
    ):
        with pytest.raises(GuardrailViolation):
            validate_read_only_select(statement)


def test_guardrail_failure_is_typed_and_never_executes(database):
    class DestructiveGenerator:
        def generate(self, *args, **kwargs):
            return "DROP TABLE customers"

    outcome = TextToSQLEngine(database, DestructiveGenerator()).query("delete all customers")
    assert outcome.status == "failed"
    assert outcome.iterations == 3
    assert outcome.repair_history[0]["failure_type"] == "syntax"
    assert "guardrail" in outcome.repair_history[0]["error_message"].lower()
    with database.connect() as connection:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM customers").scalar_one() == 150


def test_schema_error_is_logged_then_repaired(database):
    generated = deque(
        [
            "SELECT customers.name FROM customers JOIN orders ON customers.customer_id = orders.customer_id",
            "SELECT customers.name FROM customers JOIN orders ON customers.customer_id = orders.cust_id",
        ]
    )

    class RepairGenerator:
        def generate(self, *args, **kwargs):
            return generated.popleft()

    outcome = TextToSQLEngine(database, RepairGenerator()).query("Join customers to orders and show names")
    assert outcome.status == "success"
    assert outcome.iterations == 2
    assert outcome.repair_history[0]["failure_type"] == "schema"
    assert "customer_id" in outcome.repair_history[0]["error_message"]


def test_cartesian_and_empty_entity_heuristics():
    assert "Cartesian" in semantic_issue("show customers", [{"id": index} for index in range(1001)])
    assert "zero rows" in semantic_issue("show customers", [])
    assert semantic_issue("count customers", []) is None


def test_impossible_request_stops_after_three_attempts(database):
    outcome = TextToSQLEngine(database, RuleBasedGenerator()).query(
        "Calculate the quantum entanglement ratio of the customer names"
    )
    assert outcome.status == "failed"
    assert outcome.iterations == 3
    assert all(entry["failure_type"] == "semantic" for entry in outcome.repair_history)


def test_zero_lifetime_value_trap_records_semantic_repairs(database):
    outcome = TextToSQLEngine(database, RuleBasedGenerator()).query(
        "Who are the customers with zero lifetime value?"
    )
    assert outcome.status == "failed"
    assert outcome.iterations == 3
    assert all(entry["failure_type"] == "semantic" for entry in outcome.repair_history)


def test_required_question_returns_typed_response(database, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "pipeline", TextToSQLEngine(database, RuleBasedGenerator()))
    response = TestClient(app).post("/api/query", json={"question": "Show me all customers in New York"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert isinstance(payload["final_sql"], str)
    assert isinstance(payload["results"], list)
    assert isinstance(payload["iterations"], int)
    assert isinstance(payload["repair_history"], list)
