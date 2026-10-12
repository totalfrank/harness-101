"""Hidden test suite + grader.

The suite lives here, outside the agent's workspace, so the agent can't read it.
Grading runs in a subprocess so a broken/hanging solution can't take down the harness.
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

V, T = "ValueError", "TypeError"

# (function, argument, expected value or exception name)
CASES = [
    # basics
    ("parse", "1h", 3_600_000),
    ("parse", "1h30m", 5_400_000),
    ("parse", "1w", 604_800_000),
    ("parse", "2d", 172_800_000),
    ("parse", "45s", 45_000),
    ("parse", "250ms", 250),
    ("parse", "1m", 60_000),
    ("parse", "1m500ms", 60_500),           # 'm' vs 'ms' tokenisation
    ("parse", "1w1d1h1m1s1ms", 694_861_001),
    # whitespace
    ("parse", "1h 30m", 5_400_000),
    ("parse", "  1h30m  ", 5_400_000),
    ("parse", "1h  30m", V),
    ("parse", "", V),
    ("parse", "   ", V),
    # units
    ("parse", "1H", V),
    ("parse", "1M", V),
    ("parse", "1y", V),
    ("parse", "1min", V),
    # numbers
    ("parse", "0", 0),
    ("parse", "5", V),
    ("parse", "0s", 0),
    ("parse", "01h", V),
    ("parse", "0.5h", 1_800_000),
    ("parse", "00.5h", V),
    # decimals
    ("parse", "1.5h", 5_400_000),
    ("parse", "1h1.5m", 3_690_000),
    ("parse", "1.5h30m", V),
    ("parse", ".5h", V),
    ("parse", "1.h", V),
    ("parse", "0.0005s", V),
    ("parse", "1.5ms", V),
    # order
    ("parse", "30m1h", V),
    ("parse", "1h1h", V),
    ("parse", "1s1m", V),
    # sign
    ("parse", "-1h30m", -5_400_000),
    ("parse", "-0s", 0),
    ("parse", "+1h", V),
    ("parse", "--1h", V),
    ("parse", "1h-30m", V),
    # types
    ("parse", 3600, T),
    ("parse", None, T),
    # format
    ("format", 5_400_000, "1h30m"),
    ("format", 1_500, "1s500ms"),
    ("format", 694_861_001, "1w1d1h1m1s1ms"),
    ("format", 0, "0s"),
    ("format", -90_000, "-1m30s"),
    ("format", 1, "1ms"),
    ("format", 1_209_600_000, "2w"),
    ("format", True, T),
    ("format", 1.5, T),
    ("format", "100", T),
    # round trip
    ("roundtrip", 123_456_789, 123_456_789),
    ("roundtrip", -3_600_001, -3_600_001),
    ("roundtrip", 0, 0),
]


@dataclass
class Grade:
    passed: int
    total: int
    failures: list[str]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.passed == self.total

    def feedback(self, limit: int = 8) -> str:
        """Text the harness hands back to the model when it isn't done yet."""
        if self.error:
            return f"Your module could not be loaded:\n{self.error}"
        if self.ok:
            return f"All {self.total} hidden tests pass."
        lines = [f"{self.passed}/{self.total} hidden tests pass. Failing cases:"]
        lines += [f"  - {f}" for f in self.failures[:limit]]
        if len(self.failures) > limit:
            lines.append(f"  ... and {len(self.failures) - limit} more")
        return "\n".join(lines)


def grade(workspace: Path, timeout: float = 20) -> Grade:
    worker = Path(__file__).with_name("_grade_worker.py")
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(worker), str(workspace / "duration.py")],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return Grade(0, len(CASES), [], error="timed out")
    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return Grade(0, len(CASES), [], error=(proc.stderr or proc.stdout)[-1500:])
    return Grade(**data)
