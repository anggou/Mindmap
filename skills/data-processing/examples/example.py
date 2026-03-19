"""
데이터 처리 스킬 사용 예제
"""
from scripts.helpers import read_csv, save_json


def main():
    # CSV 읽기
    data = read_csv("input.csv")

    # 데이터 가공
    processed = [
        {"name": row["name"].strip(), "value": int(row["value"])}
        for row in data
    ]

    # JSON으로 저장
    save_json(processed, "output.json")
    print(f"처리 완료: {len(processed)}건")


if __name__ == "__main__":
    main()
