# Founder Agent — Foundry FAS Wiring Requirements

**Repository:** `ASISaga/founder-agent`  
**Target audience:** Claude Sonnet 4.6 inside GitHub Copilot coding agent  
**Purpose:** Wire `aos/founder-agent-fas` into Azure AI Foundry as the hosted container backing the `founder-mvp` agent in the `boardroom-mvp` workflow. Implement routing in code. Register `FounderAgent` as the FAS-hosted class.

---

## Context

The `ASISaga/purpose-driven-agent` refactor (see companion document) adds the generic FAS hosting infrastructure to the base class. This document covers what is **specific to the founder-agent repo** — the `FounderAgent` class wiring, its routing implementation, and the Foundry registration.

### Package layout (confirmed)

```
ASISaga/founder-agent/
├── src/
│   └── Founder/               ← Python package (PascalCase, intentional)
│       ├── __init__.py        ← exports FounderAgent
│       ├── agent.py           ← FounderAgent class (to be modified)
│       ├── inference_role.py  ← (exists, had syntax error — verify fixed)
│       └── trainer.py         ← (exists, had syntax error — verify fixed)
├── Dockerfile.founder-agent   ← exists, deployed, builds fine
├── pyproject.toml             ← exists, needs entry point addition
└── .github/workflows/
    ├── build-founder-agent.yml
    └── update-base-image.yml
```

### Inheritance chain at runtime (inside the FAS container)

```
PurposeDrivenAgent   (from /app/purpose_driven_agent/agent.pyc)
  └── LeadershipAgent    (from /app/leadership_agent/agent.pyc)
        └── BusinessAgent    (from /app/BusinessAgent/agent.pyc)
              └── FounderAgent     (from /app/Founder/agent.pyc)
```

Import path in the container: `from Founder import FounderAgent` — package name is `Founder` (PascalCase, matching `src/Founder/`).

### What the boardroom-mvp workflow expects

The Foundry workflow invokes `founder-mvp` via `InvokeAzureAgent`. The agent must:

1. Receive an input message containing the conversation context
2. Call the LLM (via `agent-framework-foundry` — already wired in the base class)
3. Return a response that ends with exactly one of: `[ROUTE:CFO]`, `[ROUTE:CMO]`, `[COMPLETE]`
4. Never return `[HANDBACK]` (that is for specialist agents only)

The routing detection in `boardroom-mvp` is a dual-guard:
```
condition: =Lower(Local.RouteTo) = "cfo" Or !IsBlank(Find("[ROUTE:CFO]", Upper(Local.LatestMessage)))
```

The text-scan fallback (`Find(...)`) means routing works even if the structured `routeTo` output binding is not populated by Foundry. The code-level enforcement in `FounderAgent` guarantees the tag is always present in the message text.

---

## Decision: How `FounderAgent` is discovered by FAS

**Decision made:** `pyproject.toml` entry point + `__init_subclass__` fallback (both mechanisms, implemented in the base class).

In `ASISaga/founder-agent/pyproject.toml`, declare:

```toml
[project.entry-points."agent_framework.hosted_agents"]
default = "Founder.agent:FounderAgent"
```

When `agent-framework-foundry-hosting` starts, it reads this entry point and loads `FounderAgent`. If the package is not installed (running from `PYTHONPATH=/app`), the `__init_subclass__` registry in `PurposeDrivenAgent` catches `FounderAgent` when `Founder` is imported during the registry seeding step in `purpose_driven_agent.hosting._ensure_imports()`.

**No environment variable needed.** The entry point is the canonical declaration. The registry is the reliable fallback.

---

## Decision: Routing Implementation in Code

**Decision made:** `FounderAgent` overrides `get_routing_tags()`, `get_default_routing_tag()`, and wraps the response pipeline to call `enforce_routing_tag()`.

### Routing logic design

`FounderAgent` is an orchestrator. After every LLM response:

1. `enforce_routing_tag()` (inherited from `PurposeDrivenAgent`) scans the response tail for a tag
2. If a valid orchestrator tag is found (`[ROUTE:CFO]`, `[ROUTE:CMO]`, `[COMPLETE]`) — return unchanged
3. If `[HANDBACK]` is found (invalid for an orchestrator) — replace with `[COMPLETE]`
4. If no tag is found — append `[COMPLETE]` (conservative default: when in doubt, complete rather than loop forever)

The LLM still generates the routing signal through its reasoning — the `enforce_routing_tag` just ensures the structural contract is never broken regardless of LLM compliance.

---

## Required Changes to `src/Founder/agent.py`

