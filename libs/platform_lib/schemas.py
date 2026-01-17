import json
from pathlib import Path
from typing import Any, Dict


def load_schema(name: str) -> Dict[str, Any]:
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / f"{name}.json"
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
