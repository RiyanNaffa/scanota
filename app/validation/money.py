"""app/validation/money.py – Rupiah currency parsing.

parse_rupiah(value) -> int

Accepts:
    int       : returned as-is after checking non-negative
    float     : accepted only when the value is integral (no fractional cents)
    str       : many Indonesian/spreadsheet formats, e.g.:
                "1.250.000"  "1,250,000"  "Rp 25.000"
                "25000"      " 25.000,- " "Rp1.250"

Rules for string parsing:
  * Strip "Rp", whitespace, dashes at end ("-")
  * If the cleaned string contains a comma followed by exactly 3 digits at the
    end (e.g. "1,000") treat the comma as a thousands separator and remove it.
  * If the cleaned string ends with ",00" treat it as a decimal part of zero.
  * Dots followed by exactly 3 digits are thousands separators.
  * Remaining commas are decimal separators; accept only when fractional part
    is 00 (i.e. whole Rupiah).
  * Reject empty, negative, and non-numeric input.
"""

from __future__ import annotations

import re


def parse_rupiah(value: object) -> int:
    """Parse a Rupiah value to an integer.

    Args:
        value: int, float, or str representation of a Rupiah amount.

    Returns:
        Non-negative integer (Rupiah amount).

    Raises:
        ValueError: on empty, negative, non-numeric, or fractional input.
    """
    if isinstance(value, bool):
        raise ValueError(f"Invalid Rupiah value: {value!r}")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"Negative Rupiah value: {value}")
        return value
    if isinstance(value, float):
        if value < 0:
            raise ValueError(f"Negative Rupiah value: {value}")
        if value != int(value):
            raise ValueError(f"Non-integral float Rupiah value: {value}")
        return int(value)
    if not isinstance(value, str):
        raise ValueError(f"Unsupported type for Rupiah value: {type(value)}")

    # Remove Rp prefix (case-insensitive), spaces, trailing dashes/spaces
    cleaned = re.sub(r"(?i)^rp\s*", "", value.strip())
    # Strip trailing dashes and comma-dash (e.g. ",-" in Indonesian style)
    cleaned = re.sub(r"[,.-]+$", "", cleaned).strip()

    if not cleaned:
        raise ValueError("Empty Rupiah string")

    # Handle trailing decimal part ",00" or ".00"
    cleaned = re.sub(r"[,.]00$", "", cleaned)

    # Detect format:
    # "1.250.000" – dots as thousands separators
    # "1,250,000" – commas as thousands separators
    # "1.250"     – ambiguous: if dot group is exactly 3 digits → thousands
    # "25000"     – no separators

    # Count dots and commas
    n_dots = cleaned.count(".")
    n_commas = cleaned.count(",")

    if n_dots == 0 and n_commas == 0:
        # Plain integer string
        result_str = cleaned
    elif n_dots > 0 and n_commas == 0:
        # Only dots: all must be thousands separators (groups of 3)
        # e.g. "1.250.000" or "25.000"
        parts = cleaned.split(".")
        # First part can be any length; subsequent parts must be exactly 3 digits
        if all(p.isdigit() for p in parts) and all(len(p) == 3 for p in parts[1:]):
            result_str = "".join(parts)
        else:
            raise ValueError(f"Unrecognized Rupiah format (mixed dot usage): {value!r}")
    elif n_commas > 0 and n_dots == 0:
        # Only commas: treat as thousands separators (e.g. "1,250,000")
        parts = cleaned.split(",")
        if all(p.isdigit() for p in parts) and all(len(p) == 3 for p in parts[1:]):
            result_str = "".join(parts)
        else:
            raise ValueError(f"Unrecognized Rupiah format (comma usage): {value!r}")
    else:
        # Mixed: dot and comma
        # Typical: "1.250.000,00" or "1,250,000.00" (decimal at end)
        # We already stripped ",00" / ".00" above; if comma comes before dot,
        # dot is decimal – but Rupiah has no cents so raise.
        # If dot comes before comma (Indonesian style), dot is thousands, comma is decimal.
        last_dot = cleaned.rfind(".")
        last_comma = cleaned.rfind(",")
        if last_dot > last_comma:
            # dot is last separator → decimal dot (e.g. "25000.00" already stripped above)
            raise ValueError(f"Non-integral Rupiah value: {value!r}")
        else:
            # comma is last → decimal comma (Indonesian style "1.250,50")
            # after stripping ",00" above, only whole values remain
            raise ValueError(f"Non-integral Rupiah value (decimal comma): {value!r}")

    if not result_str.isdigit():
        raise ValueError(f"Non-numeric Rupiah value: {value!r}")

    result = int(result_str)
    if result < 0:
        raise ValueError(f"Negative Rupiah value: {value!r}")
    return result