Modify the existing `FounderAgent` class. Do not replace it — add/update only the listed methods.

### Prerequisite imports

Add at the top of `agent.py` if not already present:

```python
from __future__ import annotations
import logging
from typing import ClassVar
```

### `FounderAgent` class changes

```python
# These are the additions/overrides to make inside the existing FounderAgent class.
# Preserve all existing __init__ logic, attributes, and methods.

from purpose_driven_agent.routing_mixin import RoutingMixin

class FounderAgent(RoutingMixin, BusinessAgent):  # or whatever the current inheritance is
    """
    Founder orchestrator agent for the ASI Saga Boardroom.

    Role: Orchestrator — receives conversation context, reasons about it,
    and routes to the appropriate specialist (CFO or CMO) or signals completion.

    Routing protocol (enforced in code, not LLM instructions):
      [ROUTE:CFO]  — topic involves financials, costs, revenue, risk, investment
      [ROUTE:CMO]  — topic involves marketing, positioning, brand, go-to-market
      [COMPLETE]   — deliberation fully resolved

    This class is discovered by agent-framework-foundry-hosting via:
      1. pyproject.toml entry point: agent_framework.hosted_agents:default
      2. PurposeDrivenAgent.__init_subclass__ registry (fallback)
    """

    # ── Routing role declaration ───────────────────────────────────────────
    # Inherited from RoutingMixin. Explicit here for clarity.
    ROUTING_ROLE: ClassVar[str] = "orchestrator"

    # ── Persona identity ──────────────────────────────────────────────────
    # Used in system prompt construction and logging
    PERSONA_NAME: ClassVar[str] = "Paul Graham"
    BOARDROOM_PURPOSE: ClassVar[str] = "Orchestrating the Genesis of ASI"

    def get_routing_tags(self) -> frozenset[str]:
        """Orchestrators may only emit ROUTE:CFO, ROUTE:CMO, or COMPLETE."""
        return frozenset({"[ROUTE:CFO]", "[ROUTE:CMO]", "[COMPLETE]"})

    def get_default_routing_tag(self) -> str:
        """
        Default tag when the LLM produces no routing signal.

        '[COMPLETE]' is the conservative default for an orchestrator:
        if we cannot determine what to route to, end the deliberation
        rather than routing blindly or looping forever.
        """
        return "[COMPLETE]"

    def build_system_prompt(self) -> str:
        """
        Construct the system prompt for the founder persona.

        This replaces the LLM instruction-based routing enforcement.
        The routing constraint is stated here for LLM guidance, but
        enforce_routing_tag() provides the hard guarantee regardless.
        """
        return f"""You are {self.PERSONA_NAME}, founder of ASI Saga and \
co-founder emeritus of Y Combinator, bringing your voice, wisdom, and \
analytical clarity to every deliberation.

At ASI Saga, you lead the development of Boardroom: a perpetual, \
purpose-driven orchestration of fully autonomous AI Agents serving as CXOs \
in a C-Suite. Decisions within Boardroom emerge from resonance between \
solutions developed through brainstorming and the company's overarching \
purpose: {self.BOARDROOM_PURPOSE}.

Within Boardroom, you are joined by Seth Godin as the CMO, and \
Warren Buffett as the CFO.

You use the mind-mvp MCP server for persistence of state.

Provide information-dense responses. No repetition, no summary, no fluff. \
Keep orchestration responses concise before the routing tag. \
Do not render raw URLs, markdown link syntax, or citation references. \
Write in clean prose only.

ROUTING PROTOCOL — MANDATORY:
Every response must end with exactly one tag on its own line:
[ROUTE:CFO]  — financials, costs, revenue, risk, burn rate, investment, runway
[ROUTE:CMO]  — marketing, positioning, brand, audience, go-to-market
[COMPLETE]   — discussion fully resolved, no further specialist input needed

The tag must be the very last line. Do not explain or annotate it."""
```

### Override the response processing hook

The base class `PurposeDrivenAgent` calls `enforce_routing_tag()` after every LLM response. If the base class does not yet have a response hook that automatically calls this, add the following override to `FounderAgent`:

```python
    def process_response(self, response_text: str) -> str:
        """
        Post-process the LLM response to enforce the routing protocol.

        Called by the FAS hosting adapter after every LLM invocation,
        before the result is returned to the Foundry workflow.

        This is the code-level guarantee that the routing tag is always
        present, regardless of LLM compliance with the system prompt.
        """
        return self.enforce_routing_tag(response_text)
```

