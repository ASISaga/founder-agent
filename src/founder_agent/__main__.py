"""
Entry point for running FounderAgent as a FAS hosted container.

Executed by:
    CMD ["python", "-m", "founder_agent"]

Discovery chain:
1. Imports FounderAgent — triggers __init_subclass__ registration in base class
2. Calls purpose_driven_agent.hosting.run_server()
3. run_server() discovers FounderAgent via entry point or registry
4. Registers FounderAgent instance with AgentServer
5. AgentServer.serve() starts the FAS HTTP listener
"""
from __future__ import annotations

# Import FounderAgent first — this seeds the __init_subclass__ registry
# before run_server() calls _ensure_imports() and _discover_agent_class()
from founder_agent.agent import FounderAgent  # noqa: F401  (import for side effect)

from purpose_driven_agent.hosting import run_server

if __name__ == "__main__":
    run_server()
