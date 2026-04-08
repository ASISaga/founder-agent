# Agent Repository Workflow Templates

This directory contains **ready-to-copy GitHub Actions workflow templates** for
agent repositories (e.g. `ceo-agent`, `cmo-agent`, `cfo-agent`) built with the
Microsoft Agent Framework and deployed on Azure AI Foundry Agent Service.

These templates invoke the centralized, reusable workflows in
`ASISaga/aos-intelligence` to manage fine-tuning datasets and LoRA adapter
artifacts without duplicating infrastructure logic in every agent repo.

---

## Centralized Reusable Workflows (in this repo)

| Workflow | Purpose |
|----------|---------|
| `.github/workflows/load-dataset.yml` | Upload JSONL / MLTable dataset to Azure ML as a versioned Data Asset |
| `.github/workflows/persist-lora-adapter.yml` | Register a trained LoRA adapter (MLflow) in the Azure ML Model Registry |
| `.github/workflows/load-lora-adapter.yml` | Resolve and optionally download a LoRA adapter from the Azure ML Model Registry |

These workflows use `on: workflow_call` and are designed to be called from any
agent repository via:

```yaml
uses: ASISaga/aos-intelligence/.github/workflows/<workflow-name>.yml@main
```

---

## Templates to Copy to Agent Repositories

| Template file | Destination in agent repo | Purpose |
|---------------|--------------------------|---------|
| `dataset-upload.yml` | `.github/workflows/dataset-upload.yml` | Push training data to Azure ML whenever datasets change |
| `finetune.yml` | `.github/workflows/finetune.yml` | Run LoRA fine-tuning job end-to-end (upload data → train → register adapter) |
| `load-adapter.yml` | `.github/workflows/load-adapter.yml` | Retrieve a registered adapter from the Azure ML Model Registry |

---

## Quick Setup

### 1. Copy the template workflows to your agent repo

```bash
# Example: setting up a ceo-agent repository
cp .github/agent-repo-workflows/dataset-upload.yml  /path/to/ceo-agent/.github/workflows/
cp .github/agent-repo-workflows/finetune.yml        /path/to/ceo-agent/.github/workflows/
cp .github/agent-repo-workflows/load-adapter.yml    /path/to/ceo-agent/.github/workflows/
```

### 2. Configure the templates

Open each copied file and update the `env:` section at the top with your
agent's specific values:

```yaml
env:
  AGENT_NAME: "ceo-agent"         # Your agent name
  PERSONA_TYPE: "ceo"             # Persona type (matches LoRAAdapterRegistry key)
  DATASET_TYPE: "jsonl"           # 'jsonl' or 'mltable'
  DATASET_PATH: "data/finetune"   # Path to training data in your repo
  DATASET_NAME: "ceo-finetune"    # Azure ML Data Asset name
  TRAIN_SCRIPT: "scripts/train_lora.py"  # Your LoRA training script
```

### 3. Create Azure credentials

Each agent repo needs the following **secrets** (Settings → Secrets and variables → Actions):

| Secret | Description |
|--------|-------------|
| `AZURE_CLIENT_ID` | Client ID of the service principal or user-assigned managed identity |
| `AZURE_TENANT_ID` | Azure tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |

And the following **variables** (Settings → Secrets and variables → Actions → Variables):

| Variable | Description |
|----------|-------------|
| `AZURE_ML_WORKSPACE` | Azure ML workspace name |
| `AZURE_RESOURCE_GROUP` | Azure resource group containing the workspace |

> **Tip**: Use a single service principal with appropriate RBAC roles across all
> agent repositories, or use Workload Identity Federation (OIDC) for keyless
> authentication — both are supported by the `azure/login@v2` action used in
> these workflows.

### 4. (Optional) Add a training script

The `finetune.yml` template expects a training script in your repo.
A minimal LoRA training script using HuggingFace PEFT looks like:

```python
# scripts/train_lora.py
import argparse
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import SFTTrainer
import mlflow

parser = argparse.ArgumentParser()
parser.add_argument("--persona_type", required=True)
parser.add_argument("--base_model", default="meta-llama/Llama-3.3-70B-Instruct")
parser.add_argument("--dataset_path", required=True)
args = parser.parse_args()

# Enable MLflow autologging so Azure ML automatically logs the adapter
mlflow.autolog()

lora_config = LoraConfig(r=16, lora_alpha=32, target_modules="all-linear")
model = AutoModelForCausalLM.from_pretrained(args.base_model)
model = get_peft_model(model, lora_config)
tokenizer = AutoTokenizer.from_pretrained(args.base_model)

training_args = TrainingArguments(
    output_dir="./outputs/model",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    learning_rate=3e-4,
)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=...,  # load from args.dataset_path
)
trainer.train()
trainer.save_model("./outputs/model")
```

---

## Workflow Sequence Diagram

```
Agent Repository                        aos-intelligence
─────────────────                       ──────────────────────────────────
dataset-upload.yml
  ├─ push to data/finetune/**
  └─ calls ──────────────────────────► load-dataset.yml
                                            ├─ Azure Login (OIDC)
                                            └─ Upload to Azure ML Data Asset
                                                     │
                                                     ▼
finetune.yml (workflow_dispatch)
  ├─ calls ──────────────────────────► load-dataset.yml (refresh data)
  ├─ Submit Azure ML training job
  ├─ Wait for job completion
  └─ calls ──────────────────────────► persist-lora-adapter.yml
                                            ├─ Azure Login (OIDC)
                                            └─ Register MLflow model
                                                 in Azure ML Model Registry
                                                     │
                                                     ▼
load-adapter.yml (workflow_dispatch)
  └─ calls ──────────────────────────► load-lora-adapter.yml
                                            ├─ Azure Login (OIDC)
                                            ├─ Resolve model version
                                            └─ Download artifacts (optional)
```

---

## RBAC Requirements

The service principal / managed identity used by these workflows requires the
following Azure RBAC roles on the target Azure ML workspace:

| Role | Reason |
|------|--------|
| `AzureML Data Scientist` | Submit training jobs, register models and data assets |
| `Storage Blob Data Contributor` | Upload dataset files to the workspace storage account |

Assign these roles via the Azure Portal or CLI:

```bash
az role assignment create \
  --assignee <service-principal-object-id> \
  --role "AzureML Data Scientist" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.MachineLearningServices/workspaces/<ws>
```

---

## Versioning Strategy

| Artifact | Versioning |
|----------|------------|
| Dataset (Data Asset) | Push-triggered: short Git SHA; manual: user-supplied |
| LoRA Adapter (Model Asset) | User-supplied via `adapter_version` input (default `"1"`) |

For production workflows, consider using a semantic version tag (e.g. `v1.2.0`)
or an incrementing integer tied to your release process.
