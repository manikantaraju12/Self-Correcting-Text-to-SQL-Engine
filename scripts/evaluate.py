import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import make_engine, seed_sqlite
from app.generator import RuleBasedGenerator
from app.service import TextToSQLEngine


def rows_for(engine: Any, sql: str) -> list[tuple[Any, ...]]:
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(text(sql)).all()]


def run_configuration(
    dataset: list[dict[str, Any]],
    database: Any,
    max_attempts: int,
    enable_semantic: bool,
) -> tuple[float, float, int, int]:
    pipeline = TextToSQLEngine(
        database,
        generator=RuleBasedGenerator(),
        max_attempts=max_attempts,
        enable_semantic=enable_semantic,
    )
    correct = 0
    iterations = 0
    schema_repairs = 0
    semantic_repairs = 0
    for item in dataset:
        outcome = pipeline.query(item["question"])
        expected = rows_for(database, item["gold_sql"])
        actual = rows_for(database, outcome.final_sql) if outcome.final_sql else []
        correct += outcome.status == "success" and actual == expected
        iterations += outcome.iterations
        schema_repairs += sum(entry["failure_type"] == "schema" for entry in outcome.repair_history)
        semantic_repairs += sum(entry["failure_type"] == "semantic" for entry in outcome.repair_history)
    total = len(dataset)
    return (100.0 * correct / total, iterations / total, schema_repairs, semantic_repairs)


def main() -> None:
    dataset = json.loads((ROOT / "data" / "eval_set.json").read_text(encoding="utf-8"))
    database = make_engine("sqlite+pysqlite:///:memory:")
    seed_sqlite(database)
    zero_shot = run_configuration(dataset, database, 1, False)
    repair_only = run_configuration(dataset, database, 3, False)
    full_pipeline = run_configuration(dataset, database, 3, True)
    metrics = {
        "configurations": {
            "zero_shot": {"accuracy_pct": zero_shot[0], "avg_iterations": zero_shot[1]},
            "syntax_schema_repair_only": {
                "accuracy_pct": repair_only[0],
                "avg_iterations": repair_only[1],
                "total_schema_repairs": repair_only[2],
            },
            "full_pipeline": {
                "accuracy_pct": full_pipeline[0],
                "avg_iterations": full_pipeline[1],
                "total_semantic_repairs": full_pipeline[3],
            },
        }
    }
    output = ROOT / "results" / "evaluation_metrics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()