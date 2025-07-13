# CI互換性ガイド

## 概要

このプロジェクトはPython 3.12を推奨していますが、CI環境ではPython 3.9+互換性を維持する必要があります。

## 🚨 重要：型注釈互換性

### 問題の背景
- Python 3.10+で導入された新しい型注釈構文は古いバージョンで動作しない
- CI失敗の主要原因となっている
- `TypeError: unsupported operand type(s) for |` エラーが発生

### 禁止事項 ❌

以下の型注釈は**使用禁止**です：

```python
# ❌ Union type syntax (Python 3.10+)
def get_user() -> User | None:
    pass

# ❌ Generic type syntax (Python 3.9+)
def get_items() -> dict[str, Any]:
    pass

def get_list() -> list[Model]:
    pass

def get_class() -> type[Model]:
    pass
```

### 推奨事項 ✅

以下の従来型注釈を使用してください：

```python
from typing import Any, Dict, List, Optional, Type, Union

# ✅ Optional型
def get_user() -> Optional[User]:
    pass

# ✅ 明示的なUnion型
def get_value() -> Union[str, int]:
    pass

# ✅ 従来のGeneric型
def get_items() -> Dict[str, Any]:
    pass

def get_list() -> List[Model]:
    pass

def get_class() -> Type[Model]:
    pass
```

## よくあるCIエラーと対処法

### 1. mypy TypeError
```
TypeError: unsupported operand type(s) for |: 'TypeVar' and 'NoneType'
```
**対処法**: `ModelType | None` → `Optional[ModelType]`

### 2. mypy 'type' object error
```
'type' object is not subscriptable
```
**対処法**: `dict[str, Any]` → `Dict[str, Any]`

### 3. Import type errors
```
Library stubs not installed for "yaml"
```
**対処法**: `# type: ignore[import-untyped]` を追加

## チェックリスト

PR作成前に以下を確認：

- [ ] `|` を使ったUnion型注釈がないか
- [ ] `dict[...]`, `list[...]` などの小文字Generic型がないか
- [ ] `from typing import` で必要な型をインポートしているか
- [ ] ローカルでmypyが通るか（`python3 -m mypy src/`）

## 自動チェック方法

```bash
# 禁止パターンの検索
grep -r " | " src/ --include="*.py" | grep -E "(-> .* \|)|(: .* \|)"
grep -r "dict\[" src/ --include="*.py"
grep -r "list\[" src/ --include="*.py"
grep -r "type\[" src/ --include="*.py"

# 修正後の確認
python3 -m mypy src/
```

## 参考情報

- [PEP 604 - Union Operators](https://peps.python.org/pep-0604/) (Python 3.10+)
- [PEP 585 - Generic Aliases](https://peps.python.org/pep-0585/) (Python 3.9+)
- [mypy documentation](https://mypy.readthedocs.io/)

---

**重要**: このガイドラインに従うことで、CI失敗を防ぎ、スムーズな開発を実現できます。