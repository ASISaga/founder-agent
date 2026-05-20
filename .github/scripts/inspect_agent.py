"""
Diagnostic script - prints raw agent and version attributes from Foundry.
Run before tests to discover the correct status field name and value.
"""
import os
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

ENDPOINT   = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
AGENT_NAME = os.environ.get("AGENT_NAME", "Founder")
VERSION    = os.environ.get("AGENT_VERSION", "1")

client = AIProjectClient(
    endpoint=ENDPOINT,
    credential=DefaultAzureCredential(),
    allow_preview=True,
)

print(f"=== Agent: {AGENT_NAME} ===")
try:
    agent = client.agents.get(agent_name=AGENT_NAME)
    attrs = {k: v for k, v in vars(agent).items() if not k.startswith("_")}
    for k, v in sorted(attrs.items()):
        print(f"  {k}: {v}")
except Exception as e:
    print(f"  ERROR getting agent: {e}")

print(f"\n=== Version: {AGENT_NAME} v{VERSION} ===")
try:
    ver = client.agents.get_version(agent_name=AGENT_NAME, agent_version=VERSION)
    attrs = {k: v for k, v in vars(ver).items() if not k.startswith("_")}
    for k, v in sorted(attrs.items()):
        print(f"  {k}: {v}")
except Exception as e:
    print(f"  ERROR getting version: {e}")

print("\n=== All agents in project ===")
try:
    for a in client.agents.list():
        print(f"  {a.name}")
except Exception as e:
    print(f"  ERROR listing agents: {e}")
