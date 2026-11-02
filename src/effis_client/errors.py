import re

_SERVICE_EXCEPTION = re.compile(
    r'<ServiceException(?=[\s>])(?:\s+code="(?P<code>[^"]*)")?[^>]*>(?P<text>.*?)</ServiceException>',
    re.DOTALL,
)


class EffisError(Exception):
    """EFFIS answered, but not with the data asked for.

    MapServer reports most errors as HTTP 200 with an XML body, so a status
    check alone never sees them.
    """


def describe(body: bytes | str) -> str:
    """The code and message of a MapServer exception report, else the body's start."""
    text = body if isinstance(body, str) else body.decode("utf-8", "replace")
    match = _SERVICE_EXCEPTION.search(text)
    if match is None:
        return repr(text[:200])
    code = match.group("code")
    message = " ".join(match.group("text").split())
    return f"{code}: {message}" if code else message
