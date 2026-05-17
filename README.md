# AOS Founder Agent

**Layer 5 of the AOS container hierarchy** — the `FounderAgent` hosted on Azure AI Foundry Agent Service (FAS), embodying the Paul Graham persona as the orchestrator in the `boardroom-mvp` workflow.

---

## Role in the AOS Ecosystem

`FounderAgent` is the **orchestrator** in the ASI Saga Boardroom. It receives conversation context, reasons about it, and routes to specialist agents (CFO or CMO) or signals that deliberation is complete.

```
boardroom-mvp workflow
  └── InvokeAzureAgent: founder-mvp
        └── FounderAgent
              ├── [ROUTE:CFO]  → Warren Buffett (CFO agent)
              ├── [ROUTE:CMO]  → Seth Godin (CMO agent)
              └── [COMPLETE]   → EndConversation
```

---

## Package Layout

```
founder-agent/
├── src/
│   └── Founder/                   ← Python package (PascalCase, intentional)
│       ├── __init__.py            ← exports FounderAgent
│       ├── agent.py               ← FounderAgent class (orchestrator)
│       ├── __main__.py            ← python -m Founder FAS entry point
│       ├── boardroom_repl.py      ← multi-role LoRA REPL (local dev)
│       ├── inference_role.py      ← CLI: run inference with a named adapter
│       ├── loader.py              ← multi-adapter loader utility
│       ├── train_role.py          ← CLI: launch LoRA fine-tuning job
│       ├── trainer.py             ← Stage1/Stage2 LoRA trainer classes
│       ├── RSSScrapper.py         ← download articles from paulgraham.com RSS
│       ├── WebScrapper.py         ← scrape paulgraham.com article list
│       └── usage.py               ← example usage / manual test harness
├── dataset/
│   ├── overview.md                ← 2,000-entry founder-ops corpus description
│   ├── feed.rss                   ← Paul Graham RSS feed snapshot
│   ├── paulgraham_articles/       ← scraped HTML articles (WebScrapper output)
│   └── paulgraham_rss_articles/   ← scraped HTML articles (RSSScrapper output)
├── docs/
│   └── founder-agent-refactor.md  ← FAS wiring specification (reference)
├── Dockerfile.founder-agent        ← FAS production container (two-stage)
├── Dockerfile                      ← legacy dev container
├── agent.yaml                      ← Foundry agent definition
├── pyproject.toml                  ← package metadata and entry points
└── update-base-image-founder.yml   ← base image manifest auto-update workflow
```

---

## Inheritance Chain

```
PurposeDrivenAgent   (purpose_driven_agent/agent.pyc in container)
  └── LeadershipAgent    (leadership_agent/agent.pyc)
        └── BusinessAgent    (BusinessAgent/agent.pyc)
              └── FounderAgent     (Founder/agent.pyc — this repo)
```

Import in container: `from Founder import FounderAgent`

---

## Routing Protocol

Every LLM response is post-processed by `process_response()` → `enforce_routing_tag()` to guarantee exactly one of these tags appears as the final line:

| Tag | Meaning |
|-----|---------|
| `[ROUTE:CFO]` | Topic involves financials, costs, revenue, risk, burn rate, investment, runway |
| `[ROUTE:CMO]` | Topic involves marketing, positioning, brand, audience, go-to-market |
| `[COMPLETE]` | Deliberation fully resolved — no further specialist input needed |

`[COMPLETE]` is the conservative default when no tag is detected. `[HANDBACK]` is invalid for an orchestrator and is replaced with `[COMPLETE]`.

---

## FAS Container

`Dockerfile.founder-agent` builds two image targets from a single file:

| Stage | Target | Contents | Purpose |
|-------|--------|----------|---------|
| `base` | `aos/founder-agent` | `.py` + `.pyc` | Development / debugging |
| `fas` | `aos/founder-agent-fas` | `.pyc` only | Foundry Agent Service hosting |

The FAS stage strips all `.py` files so source is not exposed in production. The `CMD` is `python -m Founder`, which delegates to `purpose_driven_agent.hosting.run_server()`.

**FAS discovery** — `FounderAgent` is found by the hosting adapter via:
1. `pyproject.toml` entry point `agent_framework.hosted_agents:default = "Founder.agent:FounderAgent"`
2. `PurposeDrivenAgent.__init_subclass__` registry (fallback, seeded on import)

---

## LoRA Fine-Tuning Tools

The `src/Founder/` package includes a two-stage LoRA fine-tuning pipeline for instilling the Paul Graham persona into a Llama-family base model.

### Stage 1 — Golden batch imprint

