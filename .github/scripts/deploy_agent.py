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

agent = client.agents.create_agent(
    model=image,
    name=os.environ["AGENT_NAME"],
    instructions="You are the Founder agent.",
)

print(f"Agent deployed: {agent.id}")