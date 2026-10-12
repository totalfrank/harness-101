"""Reference solution. Used only to sanity-check the hidden test suite.

The agent never sees this file: its workspace is a temp dir outside the repo.
"""

import re
from decimal import Decimal

UNITS = [("w", 604_800_000), ("d", 86_400_000), ("h", 3_600_000),
         ("m", 60_000), ("s", 1_000), ("ms", 1)]
RANK = {u: i for i, (u, _) in enumerate(UNITS)}
SIZE = dict(UNITS)

NUM = r"(?:0|[1-9]\d*)(?:\.\d+)?"
COMPONENT = re.compile(rf"({NUM})(ms|w|d|h|m|s)")


def parse_duration(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("text must be str")
    s = text.strip()
    if s == "0":
        return 0
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if not s:
        raise ValueError("empty duration")

    total = Decimal(0)
    pos, last_rank, parts = 0, -1, []
    while pos < len(s):
        if parts and s[pos] == " ":
            pos += 1
        m = COMPONENT.match(s, pos)
        if not m:
            raise ValueError(f"invalid duration: {text!r}")
        num, unit = m.groups()
        if RANK[unit] <= last_rank:
            raise ValueError("units out of order or repeated")
        last_rank = RANK[unit]
        parts.append(num)
        total += Decimal(num) * SIZE[unit]
        pos = m.end()

    if any("." in p for p in parts[:-1]):
        raise ValueError("decimal only allowed in last component")
    if total != total.to_integral_value():
        raise ValueError("not a whole number of milliseconds")
    value = int(total)
    return -value if neg else value


def format_duration(ms: int) -> str:
    if isinstance(ms, bool) or not isinstance(ms, int):
        raise TypeError("ms must be int")
    if ms == 0:
        return "0s"
    sign, rest, out = ("-" if ms < 0 else ""), abs(ms), []
    for unit, size in UNITS:
        q, rest = divmod(rest, size)
        if q:
            out.append(f"{q}{unit}")
    return sign + "".join(out)