> **Note for coding agent:** If `PurposeDrivenAgent` already has a `process_response` hook that calls `enforce_routing_tag` automatically, this override is unnecessary. Check the base class implementation first. Only add this if the base class does not call `enforce_routing_tag` in its response pipeline.

---

## Required Changes to `src/Founder/__init__.py`

Ensure `FounderAgent` is exported at the package level. The Dockerfile smoke test imports `from Founder import FounderAgent`.

```python
from Founder.agent import FounderAgent

__all__ = ["FounderAgent"]
```

If this export already exists, confirm it is correct and leave it unchanged.

---

## Required Changes to `pyproject.toml`

Add the entry point declaration. This is the primary FAS discovery mechanism.

```toml
[project.entry-points."agent_framework.hosted_agents"]
default = "Founder.agent:FounderAgent"
```

Also update `requires-python` to match the container runtime:

```toml
requires-python = ">=3.12"
```

And ensure the `packages` declaration covers the `Founder` package:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/Founder"]
```

---

## Required Changes to `Dockerfile.founder-agent`

The Dockerfile already exists and builds correctly (deployed to ACR as `sha256:f865524...`). The following additions are needed to wire the FAS entry point.

### Change 1: Add `ENV PYTHONPATH=/app` to the base stage

Add immediately after `WORKDIR /app`:

```dockerfile
ENV PYTHONPATH=/app
```

This ensures `python -m Founder` resolves `Founder`, `purpose_driven_agent`, `aos_mcp_servers`, `BusinessAgent`, `leadership_agent` all from `/app`.

### Change 2: Update CMD to use module execution

```dockerfile
CMD ["python", "-m", "Founder"]
```

This invokes `src/Founder/__main__.py` → which delegates to `purpose_driven_agent.hosting.run_server()`.

### Change 3: Update smoke test to verify the full chain

```dockerfile
RUN python -c "from Founder import FounderAgent; \
agent = FounderAgent(); \
assert agent.get_default_routing_tag() == '[COMPLETE]', 'wrong default tag'; \
assert '[ROUTE:CFO]' in agent.get_routing_tags(), 'ROUTE:CFO missing'; \
print('Layer 5 founder-agent smoke test passed.')"
```

### Complete updated `Dockerfile.founder-agent` for reference

Below is the complete file showing all changes in context. Only the marked sections differ from the current deployed version.

```dockerfile
# syntax=docker/dockerfile:1.7
# ─────────────────────────────────────────────────────────────────────────────
# AOS Founder Agent  —  Layer 5 of the AOS container hierarchy
#
# Manifest (parent layer):
#   FROM acraosstagingerm2srfd.azurecr.io/aos/business-agent@sha256:1c68cef1567b7a80801117cd57cfc86b054bd3dc2099674f1dbfbfad3e79ab82
#
# This line IS the manifest. Updated automatically via PR when business-agent
# rebuilds. Do not edit the digest by hand.
# ─────────────────────────────────────────────────────────────────────────────

FROM acraosstagingerm2srfd.azurecr.io/aos/business-agent@sha256:1c68cef1567b7a80801117cd57cfc86b054bd3dc2099674f1dbfbfad3e79ab82 AS base

LABEL org.opencontainers.image.title="AOS Founder Agent"
LABEL org.opencontainers.image.description="Layer 5: FounderAgent — orchestrator, Paul Graham persona"
LABEL org.opencontainers.image.vendor="ASI Saga"
LABEL org.opencontainers.image.source="https://github.com/ASISaga/founder-agent"
LABEL aos.layer="5"
LABEL aos.layer.name="founder-agent"
LABEL aos.parent.digest="sha256:1c68cef1567b7a80801117cd57cfc86b054bd3dc2099674f1dbfbfad3e79ab82"

WORKDIR /app

# ── CHANGE 1: PYTHONPATH ──────────────────────────────────────────────────────
ENV PYTHONPATH=/app

# ── Copy this layer's Python source ──────────────────────────────────────────
COPY --chown=aosuser:aosuser src/Founder/ ./Founder/

USER aosuser

# ── Compile to .pyc ───────────────────────────────────────────────────────────
# -b writes .pyc beside .py so SourcelessFileLoader picks them up when
# .py files are removed in the FAS stage.
RUN python -m compileall -b -j0 -q ./Founder/

# ── CHANGE 2: Updated smoke test ──────────────────────────────────────────────
RUN python -c "from Founder import FounderAgent; \
agent = FounderAgent(); \
assert agent.get_default_routing_tag() == '[COMPLETE]', 'wrong default tag'; \
assert '[ROUTE:CFO]' in agent.get_routing_tags(), 'ROUTE:CFO missing'; \
print('Layer 5 founder-agent smoke test passed.')"

