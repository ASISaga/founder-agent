# Founder Agent GitHub Actions Workflows

This directory contains the GitHub Actions workflows for building, deploying, and
maintaining the `FounderAgent` FAS container and its associated LoRA fine-tuning pipeline.

---

## Workflow Reference

### `build-founder-agent.yml` — Build and push FAS container images

**Trigger:** Push to `main` affecting `Dockerfile.founder-agent` or `src/Founder/**`; `workflow_dispatch`

Builds two image targets from `Dockerfile.founder-agent` and pushes them to ACR:

| Image | Target | Contents |
|-------|--------|----------|
| `aos/founder-agent` | `base` | `.py` + `.pyc` — development / debugging |
| `aos/founder-agent-fas` | `fas` | `.pyc` only — Foundry Agent Service production |

After pushing, it runs an in-container verification for each image to confirm the correct file set. A step summary shows digests, parent manifest, and the full layer hierarchy.

**Required:** GitHub Environment `staging`, secrets `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID`, variable `ACR_NAME`.

---

### `deploy.yml` — Build and deploy to Foundry

**Trigger:** GitHub Release published → `prod`; `workflow_dispatch` (choose environment); `repository_dispatch: infra_provisioned`

Builds the container image via ACR Tasks (no Docker required on the runner), creates a new agent version in Azure AI Foundry, and starts it. The agent name follows `<APP_NAME>-<repo>` convention.

**Required:** Secrets `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID`; variables `ACR_NAME`, `FOUNDRY_HUB_NAME`, `FOUNDRY_PROJECT_NAME`, `RG_NAME`, `AGENT_VERSION`, `APP_NAME`.

---

### `deploy-foundry-acr.yml` — Deploy existing image from ACR

**Trigger:** GitHub Release published → `prod`; `workflow_dispatch`; `repository_dispatch: infra_provisioned`

Resolves the latest image tag from ACR dynamically (no build step) and deploys it to Foundry via the Azure AI Projects Python SDK. Uses a deploy script at `.github/scripts/deploy_agent.py`.

Agent name is hard-coded as `boardroom-founder-agent`.

**Required:** Same secrets and variables as `deploy.yml`.

---

### `update-base-image-founder.yml` — Automated base image manifest update

**Trigger:** `repository_dispatch: base-image-updated` (sent by `business-agent` build pipeline)

When the parent `aos/business-agent` image is rebuilt, this workflow:
1. Validates the incoming `base_digest` payload
2. Checks whether the digest in `Dockerfile.founder-agent` already matches
3. If different, updates the `FROM` and `LABEL aos.parent.digest` lines
4. Commits to a new branch and opens a PR

Merging the PR triggers `build-founder-agent.yml`, completing the cascade.

**Required:** Secret `DEPLOY_DISPATCH_TOKEN` (PAT with `contents: write` and `pull-requests: write`).

---

### `finetune.yml` — LoRA fine-tuning pipeline

**Trigger:** `workflow_dispatch`

End-to-end LoRA fine-tuning job: uploads the training dataset to Azure ML as a versioned Data Asset, submits the training job, waits for completion, and registers the resulting adapter in the Azure ML Model Registry as an MLflow model.

---

### `dataset-upload.yml` — Upload training dataset

**Trigger:** Push to `data/**`

Uploads JSONL / MLTable training data to Azure ML whenever the dataset changes.

---

### `load-adapter.yml` — Load LoRA adapter from registry

**Trigger:** `workflow_dispatch`

Resolves the specified adapter version from the Azure ML Model Registry and optionally downloads the artifacts.

---

## Layer Hierarchy

```
python:3.12-slim
  └── aos/infrastructure
        └── aos/purpose-driven-agent
              └── aos/leadership-agent
                    └── aos/business-agent   ← parent (manifest in Dockerfile.founder-agent FROM line)
                          └── aos/founder-agent:${{ github.sha }}
                                ├── (base)  .py + .pyc
                                └── (fas)   .pyc only → Foundry Agent Service
```

`founder-agent` is a **leaf node** — no downstream cascade.

---

## Secrets and Variables

| Name | Type | Used By |
|------|------|---------|
| `AZURE_CLIENT_ID` | Secret | All Azure workflows (OIDC) |
| `AZURE_TENANT_ID` | Secret | All Azure workflows |
| `AZURE_SUBSCRIPTION_ID` | Secret | All Azure workflows |
| `DEPLOY_DISPATCH_TOKEN` | Secret | `update-base-image-founder.yml` |
| `ACR_NAME` | Variable | `build-founder-agent.yml`, `deploy.yml`, `deploy-foundry-acr.yml` |
| `FOUNDRY_HUB_NAME` | Variable | `deploy.yml`, `deploy-foundry-acr.yml` |
| `FOUNDRY_PROJECT_NAME` | Variable | `deploy.yml`, `deploy-foundry-acr.yml` |
| `RG_NAME` | Variable | `deploy.yml`, `deploy-foundry-acr.yml` |
| `AGENT_VERSION` | Variable | `deploy.yml`, `deploy-foundry-acr.yml` |
| `APP_NAME` | Variable | `deploy.yml` (agent name prefix) |

