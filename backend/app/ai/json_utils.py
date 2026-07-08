import re

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def strip_code_fence(raw: str) -> str:
    """Extract JSON from a ```json ... ``` fence if the model wrapped its reply in one,
    despite being told not to (some models, e.g. Gemini, do this anyway)."""
    text = raw.strip()
    match = _CODE_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text
