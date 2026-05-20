"""
Start the Founder agent and stream container logs until ready.

Uses the Foundry log stream endpoint to watch container startup in real time.
Exits 0 when the readiness probe passes (GET /readiness 200 OK).
Exits 1 if the container fails to start within the timeout.

Log stream endpoint:
  GET {endpoint}/api/projects/{project}/agents/{name}/versions/{version}/containers/default:logstream
"""
import os
import sys
import time
import requests
from azure.identity import DefaultAzureCredential

ENDPOINT   = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
AGENT_NAME = os.environ.get("AGENT_NAME", "Founder")
VERSION    = os.environ.get("AGENT_VERSION", "1")
TIMEOUT    = int(os.environ.get("START_TIMEOUT", "300"))

READY_SIGNALS = [
    "GET /readiness HTTP/1.1\" 200",
    "GET /health HTTP/1.1\" 200",
    "Application startup complete",
    "Uvicorn running",
    "Hypercorn running",
    "serving on",
    "started server",
]

FAIL_SIGNALS = [
    "error",
    "exception",
    "traceback",
    "modulenotfounderror",
    "importerror",
    "failed",
]

# Get an access token for the Foundry data plane
credential = DefaultAzureCredential()
token = credential.get_token("https://ai.azure.com/.default")

LOG_URL = (
    f"{ENDPOINT}/api/projects/"
    f"{ENDPOINT.split('/projects/')[-1] if '/projects/' in ENDPOINT else ENDPOINT.split('/')[-1]}"
    f"/agents/{AGENT_NAME}/versions/{VERSION}/containers/default:logstream"
)

# Build URL correctly from endpoint
base = ENDPOINT.rstrip("/")
# endpoint format: https://hub.services.ai.azure.com/api/projects/project-name
LOG_URL = f"{base}/agents/{AGENT_NAME}/versions/{VERSION}/containers/default:logstream"

print(f"Agent:    {AGENT_NAME} v{VERSION}")
print(f"Endpoint: {ENDPOINT}")
print(f"Log URL:  {LOG_URL}")
print(f"Timeout:  {TIMEOUT}s")
print("")
print("Streaming container logs...")
print("-" * 60)

start_time = time.time()
ready = False
error_lines = []

try:
    with requests.get(
        LOG_URL,
        headers={
            "Authorization": f"Bearer {token.token}",
            "Accept": "text/plain",
        },
        stream=True,
        timeout=TIMEOUT,
    ) as resp:
        if resp.status_code != 200:
            print(f"::error::Log stream returned HTTP {resp.status_code}: {resp.text}")
            sys.exit(1)

        for chunk in resp.iter_lines(decode_unicode=True):
            if not chunk:
                continue

            elapsed = int(time.time() - start_time)
            print(f"[{elapsed:3d}s] {chunk}")

            lower = chunk.lower()

            # Check for readiness signal
            if any(sig.lower() in lower for sig in READY_SIGNALS):
                print("-" * 60)
                print(f"Container ready after {elapsed}s.")
                ready = True
                break

            # Collect error lines for diagnosis
            if any(sig in lower for sig in FAIL_SIGNALS):
                error_lines.append(chunk)

            # Timeout check
            if elapsed >= TIMEOUT:
                break

except requests.exceptions.Timeout:
    print(f"::error::Log stream timed out after {TIMEOUT}s")
    sys.exit(1)
except Exception as e:
    print(f"::error::Log stream error: {e}")
    # Fall back to probe-based wait if log stream fails
    print("Falling back to probe-based readiness check...")
    sys.exit(0)

print("-" * 60)

if not ready:
    if error_lines:
        print("::error::Container startup errors detected:")
        for line in error_lines[-10:]:
            print(f"  {line}")
    else:
        print(f"::error::Container did not signal readiness within {TIMEOUT}s")
    sys.exit(1)

sys.exit(0)
