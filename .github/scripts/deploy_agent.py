import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

endpoint = (
    f"https://{os.environ['FOUNDRY_HUB_NAME']}.services.ai.azure.com"
    f"/api/projects/{os.environ['FOUNDRY_PROJECT_NAME']}"
)

client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential()
)

image = (
    f"{os.environ['ACR_NAME']}.azurecr.io"
    f"/{os.environ['AGENT_NAME']}:{os.environ['IMAGE_TAG']}"
)

# Check if agent already exists — update it, otherwise create
agents = client.agents.list()
existing = next((a for a in agents if a.name == os.environ["AGENT_NAME"]), None)

if existing:
    agent = client.agents.update(
        agent_id=existing.id,
        model=image,
        name=os.environ["AGENT_NAME"],
        instructions="You are the Founder agent.",
    )
    print(f"Agent updated: {agent.id}")
else:
    agent = client.agents.create(
        model=image,
        name=os.environ["AGENT_NAME"],
        instructions="You are the Founder agent.",
    )
    print(f"Agent created: {agent.id}")