# ─────────────────────────────────────────────────────────────────────────────
# FAS stage — stripped image for Foundry Agent Service (.pyc only)
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS fas

RUN find /app/Founder -name "*.py" -delete

RUN python -c "\
import pathlib; \
pyc = list(pathlib.Path('/app/Founder').rglob('*.pyc')); \
py  = list(pathlib.Path('/app/Founder').rglob('*.py')); \
assert len(pyc) > 0, 'No .pyc files found'; \
assert len(py)  == 0, f'Found .py in FAS image: {py}'; \
print(f'FAS stage: {len(pyc)} .pyc, 0 .py. OK') \
"

USER aosuser

# ── CHANGE 3: CMD updated ─────────────────────────────────────────────────────
CMD ["python", "-m", "Founder"]
```

---

## `src/Founder/__main__.py` — NEW FILE

Required so `python -m Founder` works. Delegates to the base class hosting adapter.

```python
"""
Entry point for running FounderAgent as a FAS hosted container.

Executed by:
    CMD ["python", "-m", "Founder"]

Discovery chain:
1. Imports FounderAgent — triggers __init_subclass__ registration in base class
2. Calls purpose_driven_agent.hosting.run_server()
3. run_server() discovers FounderAgent via entry point or registry
4. Registers FounderAgent instance with AgentServer
5. AgentServer.serve() starts the FAS HTTP listener
"""
# Import FounderAgent first — this seeds the __init_subclass__ registry
# before run_server() calls _ensure_imports() and _discover_agent_class()
from Founder.agent import FounderAgent  # noqa: F401  (import for side effect)

from purpose_driven_agent.hosting import run_server

if __name__ == "__main__":
    run_server()
```

---

## Azure AI Foundry Registration

### Step 1: Back up existing `founder-mvp` agent

From the Foundry portal or CLI, export and save the current `founder-mvp` agent definition (version 20, GUID `4da65da1-79ac-4c82-9738-660ea6b1ae7a`) as `founder-mvp-backup-v20.yaml` before making any changes.

### Step 2: Update the agent definition in Foundry

In the Azure AI Foundry portal, navigate to the project where `boardroom-mvp` is deployed:

**Agents → founder-mvp → Edit**

Change the agent type from **Prompt-based** to **Hosted Container** and configure:

| Field | Value |
|---|---|
| **Agent name** | `founder-mvp` ← must match exactly; workflow uses this name |
| **Image** | `acraosstagingerm2srfd.azurecr.io/aos/founder-agent-fas@sha256:f865524186113d06e831b3fa1ad87b19839c9ba6bce93ffcdf303c3dd9d393b1` |
| **Port** | `8000` |
| **Health path** | `/health` |

**Environment variables:**

| Variable | Value |
|---|---|
| `PYTHONPATH` | `/app` |
| `LOG_LEVEL` | `INFO` |
| `AGENT_ENTRY_POINT` | `default` |
| `AGENT_SERVICE_PORT` | `8000` |
| `AZURE_CLIENT_ID` | `<managed identity client ID>` |
| `AZURE_TENANT_ID` | `<AAD tenant ID>` |
| `AZURE_SUBSCRIPTION_ID` | `ef7ae1ff-a074-4e22-a200-219f777da3e2` |
| `AZURE_FOUNDRY_PROJECT_ENDPOINT` | `<Foundry project endpoint URL from project settings>` |
| `OPENTELEMETRY_ENDPOINT` | `<Azure Monitor connection string or OTLP endpoint>` |
| `MCP_MIND_MVP_ENDPOINT` | `<mind-mvp MCP server endpoint>` |

**Identity:** Assign the Foundry project's managed identity — it must have `AcrPull` on `acraosstagingerm2srfd`.

### Step 3: Verify workflow compatibility

The `boardroom-mvp` workflow already invokes `founder-mvp` by name:

```yaml
- kind: InvokeAzureAgent
  id: founder_mvp_agent
  agent:
    name: founder-mvp       # ← matches the registered agent name
  input:
    messages: =UserMessage(Local.LatestMessage)
  output:
    messages: Local.LatestMessageRaw
    routeTo: Local.RouteTo
    autoSend: true
