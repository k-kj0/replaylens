"""REPLAY: re-run every recorded input with a new model and/or prompt."""
import time
from concurrent.futures import ThreadPoolExecutor

from .recorder import make_row


def replay_runs(runs, agent_fn, model, system_prompt, prompt_version="new",
                price_in=None, price_out=None, workers=4):
    raw = getattr(agent_fn, "__wrapped__", agent_fn)  # don't re-record replays

    def one(old):
        start = time.perf_counter()
        error = None
        try:
            res = raw(old["input"], model=model, system_prompt=system_prompt)
        except Exception as exc:
            res = {"output": "", "tool_calls": [], "tokens_in": 0, "tokens_out": 0}
            error = f"{type(exc).__name__}: {exc}"
        ms = int((time.perf_counter() - start) * 1000)
        # no new price given -> assume the same $/token rate that was recorded
        p_in = old.get("price_in", 0.0) if price_in is None else price_in
        p_out = old.get("price_out", 0.0) if price_out is None else price_out
        return old, make_row(old["input"], res, model, prompt_version, ms, p_in, p_out, error)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        return list(ex.map(one, runs))
