import re
import string
from typing import Any, Tuple


ParseResult = Tuple[bool, Any, str]


_THINK_RE = re.compile(
    r'<(think|reasoning|scratchpad|thinking|analysis)\b[^>]*>.*?</\1>',
    re.DOTALL | re.IGNORECASE,
)
_CODE_FENCE_RE = re.compile(r'```[a-zA-Z]*\s*(.*?)```', re.DOTALL)
_STRAY_TOKEN_RE = re.compile(r'<(?:unused\d+|s|/s|bos|eos|pad)>', re.IGNORECASE)
_ANSWER_PREFIX_RE = re.compile(
    r'^\s*(?:final\s+)?(?:answer|response|reply)\s*[:=\-]\s*',
    re.IGNORECASE,
)
_MARKDOWN_EMPHASIS_RE = re.compile(
    r'\*{1,2}([^*\n]+?)\*{1,2}|_{1,2}([^_\n]+?)_{1,2}'
)


def _strip_outer_noise(raw: str) -> str:
    """Layer 1: remove reasoning blocks, code fences, stray special tokens, leading 'Answer:' labels, and outer quotes."""
    s = _THINK_RE.sub('', raw)
    s = _CODE_FENCE_RE.sub(r'\1', s)
    s = _STRAY_TOKEN_RE.sub('', s)
    s = s.strip()
    if len(s) >= 2 and s[0] in '"\'' and s[-1] == s[0]:
        s = s[1:-1].strip()
    s = _ANSWER_PREFIX_RE.sub('', s)
    return s.strip()


def _strip_emphasis(text: str) -> str:
    """Remove markdown bold/italic markers; used by bool/int parsers where the answer is a single token."""
    return _MARKDOWN_EMPHASIS_RE.sub(lambda m: m.group(1) or m.group(2), text)


def _strict_clean(s: str) -> str:
    """Strip surrounding whitespace and punctuation for exact-token comparison."""
    return s.strip().strip(string.punctuation + string.whitespace)


def _format_correction(raw: str, reason: str, format_instruction: str) -> str:
    """Build a user-role retry message that quotes the bad response and re-states the required format."""
    quoted = raw.strip()
    if len(quoted) > 200:
        quoted = quoted[:200] + '…'
    return f'Your previous response was: "{quoted}". {reason} {format_instruction}'


class BoolParser:
    """Parse a VLM response into True / False / unknown."""

    zero_value = False
    format_instruction = (
        "Reply with exactly one word: 'yes', 'no', or 'unknown'. "
        "Do not add explanations or punctuation."
    )

    _YES_STRICT = {'yes', 'y', 'true', 't'}
    _NO_STRICT = {'no', 'n', 'false', 'f'}
    _UNKNOWN_STRICT = {'unknown', 'idk', 'unsure', 'unclear'}

    _YES_LENIENT = {'yes', 'true'}
    _NO_LENIENT = {'no', 'false'}
    _UNKNOWN_LENIENT = {'unknown', 'idk'}

    _TOKEN_RE = re.compile(r"[a-z']+")

    def parse(self, raw: str) -> ParseResult:
        """Return (ok, value, reason). Strict single-token match first, then one-category extraction."""
        cleaned = _strip_emphasis(_strip_outer_noise(raw)).lower()

        strict = _strict_clean(cleaned)
        if strict in self._YES_STRICT:
            return True, True, ''
        if strict in self._NO_STRICT:
            return True, False, ''
        if strict in self._UNKNOWN_STRICT:
            return True, None, ''

        tokens = self._TOKEN_RE.findall(cleaned)
        has_yes = any(t in self._YES_LENIENT for t in tokens)
        has_no = any(t in self._NO_LENIENT for t in tokens)
        has_unknown = any(t in self._UNKNOWN_LENIENT for t in tokens)
        categories = sum([has_yes, has_no, has_unknown])
        if categories == 1:
            if has_yes:
                return True, True, ''
            if has_no:
                return True, False, ''
            return True, None, ''
        if categories > 1:
            return False, None, 'It contained conflicting yes/no/unknown signals.'
        return False, None, 'It did not contain yes, no, or unknown.'

    def format_correction(self, raw: str, reason: str) -> str:
        """Build the retry user message that quotes the bad response."""
        return _format_correction(raw, reason, self.format_instruction)


class IntParser:
    """Parse a VLM response into an integer or unknown."""

    zero_value = 0
    format_instruction = (
        "Reply with only an integer (no words, units, or punctuation), "
        "or the single word 'unknown' if you cannot determine a number."
    )

    _STRICT_INT_RE = re.compile(r'^-?\d+$')
    _ANY_INT_RE = re.compile(r'-?\d+')
    _UNKNOWN_RE = re.compile(r'\bunknown\b', re.IGNORECASE)

    def parse(self, raw: str) -> ParseResult:
        """Return (ok, value, reason). Strict single-integer match first, then one-integer extraction."""
        cleaned = _strip_emphasis(_strip_outer_noise(raw))

        strict = _strict_clean(cleaned).lower()
        if strict == 'unknown':
            return True, None, ''
        if self._STRICT_INT_RE.match(strict):
            return True, int(strict), ''

        integers = self._ANY_INT_RE.findall(cleaned)
        has_unknown = self._UNKNOWN_RE.search(cleaned) is not None
        if len(integers) == 1 and not has_unknown:
            return True, int(integers[0]), ''
        if not integers and has_unknown:
            return True, None, ''
        if len(integers) > 1:
            return False, None, f'It contained multiple numbers ({", ".join(integers)}).'
        return False, None, 'It did not contain an integer or the word unknown.'

    def format_correction(self, raw: str, reason: str) -> str:
        """Build the retry user message that quotes the bad response."""
        return _format_correction(raw, reason, self.format_instruction)


class StringParser:
    """Pass through free-form text. Empty responses retry; literal 'UNKNOWN' signals unknown."""

    zero_value = ''
    format_instruction = (
        "Respond concisely in plain text. "
        "If you genuinely cannot answer, reply with exactly: UNKNOWN."
    )

    def parse(self, raw: str) -> ParseResult:
        """Return (ok, value, reason). Empty → retry; 'UNKNOWN' → unknown; otherwise the cleaned text."""
        s = _strip_outer_noise(raw)
        if not s:
            return False, None, 'The response was empty.'
        if s.strip().lower() == 'unknown':
            return True, None, ''
        return True, s, ''

    def format_correction(self, raw: str, reason: str) -> str:
        """Build the retry user message that quotes the bad response."""
        return _format_correction(raw, reason, self.format_instruction)
