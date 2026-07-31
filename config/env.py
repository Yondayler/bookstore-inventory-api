"""Tiny helpers to read typed values out of environment variables."""
import json
import os
from decimal import Decimal, InvalidOperation
from typing import Dict, List

TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def env_str(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None or value.strip() == "" else value.strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = env_str(name).lower()
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    return default


def env_int(name: str, default: int) -> int:
    try:
        return int(env_str(name, str(default)))
    except ValueError:
        return default


def env_csv(name: str, default: List[str]) -> List[str]:
    raw = env_str(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_decimal_map(name: str, default: Dict[str, str]) -> Dict[str, Decimal]:
    """Read a JSON object of ``{"CURRENCY": "rate"}`` pairs.

    Falls back to ``default`` when the variable is missing or malformed, so a
    typo in the environment can never take the service down.
    """
    raw = env_str(name)
    source: Dict[str, str] = dict(default)
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                source = {str(k): str(v) for k, v in parsed.items()}
        except (json.JSONDecodeError, TypeError):
            pass

    rates: Dict[str, Decimal] = {}
    for currency, rate in source.items():
        try:
            rates[currency.upper()] = Decimal(str(rate))
        except (InvalidOperation, TypeError):
            continue
    return rates
