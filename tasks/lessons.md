# Lessons Learned

## Python 호환성
- Python 3.8에서는 `list[str]`, `dict[str, int]` 등 빌트인 제네릭 문법 사용 불가
- `from typing import List, Dict` 사용 필수
