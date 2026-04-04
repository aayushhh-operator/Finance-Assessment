def escape_like_pattern(value: str) -> str:
    """Escape SQL LIKE special characters so user input stays literal."""

    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
