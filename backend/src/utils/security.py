"""Security utilities."""

import re2 as re #use google re2 not normal re


def sanitize_search_query(query: str) -> str:
    """Sanitize search query to prevent injection attacks.

    Args:
        query: Raw search query from untrusted user input

    Returns:
        Sanitized query string (max 255 characters, dangerous chars removed)
    """
    # Remove potential SQL/HTML/path travelsal injection
    sanitized = re.sub(r"[<>\"';(){}\\]", "", query)

    # Trim whitespace and limit length
    sanitized = sanitized.strip()[:255]

    return sanitized
