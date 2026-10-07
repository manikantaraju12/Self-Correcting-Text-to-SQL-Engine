import json
import re
from typing import Protocol
from urllib.request import Request, urlopen

from app.config import settings


class SQLGenerator(Protocol):
    def generate(
        self,
        question: str,
        previous_sql: str | None = None,
        failure_type: str | None = None,
        error_message: str | None = None,
    ) -> str: ...


class OpenAICompatibleGenerator:
    def generate(
        self,
        question: str,
        previous_sql: str | None = None,
        failure_type: str | None = None,
        error_message: str | None = None,
    ) -> str:
        schema = (
            "customers(customer_id, name, region nullable); "
            "orders(id, cust_id -> customers.customer_id, total_amount); "
            "line_items(id, order_id -> orders.id, qty, unit_price)."
        )
        repair = ""
        if previous_sql:
            repair = (
                f"\nPrevious SQL: {previous_sql}\nFailure type: {failure_type}"
                f"\nFailure: {error_message}\nCorrect the query using this feedback."
            )
        payload = {
            "model": settings.llm_model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return exactly one read-only PostgreSQL SELECT statement, with no markdown. "
                        f"Use only this schema: {schema} Prefer explicit joins and qualified columns."
                    ),
                },
                {"role": "user", "content": question + repair},
            ],
        }
        request = Request(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            content = json.loads(response.read())["choices"][0]["message"]["content"].strip()
        return re.sub(r"^```(?:sql)?\s*|\s*```$", "", content, flags=re.IGNORECASE).strip()


class RuleBasedGenerator:
    """Credential-free generator for common schema questions and reproducible tests."""

    def generate(
        self,
        question: str,
        previous_sql: str | None = None,
        failure_type: str | None = None,
        error_message: str | None = None,
    ) -> str:
        text = question.lower().strip().rstrip("?.!")
        if previous_sql and failure_type in {"syntax", "schema", "semantic"}:
            return self._correct(text, previous_sql, failure_type)
        if any(term in text for term in ("quantum", "entanglement", "impossible")):
            return "SELECT customer_id, name FROM customers WHERE 1 = 0"
        if "cartesian" in text or "cross join" in text:
            return "SELECT customers.customer_id, orders.id FROM customers CROSS JOIN orders"
        if "zero lifetime value" in text or "no lifetime value" in text:
            return (
                "SELECT customers.customer_id, customers.name FROM customers "
                "WHERE NOT EXISTS (SELECT 1 FROM orders WHERE orders.cust_id = customers.customer_id)"
            )
        if "new york" in text:
            return "SELECT customer_id, name, region FROM customers WHERE region = 'New York' ORDER BY customer_id"
        for region in ("california", "texas", "florida", "washington"):
            if region in text:
                return (
                    "SELECT customer_id, name, region FROM customers WHERE region = "
                    f"'{region.title()}' ORDER BY customer_id"
                )
        if "null" in text and "region" in text:
            return "SELECT customer_id, name FROM customers WHERE region IS NULL ORDER BY customer_id"
        if ("count" in text or "how many" in text) and "customer" in text and "region" in text:
            return "SELECT region, COUNT(*) AS customer_count FROM customers GROUP BY region ORDER BY region"
        if ("count" in text or "how many" in text) and "order" in text and "customer" in text:
            return "SELECT cust_id, COUNT(*) AS order_count FROM orders GROUP BY cust_id ORDER BY cust_id"
        if ("count" in text or "how many" in text) and "order" in text:
            return "SELECT COUNT(*) AS order_count FROM orders"
        if ("count" in text or "how many" in text) and "line item" in text:
            return "SELECT COUNT(*) AS line_item_count FROM line_items"
        if ("count" in text or "how many" in text) and "customer" in text:
            return "SELECT COUNT(*) AS customer_count FROM customers"
        if ("average" in text or "avg" in text or "mean" in text) and "order" in text:
            return "SELECT AVG(total_amount) AS average_order_amount FROM orders"
        if ("total" in text or "sum" in text or "revenue" in text) and "order" in text:
            return "SELECT SUM(total_amount) AS total_revenue FROM orders"
        if "line item" in text or "line_item" in text:
            if "first 100" in text or "top 100" in text:
                return "SELECT id, order_id, qty, unit_price FROM line_items ORDER BY id LIMIT 100"
            return "SELECT id, order_id, qty, unit_price FROM line_items ORDER BY id"
        if "join" in text or ("customer" in text and "order" in text):
            return (
                "SELECT customers.name, orders.id AS order_id, orders.total_amount "
                "FROM customers JOIN orders ON customers.customer_id = orders.cust_id "
                "ORDER BY orders.id"
            )
        if "order" in text:
            return "SELECT id, cust_id, total_amount FROM orders ORDER BY id"
        if "name" in text and "customer" in text:
            return "SELECT name FROM customers ORDER BY customer_id"
        if "customer" in text:
            return "SELECT customer_id, name, region FROM customers ORDER BY customer_id"
        return "SELECT customer_id, name FROM customers WHERE 1 = 0"

    @staticmethod
    def _correct(question: str, previous_sql: str, failure_type: str) -> str:
        if any(term in question for term in ("quantum", "entanglement", "impossible")):
            return previous_sql
        if failure_type == "semantic" and "1 = 0" in previous_sql:
            return "SELECT customer_id, name FROM customers ORDER BY customer_id"
        if failure_type == "semantic" and "NOT EXISTS" in previous_sql.upper():
            return previous_sql
        if failure_type == "semantic" and "CROSS JOIN" in previous_sql.upper():
            return "SELECT customers.customer_id, orders.id FROM customers JOIN orders ON customers.customer_id = orders.cust_id"
        if "customer" in question and "order" in question:
            return (
                "SELECT customers.name, orders.id AS order_id, orders.total_amount "
                "FROM customers JOIN orders ON customers.customer_id = orders.cust_id "
                "ORDER BY orders.id"
            )
        return "SELECT customer_id, name, region FROM customers ORDER BY customer_id"