"""The harness ladder. Same model, same task, same prompt. Only the harness changes.

  L0  single shot     : one completion, no tools. Whatever comes back is graded.
  L1  agent loop      : file + shell tools. The model decides when it is done.
  L2  verify gate     : a Stop hook runs the hidden tests and refuses to let the
                        agent finish until they pass, feeding back the failures.
  L3  fast feedback   : L2 + a PostToolUse hook that grades after every edit, so
                        the model sees the score as it works, not only at the end.
"""

import re
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from .grader import Grade, grade

TASK_DIR = Path(__file__).resolve().parent.parent / "task"
SPEC = (TASK_DIR / "TASK.md").read_text()

PROMPT = "Implement duration.py so that it satisfies the spec in TASK.md."

LEVELS = {
    0: "single shot",
    1: "agent loop",
    2: "+ verify gate",
    3: "+ fast feedback",
}

MAX_GATE_BLOCKS = 6  # how many times L2/L3 may refuse "I'm done"


@dataclass
class RunResult:
    level: int
    model: str
    grade: Grade
    turns: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0
    gate_blocks: int = 0
    log: list[str] = field(default_factory=list)


class Logger:
    def __init__(self, result: RunResult, verbose: bool):
        self.result, self.verbose = result, verbose

    def __call__(self, line: str):
        self.result.log.append(line)
        if self.verbose:
            print(line, flush=True)


def make_workspace() -> Path:
    """Fresh temp dir with only the spec and the stub. The hidden tests stay behind."""
    ws = Path(tempfile.mkdtemp(prefix="harness-ws-"))
    shutil.copy(TASK_DIR / "TASK.md", ws)
    shutil.copy(TASK_DIR / "duration.py", ws)
    return ws


def base_options(model: str, ws: Path) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=model,
        cwd=str(ws),
        setting_sources=[],             # don't inherit the user's CLAUDE.md / settings
        tools=["Read", "Write", "Edit", "Bash"],
        allowed_tools=["Read", "Write", "Edit", "Bash"],
        permission_mode="acceptEdits",
        max_turns=40,
    )


def describe_tool(block: ToolUseBlock) -> str:
    inp = block.input
    if block.name == "Bash":
        return f"$ {inp.get('command', '')[:90]}"
    return f"{block.name} {Path(inp.get('file_path', '')).name}"


async def drive(prompt: str, options: ClaudeAgentOptions, result: RunResult, log: Logger) -> str:
    """Run the agent loop, stream a compact transcript, return the final text."""
    final_text = ""
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    log(f"    🔧 {describe_tool(block)}")
                elif isinstance(block, TextBlock) and block.text.strip():
                    final_text = block.text
                    first = block.text.strip().splitlines()[0][:100]
                    log(f"    💬 {first}")
        elif isinstance(msg, ResultMessage):
            result.turns = msg.num_turns
            result.cost_usd = msg.total_cost_usd or 0.0
    return final_text


# --------------------------------------------------------------------------- L0
async def level0(model: str, ws: Path, result: RunResult, log: Logger):
    options = ClaudeAgentOptions(
        model=model, cwd=str(ws), setting_sources=[], tools=[], max_turns=1,
    )
    prompt = (
        f"{SPEC}\n\n{PROMPT} Reply with the complete contents of duration.py "
        "in a single ```python code block."
    )
    text = await drive(prompt, options, result, log)
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.S)
    if blocks:
        (ws / "duration.py").write_text(max(blocks, key=len))
    else:
        log("    ⚠️  no code block in reply")


# --------------------------------------------------------------------------- L1
async def level1(model: str, ws: Path, result: RunResult, log: Logger):
    await drive(PROMPT, base_options(model, ws), result, log)


# --------------------------------------------------------------------------- L2 / L3
def verify_gate(ws: Path, result: RunResult, log: Logger):
    """Stop hook: the agent may only stop once the hidden tests pass."""

    async def on_stop(_input, _tool_use_id, _ctx):
        g = grade(ws)
        if g.ok:
            log(f"    ✅ gate: {g.passed}/{g.total} pass, agent may stop")
            return {}
        if result.gate_blocks >= MAX_GATE_BLOCKS:
            log(f"    ⛔ gate: {g.passed}/{g.total}, out of retries, giving up")
            return {}
        result.gate_blocks += 1
        log(f"    🛑 gate: {g.passed}/{g.total}, blocking stop #{result.gate_blocks}")
        return {
            "decision": "block",
            "reason": "You are not done yet. " + g.feedback()
            + "\nRe-read the relevant rules in TASK.md, fix duration.py, and try again.",
        }

    return HookMatcher(hooks=[on_stop])


def edit_feedback(ws: Path, log: Logger):
    """PostToolUse hook: after each edit, tell the model its current score."""

    async def after_edit(_input, _tool_use_id, _ctx):
        g = grade(ws)
        log(f"    📊 after edit: {g.passed}/{g.total}")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "[harness] " + g.feedback(limit=5),
            }
        }

    return HookMatcher(matcher="Write|Edit", hooks=[after_edit])


async def level2(model: str, ws: Path, result: RunResult, log: Logger):
    options = base_options(model, ws)
    options.hooks = {"Stop": [verify_gate(ws, result, log)]}
    await drive(PROMPT, options, result, log)


async def level3(model: str, ws: Path, result: RunResult, log: Logger):
    options = base_options(model, ws)
    options.hooks = {
        "Stop": [verify_gate(ws, result, log)],
        "PostToolUse": [edit_feedback(ws, log)],
    }
    await drive(PROMPT, options, result, log)


RUNNERS = {0: level0, 1: level1, 2: level2, 3: level3}


async def run_level(level: int, model: str, verbose: bool = True) -> RunResult:
    result = RunResult(level, model, grade=Grade(0, 0, []))
    log = Logger(result, verbose)
    ws = make_workspace()
    start = time.monotonic()
    try:
        await RUNNERS[level](model, ws, result, log)
    except Exception as e:  # noqa: BLE001 - a crashed run is just a failed run
        log(f"    💥 {type(e).__name__}: {e}")
    result.seconds = time.monotonic() - start
    result.grade = grade(ws)  # final, independent grading
    shutil.rmtree(ws, ignore_errors=True)
    return result
