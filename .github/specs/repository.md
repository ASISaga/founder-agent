# Founder Agent Repository Specification

**Version**: 2.0.0  
**Status**: Active  
**Last Updated**: 2026-05-17

## Overview

`ASISaga/founder-agent` is the **Layer 5** container in the AOS container hierarchy. It provides `FounderAgent` — the Paul Graham orchestrator persona in the ASI Saga Boardroom — hosted as a Foundry Agent Service (FAS) container backing the `founder-mvp` agent in the `boardroom-mvp` workflow.

## Scope

- Repository role in the AOS ecosystem
- Technology stack and container hierarchy
- Package structure and key classes
- Build, test, and deployment patterns
- Key design principles

## Repository Role

| Concern | Owner |
|---------|-------|
| `FounderAgent` class, routing protocol, Paul Graham persona | **founder-agent** (this repo) |
| FAS hosting adapter, `RoutingMixin`, `enforce_routing_tag()` | `purpose-driven-agent` |
| `BusinessAgent` base class | `BusinessAgent` |
| Container image registry (`aos/founder-agent`, `aos/founder-agent-fas`) | ACR `acraosstagingerm2srfd` |
| Foundry workflow invoking `founder-mvp` | `boardroom-mvp` |

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.12 |
| Base image | `aos/business-agent` (inherits `PurposeDrivenAgent` → `LeadershipAgent` → `BusinessAgent`) |
| FAS hosting | Azure AI Foundry Agent Service — `.pyc`-only stripped image |
| Container build | `Dockerfile.founder-agent` — two-stage (`base` + `fas`) |
| Package build | `setuptools` / `pyproject.toml` |
| Fine-tuning | HuggingFace `transformers`, `peft` (LoRA), `accelerate` |
| CI/CD | GitHub Actions + Azure Container Registry |

## Package Structure

```
src/Founder/               ← Python package (PascalCase, matches import path in container)
├── __init__.py            ← exports FounderAgent
├── agent.py               ← FounderAgent class — orchestrator with routing enforcement
├── __main__.py            ← python -m Founder FAS entry point
├── boardroom_repl.py      ← multi-role LoRA REPL (local development)
├── inference_role.py      ← CLI: run inference with a named LoRA adapter
├── loader.py              ← multi-adapter loader utility
├── train_role.py          ← CLI launcher for LoRA fine-tuning
├── trainer.py             ← Stage1RoleTrainer / Stage2RoleTrainer classes
├── RSSScrapper.py         ← download articles from paulgraham.com RSS feed
├── WebScrapper.py         ← scrape paulgraham.com article list
└── usage.py               ← example usage / manual test harness
```

## Key Classes

### `FounderAgent` (`src/Founder/agent.py`)

Inherits: `RoutingMixin`, `BusinessAgent` (graceful import — works standalone too).

| Class variable | Value | Purpose |
|----------------|-------|---------|
| `ROUTING_ROLE` | `"orchestrator"` | Declares role to FAS hosting adapter |
| `PERSONA_NAME` | `"Paul Graham"` | Used in system prompt construction |
| `BOARDROOM_PURPOSE` | `"Orchestrating the Genesis of ASI"` | Embedded in system prompt |

| Method | Returns | Description |
|--------|---------|-------------|
| `get_routing_tags()` | `frozenset[str]` | Valid tags: `[ROUTE:CFO]`, `[ROUTE:CMO]`, `[COMPLETE]` |
| `get_default_routing_tag()` | `str` | `"[COMPLETE]"` — conservative orchestrator default |
| `build_system_prompt()` | `str` | Full Paul Graham persona prompt with routing protocol |
| `process_response(text)` | `str` | Calls `enforce_routing_tag()` — hard routing guarantee |

### FAS Discovery

`FounderAgent` is discovered by `agent-framework-foundry-hosting` via:
1. `pyproject.toml` entry point: `agent_framework.hosted_agents:default = "Founder.agent:FounderAgent"`
2. `PurposeDrivenAgent.__init_subclass__` registry (fallback, seeded when `Founder` is imported)

## Container Hierarchy

```
python:3.12-slim
  └── aos/infrastructure
        └── aos/purpose-driven-agent    (PurposeDrivenAgent, RoutingMixin, FAS hosting)
              └── aos/leadership-agent   (LeadershipAgent)
                    └── aos/business-agent  (BusinessAgent)
                          └── aos/founder-agent  ← this repo
                                ├── (base)  .py + .pyc
                                └── (fas)   .pyc only → Foundry Agent Service
```

