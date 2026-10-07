import sqlglot
from sqlglot import exp


class GuardrailViolation(ValueError):
    pass


def validate_read_only_select(sql: str) -> str:
    try:
        statements = [statement for statement in sqlglot.parse(sql) if statement is not None]
    except sqlglot.errors.ParseError as error:
        raise GuardrailViolation(f"SQL parse error: {error}") from error
    if len(statements) != 1:
        raise GuardrailViolation("Guardrail violation: exactly one SQL statement is allowed.")
    statement = statements[0]
    if (
        not isinstance(statement, (exp.Select, exp.Subquery))
        or statement.args.get("into")
        or statement.args.get("locks")
        or any(
        isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.TruncateTable))
        for node in statement.walk()
        )
    ):
        raise GuardrailViolation("Guardrail violation: only read-only SELECT queries are allowed.")
    return statement.sql(dialect="postgres")