```bash
python src/Founder/train_role.py \
  --stage 1 \
  --role founder \
  --adapter_name founder_pg \
  --data_file dataset/founder_pg.json \
  --output_dir ./out/founder_stage1
```

### Stage 2 — Expansion pass

```bash
python src/Founder/train_role.py \
  --stage 2 \
  --role founder \
  --golden_adapter_name founder_pg \
  --golden_adapter_path ./out/founder_stage1/adapters/founder_pg \
  --new_adapter_name founder_expansion \
  --data_file dataset/founder_expansion.json \
  --output_dir ./out/founder_stage2
```

### Inference

```bash
python src/Founder/inference_role.py \
  --base_model meta-llama/Llama-3.1-8B-Instruct \
  --adapter founder_pg=./out/founder_stage1/adapters/founder_pg \
  --adapter founder_expansion=./out/founder_stage2/adapters/founder_expansion \
  --active founder_expansion \
  --prompt "Evaluate this founder's plan to enter a saturated SaaS market."
```

### Interactive REPL

```bash
python src/Founder/boardroom_repl.py \
  --base_model meta-llama/Llama-3.1-8B-Instruct \
  --adapter founder_pg=./out/founder_stage1/adapters/founder_pg \
  --adapter cfo=./out/cfo_stage1/adapters/cfo_pg
```

Commands: `/role <name>`, `/volley`, `/exit`

---

## Data Collection

```bash
# Scrape articles from paulgraham.com (outputs to dataset/paulgraham_articles/)
python src/Founder/WebScrapper.py

# Download articles listed in the local RSS feed (outputs to dataset/paulgraham_rss_articles/)
python src/Founder/RSSScrapper.py
```

---

## GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `build-founder-agent.yml` | Push to `main` affecting `Dockerfile.founder-agent` or `src/Founder/**` | Build and push `aos/founder-agent` (base) and `aos/founder-agent-fas` (FAS) to ACR |
| `deploy.yml` | Release published, `workflow_dispatch`, `repository_dispatch` | Build image via ACR Tasks and deploy to Azure AI Foundry |
| `deploy-foundry-acr.yml` | Release published, `workflow_dispatch`, `repository_dispatch` | Deploy an existing ACR image to Azure AI Foundry |
| `update-base-image-founder.yml` | `repository_dispatch: base-image-updated` | Automated PR to bump the `FROM` digest in `Dockerfile.founder-agent` when `business-agent` rebuilds |
| `finetune.yml` | `workflow_dispatch` | End-to-end LoRA fine-tuning: upload dataset → submit Azure ML job → register adapter |
| `dataset-upload.yml` | Push to `data/**` | Upload training dataset to Azure ML as a versioned Data Asset |
| `load-adapter.yml` | `workflow_dispatch` | Resolve and download a LoRA adapter from the Azure ML Model Registry |

---

## Required Secrets and Variables

| Name | Type | Description |
|------|------|-------------|
| `AZURE_CLIENT_ID` | Secret | Managed identity client ID (OIDC) |
| `AZURE_TENANT_ID` | Secret | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Secret | Azure subscription ID |
| `DEPLOY_DISPATCH_TOKEN` | Secret | PAT for opening automated PRs (base image update) |
| `ACR_NAME` | Variable | Azure Container Registry name (e.g. `acraosstagingerm2srfd`) |
| `FOUNDRY_HUB_NAME` | Variable | Azure AI Foundry Hub name |
| `FOUNDRY_PROJECT_NAME` | Variable | Azure AI Foundry Project name |
| `RG_NAME` | Variable | Azure Resource Group name |
| `AGENT_VERSION` | Variable | Foundry agent version string |

---

## Related Repositories

| Repository | Role |
|-----------|------|
| [purpose-driven-agent](https://github.com/ASISaga/purpose-driven-agent) | Layer 2 — `PurposeDrivenAgent` base class + FAS hosting adapter + `RoutingMixin` |
| [leadership-agent](https://github.com/ASISaga/leadership-agent) | Layer 3 — `LeadershipAgent` |
| [BusinessAgent](https://github.com/ASISaga/BusinessAgent) | Layer 4 — `BusinessAgent` |
| [boardroom-mvp](https://github.com/ASISaga/boardroom-mvp) | Foundry workflow that invokes `founder-mvp` |
| [cfo-agent](https://github.com/ASISaga/cfo-agent) | CFO specialist routed to by `[ROUTE:CFO]` |
| [cmo-agent](https://github.com/ASISaga/cmo-agent) | CMO specialist routed to by `[ROUTE:CMO]` |
