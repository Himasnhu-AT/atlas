"""Coercion and what it costs: a worked solution."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

CURRENCY = "$€£"

TRUE_WORDS = {"true", "t", "yes", "y", "1"}
FALSE_WORDS = {"false", "f", "no", "n", "0"}


def to_int(raw: str | None) -> tuple[int | None, bool]:
    if raw is None:
        return None, False
    text = raw.strip()
    if text == "":
        return None, False
    try:
        # int() rejects "2.7" on its own, which is what we want: a fractional
        # count is a field that does not mean what the caller assumed.
        return int(text), True
    except ValueError:
        return None, False


def to_decimal(raw: str | None) -> tuple[Decimal | None, bool]:
    if raw is None:
        return None, False
    text = raw.strip()
    if text == "":
        return None, False

    if text and text[0] in CURRENCY:
        text = text[1:].strip()
    text = text.replace(",", "")

    if not text or (text[0] in "+-" and len(text) == 1):
        return None, False

    try:
        return Decimal(text), True
    except InvalidOperation:
        return None, False


def to_date(raw: str | None, day_first: bool = True) -> tuple[str | None, bool]:
    if raw is None:
        return None, False
    text = raw.strip()
    if text == "":
        return None, False

    # A timestamp keeps only its date part.
    if "T" in text:
        text = text.split("T", 1)[0]

    if "-" in text:
        parts = text.split("-")
        if len(parts) != 3:
            return None, False
        year, month, day = parts
    elif "/" in text:
        parts = text.split("/")
        if len(parts) != 3:
            return None, False
        if day_first:
            day, month, year = parts
        else:
            month, day, year = parts
    else:
        return None, False

    try:
        value = date(int(year), int(month), int(day))
    except ValueError:
        # Covers both non-numeric parts and dates that do not exist.
        return None, False

    return value.isoformat(), True


def to_bool(raw: str | None) -> tuple[bool | None, bool]:
    if raw is None:
        return None, False
    text = raw.strip().lower()
    if text in TRUE_WORDS:
        return True, True
    if text in FALSE_WORDS:
        return False, True
    return None, False
