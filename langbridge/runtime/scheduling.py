import re

_DATASET_SYNC_CADENCE_PATTERN = re.compile(r"^(?P<value>[1-9][0-9]*)(?P<unit>[smhd])$")
_DATASET_SYNC_CADENCE_MULTIPLIERS = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 24 * 60 * 60,
}
_DATASET_SYNC_CADENCE_EXAMPLE = "30s, 5m, 1h, or 1d"


def normalize_dataset_sync_cadence(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if _DATASET_SYNC_CADENCE_PATTERN.fullmatch(normalized) is None:
        raise ValueError(
            f"Unsupported dataset sync cadence '{value}'. "
            f"Use an interval shorthand like {_DATASET_SYNC_CADENCE_EXAMPLE}."
        )
    return normalized


def dataset_sync_cadence_to_seconds(value: str) -> int:
    normalized = normalize_dataset_sync_cadence(value)
    if normalized is None:
        raise ValueError("Dataset sync cadence is required.")
    match = _DATASET_SYNC_CADENCE_PATTERN.fullmatch(normalized)
    if match is None:
        raise ValueError(
            f"Unsupported dataset sync cadence '{value}'. "
            f"Use an interval shorthand like {_DATASET_SYNC_CADENCE_EXAMPLE}."
        )
    interval_value = int(match.group("value"))
    interval_unit = match.group("unit")
    return interval_value * _DATASET_SYNC_CADENCE_MULTIPLIERS[interval_unit]


__all__ = [
    "dataset_sync_cadence_to_seconds",
    "normalize_dataset_sync_cadence",
]