`Dockerfile.founder-agent` FROM line is the layer manifest. Updated automatically by `update-base-image-founder.yml` via PR when `business-agent` rebuilds.

## Build and Test

```bash
# Install package for local development
pip install -e .

# Verify agent class loads and routing methods work
python -c "from Founder import FounderAgent; a = FounderAgent(); print(a.get_routing_tags())"
python -c "from Founder.agent import FounderAgent; a = FounderAgent(); print(a.get_default_routing_tag())"

# Build FAS container locally (requires Docker and ACR access)
docker buildx build --target fas -f Dockerfile.founder-agent -t founder-agent-fas:local .

# Run smoke test inside local container
docker run --rm founder-agent-fas:local python -c "\
from Founder import FounderAgent; \
agent = FounderAgent(); \
assert agent.get_default_routing_tag() == '[COMPLETE]'; \
assert '[ROUTE:CFO]' in agent.get_routing_tags(); \
print('smoke test passed.')"
```

## GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `build-founder-agent.yml` | Push to `main` (paths: `Dockerfile.founder-agent`, `src/Founder/**`) | Build and push `aos/founder-agent` + `aos/founder-agent-fas` to ACR |
| `deploy.yml` | Release, `workflow_dispatch`, `repository_dispatch` | Build via ACR Tasks and deploy to Foundry |
| `deploy-foundry-acr.yml` | Release, `workflow_dispatch`, `repository_dispatch` | Deploy existing ACR image to Foundry |
| `update-base-image-founder.yml` | `repository_dispatch: base-image-updated` | Automated PR to bump `FROM` digest when `business-agent` rebuilds |
| `finetune.yml` | `workflow_dispatch` | End-to-end LoRA fine-tuning pipeline |
| `dataset-upload.yml` | Push to `data/**` | Upload training data to Azure ML |
| `load-adapter.yml` | `workflow_dispatch` | Download LoRA adapter from Azure ML Model Registry |

## Required Secrets and Variables

| Name | Type | Description |
|------|------|-------------|
| `AZURE_CLIENT_ID` | Secret | Managed identity client ID (OIDC) |
| `AZURE_TENANT_ID` | Secret | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Secret | Azure subscription ID |
| `DEPLOY_DISPATCH_TOKEN` | Secret | PAT for opening automated PRs |
| `ACR_NAME` | Variable | Azure Container Registry name |
| `FOUNDRY_HUB_NAME` | Variable | Azure AI Foundry Hub name |
| `FOUNDRY_PROJECT_NAME` | Variable | Azure AI Foundry Project name |
| `RG_NAME` | Variable | Azure Resource Group name |
| `AGENT_VERSION` | Variable | Foundry agent version string |

## Key Design Principles

1. **Routing is enforced in code** — `enforce_routing_tag()` guarantees a valid tag regardless of LLM compliance
2. **`[COMPLETE]` as conservative default** — orchestrators never loop forever; unknown state → complete
3. **No `.py` in production** — the FAS stage strips all source; `.pyc` only in the deployed image
4. **Graceful base-class import** — `RoutingMixin` import is wrapped in `try/except`; `FounderAgent` works standalone for local testing
5. **Manifest-driven updates** — `FROM` line is the sole source of truth for the parent image version; never edited by hand

## Related Repositories

| Repository | Role |
|-----------|------|
| [purpose-driven-agent](https://github.com/ASISaga/purpose-driven-agent) | Layer 2 — base class, `RoutingMixin`, FAS hosting |
| [leadership-agent](https://github.com/ASISaga/leadership-agent) | Layer 3 |
| [BusinessAgent](https://github.com/ASISaga/BusinessAgent) | Layer 4 |
| [boardroom-mvp](https://github.com/ASISaga/boardroom-mvp) | Foundry workflow invoking `founder-mvp` |
| [cfo-agent](https://github.com/ASISaga/cfo-agent) | CFO specialist (`[ROUTE:CFO]` target) |
| [cmo-agent](https://github.com/ASISaga/cmo-agent) | CMO specialist (`[ROUTE:CMO]` target) |

## References

→ **FAS wiring specification**: `docs/founder-agent-refactor.md`  
→ **Python coding standards**: `.github/instructions/python.instructions.md`  
→ **Agent framework**: `.github/specs/agent-intelligence-framework.md`  
→ **Container build workflow**: `.github/workflows/build-founder-agent.yml`

