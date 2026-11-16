"""Small validation helpers shared by request models."""

from __future__ import annotations


def clean_string_list(
    values: list[str],
    *,
    max_items: int,
    max_length: int,
    dedupe: bool = True,
) -> list[str]:
    """Trim, drop blanks, optionally deduplicate, and enforce limits."""
    cleaned: list[str] = []
    seen: set[str] = set()

    for value in values:
        item = value.strip()
        if not item:
            continue
        if len(item) > max_length:
            raise ValueError(f"Each item must be at most {max_length} characters.")

        key = item.casefold()
        if dedupe and key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    if len(cleaned) > max_items:
        raise ValueError(f"At most {max_items} items are allowed.")
    return cleaned
