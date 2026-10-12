"""Runs in a subprocess: imports the candidate module and scores it against CASES."""

import importlib.util
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from grader import CASES  # noqa: E402


def load(path: str):
    spec = importlib.util.spec_from_file_location("candidate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_case(mod, kind, arg):
    if kind == "parse":
        return mod.parse_duration(arg)
    if kind == "format":
        return mod.format_duration(arg)
    return mod.parse_duration(mod.format_duration(arg))


def main(path: str) -> dict:
    try:
        mod = load(path)
    except Exception:
        return {"passed": 0, "total": len(CASES), "failures": [],
                "error": traceback.format_exc(limit=2)}

    passed, failures = 0, []
    for kind, arg, expected in CASES:
        wants_error = expected in ("ValueError", "TypeError")
        try:
            got = run_case(mod, kind, arg)
            outcome = repr(got)
            ok = not wants_error and got == expected and type(got) is type(expected)
        except Exception as e:  # noqa: BLE001
            outcome = type(e).__name__
            ok = outcome == expected
        if ok:
            passed += 1
        else:
            want = expected if wants_error else repr(expected)
            failures.append(f"{kind}({arg!r}): expected {want}, got {outcome}")
    return {"passed": passed, "total": len(CASES), "failures": failures}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1])))
