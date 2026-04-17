# Extended style reference

## Type hints — common patterns

```python
# Basic
def greet(name: str) -> str:
    return f"Hello, {name}"

# Optional values
from typing import Optional
def find_user(user_id: int) -> Optional[str]:
    ...

# Lists and dicts
from typing import list, dict  # Python 3.9+
def process(items: list[str]) -> dict[str, int]:
    ...

# When a function returns nothing
def log_event(event: str) -> None:
    print(event)
```

## Docstring format (Google style)

```python
def calculate_total(prices: list[float], tax_rate: float = 0.24) -> float:
    """Calculate total price including tax.

    Args:
        prices: List of item prices in euros.
        tax_rate: Tax rate as a decimal. Defaults to Finnish VAT (0.24).

    Returns:
        Total price including tax, rounded to 2 decimal places.

    Raises:
        ValueError: If any price is negative.
    """
```

## Pathlib examples

```python
# Instead of os.path
from pathlib import Path

data_dir = Path("data") / "raw"
config_file = Path.home() / ".config" / "myapp" / "settings.json"

# Reading/writing
text = config_file.read_text(encoding="utf-8")
config_file.write_text(json.dumps(config), encoding="utf-8")

# Check existence
if data_dir.exists():
    files = list(data_dir.glob("*.csv"))
```