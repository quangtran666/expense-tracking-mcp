def format_vnd(amount: float) -> str:
    """
    Format VND amount with '.' as thousands separator, no decimals.
    """
    return f"{int(amount):,}".replace(",", ".")
