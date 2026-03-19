---
name: data-processing
description: 데이터 처리 및 변환 작업을 위한 스킬
---

## 데이터 처리 스킬

이 스킬은 데이터 처리 작업 시 참고할 패턴과 도구를 제공합니다.

### 사용 시점
- CSV, JSON 등 데이터 파일을 읽고 가공할 때
- 데이터 정제 및 변환 작업 시
- 대량 데이터 배치 처리 시

### 기본 패턴

```python
import pandas as pd

def load_and_process(filepath: str) -> pd.DataFrame:
    """데이터 파일을 로드하고 기본 전처리를 수행한다."""
    df = pd.read_csv(filepath)
    df = df.dropna()
    df.columns = [col.strip().lower() for col in df.columns]
    return df
```

### 참고
- `scripts/` 폴더에 재사용 가능한 헬퍼 스크립트가 있습니다.
- `examples/` 폴더에 사용 예제가 있습니다.
