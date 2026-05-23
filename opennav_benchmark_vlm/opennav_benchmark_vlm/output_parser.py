import re
import string
from typing import Any, Tuple


ParseResult = Tuple[bool, Any]


def _clean(raw: str) -> str:
    """Strip surrounding whitespace and punctuation so token comparisons are robust to trailing periods, quotes, etc."""
    return raw.strip().strip(string.punctuation + string.whitespace)


class BoolParser:
    """Parse a VLM response into True / False / unknown."""

    zero_value = False
    format_instruction = (
        "Reply with exactly one word: 'yes', 'no', or 'unknown'. "
        "Do not add explanations or punctuation."
    )
    correction_hint = (
        "That response was not in the required format. "
        "Reply with only one of: yes, no, unknown."
    )

    _YES = {'yes', 'y', 'true', 't', '1'}
    _NO = {'no', 'n', 'false', 'f', '0'}
    _UNKNOWN = {'unknown', 'idk', 'unsure', 'maybe', 'cannot tell', "can't tell", 'unclear'}

    def parse(self, raw: str) -> ParseResult:
        """Return (ok, value): ok=False triggers retry; value=None means VLM said 'unknown'."""
        s = _clean(raw).lower()
        if s in self._YES:
            return True, True
        if s in self._NO:
            return True, False
        if s in self._UNKNOWN:
            return True, None
        return False, None


class IntParser:
    """Parse a VLM response into an integer or unknown."""

    zero_value = 0
    format_instruction = (
        "Reply with only an integer (no words, units, or punctuation), "
        "or the single word 'unknown' if you cannot determine a number."
    )
    correction_hint = (
        "That response was not in the required format. "
        "Reply with only an integer, or the word 'unknown'."
    )

    _INT_RE = re.compile(r'^-?\d+$')

    def parse(self, raw: str) -> ParseResult:
        """Return (ok, value): ok=False triggers retry; value=None means VLM said 'unknown'."""
        s = _clean(raw).lower()
        if s == 'unknown':
            return True, None
        if self._INT_RE.match(s):
            return True, int(s)
        return False, None


class StringParser:
    """Pass through arbitrary free-form text; empty responses retry, literal 'UNKNOWN' signals unknown."""

    zero_value = ''
    format_instruction = (
        "Respond concisely in plain text. "
        "If you genuinely cannot answer, reply with exactly: UNKNOWN."
    )
    correction_hint = (
        "Provide a concise plain-text answer, or reply UNKNOWN if you cannot."
    )

    def parse(self, raw: str) -> ParseResult:
        """Return (ok, value): empty response → retry; 'UNKNOWN' → value=None; otherwise the stripped text."""
        s = raw.strip()
        if not s:
            return False, None
        if s.lower() == 'unknown':
            return True, None
        return True, s