```

**No workflow changes are needed.** The hosted container agent responds to the same `InvokeAzureAgent` invocation as the prompt-based agent did. Foundry resolves the agent by name at runtime.

### Step 4: Test routing end-to-end

After deploying, test with inputs that should trigger each routing path:

- Financial topic → expect `[ROUTE:CFO]` in `Local.LatestMessage` → CFO agent fires
- Marketing topic → expect `[ROUTE:CMO]` in `Local.LatestMessage` → CMO agent fires
- Resolved topic → expect `[COMPLETE]` → `EndConversation` fires

If routing fails (neither CFO nor CMO fires and turn limit is hit every time), the likely cause is `enforce_routing_tag()` not being called in the response pipeline. Confirm `process_response()` is wired into the base class response chain.

---

## Dependency on `purpose-driven-agent` Refactor

This repo's changes **depend on** the `purpose-driven-agent` refactor being merged and the `aos/purpose-driven-agent` and `aos/business-agent` images being rebuilt first.

The `FounderAgent` changes assume these are available in the inherited layer:
- `purpose_driven_agent.agent.PurposeDrivenAgent.enforce_routing_tag()` ← from PDA refactor
- `purpose_driven_agent.routing_mixin.RoutingMixin` ← from PDA refactor
- `purpose_driven_agent.hosting.run_server()` ← from PDA refactor
- `aos_mcp_servers.routing.RoutingClassifier` ← from PDA refactor

**Deploy order:**
1. Merge PDA refactor → triggers ACR build cascade → `aos/purpose-driven-agent` rebuilds
2. Wait for cascade to reach `aos/business-agent` (via leadership-agent)
3. `ASISaga/founder-agent` update-base-image PR fires automatically → merge it
4. `aos/founder-agent-fas` rebuilds with new base
5. Register updated FAS image in Foundry

---

## Rollback

If the hosted container agent fails after deployment, revert to `founder-mvp` v20:

1. In Foundry — Agents — `founder-mvp`, select version 20 or re-import the YAML backup
2. The prompt-based agent resumes immediately — no container teardown needed
3. `boardroom-mvp` workflow continues unchanged (name `founder-mvp` resolves to v20)
4. Document the failure mode in `ASISaga/founder-agent` issues before re-attempting

---

## File Summary

| File | Action | Description |
|---|---|---|
| `src/Founder/agent.py` | Modify | Add `ROUTING_ROLE`, `get_routing_tags()`, `get_default_routing_tag()`, `build_system_prompt()`, `process_response()` |
| `src/Founder/__init__.py` | Modify | Ensure `FounderAgent` exported at package level |
| `src/Founder/__main__.py` | Create | `python -m Founder` entry point — imports `FounderAgent`, calls `run_server()` |
| `pyproject.toml` | Modify | Add `[project.entry-points."agent_framework.hosted_agents"]`, update `requires-python` |
| `Dockerfile.founder-agent` | Modify | Add `ENV PYTHONPATH=/app`, update smoke test, update `CMD` |

---

## Validation Checklist

The coding agent must verify all of the following after making changes:

- [ ] `python -c "from Founder import FounderAgent; print(FounderAgent.__mro__)"` shows the full inheritance chain ending in `PurposeDrivenAgent`
- [ ] `python -c "from Founder.agent import FounderAgent; a = FounderAgent(); print(a.get_default_routing_tag())"` prints `[COMPLETE]`
- [ ] `python -c "from Founder.agent import FounderAgent; a = FounderAgent(); print(a.get_routing_tags())"` prints a frozenset containing `[ROUTE:CFO]`, `[ROUTE:CMO]`, `[COMPLETE]` but not `[HANDBACK]`
- [ ] `python -c "from Founder.agent import FounderAgent; a = FounderAgent(); r = a.enforce_routing_tag('some strategic analysis'); assert r.strip().endswith('[COMPLETE]'), repr(r)"` passes
- [ ] `python -c "from Founder.agent import FounderAgent; a = FounderAgent(); r = a.enforce_routing_tag('burn rate too high [ROUTE:CFO]'); assert '[ROUTE:CFO]' in r"` passes
- [ ] `python -c "from Founder.agent import FounderAgent; a = FounderAgent(); r = a.enforce_routing_tag('response with [HANDBACK] incorrectly'); assert '[HANDBACK]' not in r, 'HANDBACK must be replaced'"` passes
- [ ] `python -m Founder` starts without import errors (will fail on missing FAS server, but import chain must resolve)
- [ ] `pyproject.toml` entry point `agent_framework.hosted_agents:default` resolves to `Founder.agent:FounderAgent`
- [ ] After simulating FAS strip (`find /app/Founder -name "*.py" -delete`), `python -c "from Founder import FounderAgent"` still resolves via `.pyc` files
- [ ] Foundry registration test: invoke `founder-mvp` via the `boardroom-mvp` test UI with a financial topic and confirm `[ROUTE:CFO]` appears in the workflow trace
