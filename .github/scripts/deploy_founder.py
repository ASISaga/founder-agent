"""
Deploy FounderAgent to Foundry Agent Service.

Called by deploy-founder-foundry.yml. Reads all config from environment variables.
"""
import os
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    HostedAgentDefinition,
    ProtocolVersionRecord,
    AgentProtocol,
)
from azure.identity import DefaultAzureCredential

endpoint   = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
image_ref  = os.environ["IMAGE_REF"]
agent_name = os.environ["AGENT_NAME"]

print(f"Endpoint:   {endpoint}")
print(f"Agent name: {agent_name}")
print(f"Image:      {image_ref}")

client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential(),
    allow_preview=True,
)

# Check for existing agent - handle prompt->hosted migration and idempotent updates
try:
    existing = client.agents.get(agent_name=agent_name)
    existing_kind = getattr(existing, "kind", None)
    print(f"Found existing agent '{agent_name}', kind: {existing_kind}")

    if existing_kind == "prompt":
        print("Deleting prompt agent before creating hosted version...")
        client.agents.delete(agent_name=agent_name)
        print("Deleted.")
    else:
        print("Existing hosted agent found - creating new version.")

except Exception as e:
    if "not found" in str(e).lower() or "404" in str(e):
        print(f"No existing agent '{agent_name}' - creating fresh.")
    else:
        raise

# Create hosted agent version
agent = client.agents.create_version(
    agent_name=agent_name,
    definition=HostedAgentDefinition(
        container_protocol_versions=[
            ProtocolVersionRecord(
                protocol=AgentProtocol.RESPONSES,
                version="v1",
            )
        ],
        cpu="1",
        memory="2Gi",
        image=image_ref,
        environment_variables={
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "INFO",
            "AGENT_ENTRY_POINT": "default",
            "AZURE_AI_PROJECT_ENDPOINT": endpoint,
        },
    ),
)

print(f"Created agent version: {agent.version}")
print("Foundry provisions asynchronously - check portal for status.")

# Write GitHub Actions outputs
github_output = os.environ.get("GITHUB_OUTPUT", "")
if github_output:
    with open(github_output, "a") as fh:
        fh.write(f"agent_version={agent.version}\n")
        fh.write("agent_status=provisioning\n")
