# harness-101

A talk demo: **the same model, on the same task, goes from failing to passing because of the harness around it, not because of a better model.**

## The task

`task/TASK.md` describes a duration parser and formatter (`"1h30m"` ⇄ `5400000` ms) with about 20 small rules that are easy to miss: `m` vs `ms`, decimals only in the last component, no leading zeros, strict unit order, `bool` is not an `int`, and so on.

`harness/grader.py` holds **54 hidden tests**. The agent works in a temp dir that contains only `TASK.md` and a stub, so it never sees the tests. A typical sloppy first attempt scores about 36/54.

## The ladder (`harness/levels.py`)

| Level | Harness | The idea |
|---|---|---|
| L0 | single shot, no tools | "just ask the LLM" |
| L1 | agent loop with Read/Write/Edit/Bash | the model can act, but **it** decides when it's done |
| L2 | + **verify gate** (Stop hook) | the harness runs the tests and **refuses to let the agent stop** until they pass, feeding back the failures |
| L3 | + **fast feedback** (PostToolUse hook) | the score is injected after every edit, so the loop gets tighter |

The key code is about 20 lines, in `verify_gate()`:

```python
async def on_stop(_input, _tool_use_id, _ctx):
    g = grade(ws)
    if g.ok:
        return {}                                  # allowed to stop
    return {"decision": "block",                   # not allowed to stop
            "reason": "You are not done yet. " + g.feedback()}
```

## Running

```bash
pip install -r requirements.txt
export WEAK_MODEL=...      # model id
export STRONG_MODEL=...

# one live run, with the transcript streamed (good for stage)
python -m harness.run --model $WEAK_MODEL --level 2

# the benchmark slide: pass rates over N trials
python -m harness.run --model $WEAK_MODEL --model $STRONG_MODEL \
    --level 0 1 2 3 --trials 5 --jobs 4 --quiet
```

The output ends in a scoreboard with solved/trials, average tests passed, turns, cost and time per (model, level).

## Calibrating the weak model (important)

The demo only works if the weak model **sometimes fails at L0/L1 and can recover from feedback**. Current small Claude models are already strong enough to solve this task at L1. To get a real gap:

- **Use a small open model behind an Anthropic-compatible proxy** (recommended). For example, run LiteLLM in front of a 1–7B model served by Ollama or vLLM, then set `ANTHROPIC_BASE_URL` to the proxy and pass the proxy's model alias as `--model`. The SDK is unchanged.
- Or make the task harder by adding rules to `TASK.md` and cases to `CASES` (and to `reference_solution.py`, then check it still scores 100%).

To sanity-check the grader without any model:

```bash
cp harness/reference_solution.py /tmp/x/duration.py
python -c "from pathlib import Path; from harness.grader import grade; print(grade(Path('/tmp/x')))"
```
