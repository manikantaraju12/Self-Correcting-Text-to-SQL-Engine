import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_eval_set_has_thirty_valid_cases():
    data = json.loads((ROOT / "data" / "eval_set.json").read_text(encoding="utf-8"))
    assert len(data) >= 30
    assert all({"id", "question", "difficulty", "gold_sql"} <= item.keys() for item in data)
    assert all(item["difficulty"] in {"easy", "medium", "hard"} for item in data)
