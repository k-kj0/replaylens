"""Lets a coding agent run replays. pip install mcp
Run: python -m replaylens.mcp_server"""
import subprocess, sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("replaylens")

@mcp.tool()
def replay(runs_path: str, agent: str, prompt_path: str, rules_path: str = "", mock: bool = False) -> str:
    """Replay saved agent runs with a new prompt; returns the verdict lines."""
    cmd = [sys.executable, "-m", "replaylens", "replay", runs_path,
           "--agent", agent, "--prompt", prompt_path]
    if rules_path: cmd += ["--rules", rules_path]
    if mock: cmd.append("--mock")
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    lines = [l for l in (out.stdout + out.stderr).splitlines() if "Out of" in l or "VERDICT" in l or "rror" in l]
    return "\n".join(lines) or out.stdout[-2000:]

if __name__ == "__main__":
    mcp.run()
