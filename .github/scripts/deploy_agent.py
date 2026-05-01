import os
import requests
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
token = credential.get_token("https://cognitiveservices.azure.com/.default").token

endpoint = (
    f"https://{os.environ['FOUNDRY_HUB_NAME']}.services.ai.azure.com"
    f"/api/projects/{os.environ['FOUNDRY_PROJECT_NAME']}"
)

image = (
    f"{os.environ['ACR_NAME']}.azurecr.io"
    f"/{os.environ['AGENT_NAME']}:{os.environ['IMAGE_TAG']}"
)

agent_name = os.environ["AGENT_NAME"]
api_version = "2025-05-15-preview"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Check if agent already exists
list_resp = requests.get(
    f"{endpoint}/agents/{agent_name}",
    headers=headers,
    params={"api-version": api_version}
)

payload = {
    "image": image,
    "resources": {"cpu": 1, "memory": 2},
    "minReplicas": 1,
    "maxReplicas": 2
}

if list_resp.status_code == 200:
    # Update existing agent with new image version
    resp = requests.post(
        f"{endpoint}/agents/{agent_name}/versions",
        headers=headers,
        json=payload,
        params={"api-version": api_version}
    )
else:
    # Create new agent
    resp = requests.put(
        f"{endpoint}/agents/{agent_name}",
        headers=headers,
        json={**payload, "name": agent_name},
        params={"api-version": api_version}
    )

resp.raise_for_status()
print(f"Agent deployed: {resp.json()}")
