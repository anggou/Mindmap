"""
데이터 처리 헬퍼 유틸리티
"""
import csv
import json
from pathlib import Path
from typing import Any


def read_csv(filepath: str) -> list[dict[str, Any]]:
    """CSV 파일을 딕셔너리 리스트로 읽는다."""
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_json(filepath: str) -> Any:
    """JSON 파일을 읽는다."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, filepath: str) -> None:
    """데이터를 JSON 파일로 저장한다."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
