import re
from typing import Optional

SPAM_PATTERNS: tuple[str, ...] = (
    "buy now",
    "click here",
    "free money",
    "casino online",
    "win cash",
    "crypto giveaway",
    "work from home",
)

_LINK_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_REPEATED_CHAR_RE = re.compile(r"(.)\1{7,}")


def evaluate_comment_content(content: str) -> tuple[bool, Optional[str]]:
    links = _LINK_RE.findall(content)
    if len(links) > 2:
        return True, f"Exceso de enlaces detectados ({len(links)})."

    if _REPEATED_CHAR_RE.search(content):
        return True, "Repetición excesiva de caracteres detectada."

    lowered = content.lower()
    for pattern in SPAM_PATTERNS:
        if pattern in lowered:
            return True, f"Patrón antispam detectado: '{pattern}'."

    return False, None
