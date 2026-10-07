from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.generator import RuleBasedGenerator, SQLGenerator
from app.guardrails import GuardrailViolation, validate_read_only_select


@dataclass
class QueryOutcome:
    status: str
    final_sql: str
    results: list[dict[str, Any]]
    iterations: int
    repair_history: list[dict[str, Any]]


def semantic_issue(question: str, results: list[dict[str, Any]]) -> str | None:
    if len(results) > 1000:
        return f"Semantic check failed: suspicious Cartesian product ({len(results)} rows exceeds 1000)."
    entity_terms = ("customer", "customers", "order", "orders", "line item", "line_items")
    asks_for_entities = any(term in question.lower() for term in entity_terms)
    aggregate_query = any(term in question.lower() for term in ("count", "average", "avg", "sum", "total", "revenue"))
    if asks_for_entities and not aggregate_query and not results:
        return "Semantic check failed: entity query unexpectedly returned zero rows."
    return None


class TextToSQLEngine:
    def __init__(
        self,
        database: Engine,
        generator: SQLGenerator | None = None,
        max_attempts: int = settings.max_attempts,
        enable_semantic: bool = True,
    ) -> None:
        self.database = database
        self.generator = generator or RuleBasedGenerator()
        self.max_attempts = min(3, max(1, max_attempts))
        self.enable_semantic = enable_semantic

    def query(self, question: str) -> QueryOutcome:
        history: list[dict[str, Any]] = []
        previous_sql: str | None = None
        failure_type: str | None = None
        error_message: str | None = None
        final_sql = ""
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw_sql = self.generator.generate(question, previous_sql, failure_type, error_message)
                final_sql = validate_read_only_select(raw_sql)
            except GuardrailViolation as error:
                failure_type, error_message = "syntax", str(error)
                history.append(self._history_item(attempt, failure_type, error_message))
                previous_sql = raw_sql if "raw_sql" in locals() else ""
                continue
            try:
                with self.database.connect() as connection:
                    results = [dict(row) for row in connection.execute(text(final_sql)).mappings().all()]
            except SQLAlchemyError as error:
                failure_type, error_message = "schema", str(error.orig if error.orig else error)
                history.append(self._history_item(attempt, failure_type, error_message))
                previous_sql = final_sql
                continue
            issue = semantic_issue(question, results) if self.enable_semantic else None
            if issue:
                failure_type, error_message = "semantic", issue
                history.append(self._history_item(attempt, failure_type, error_message))
                previous_sql = final_sql
                continue
            return QueryOutcome("success", final_sql, results, attempt, history)
        return QueryOutcome("failed", final_sql, [], self.max_attempts, history)

    @staticmethod
    def _history_item(attempt: int, failure_type: str, error_message: str) -> dict[str, Any]:
        return {"attempt": attempt, "failure_type": failure_type, "error_message": error_message}