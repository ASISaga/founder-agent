"""
Warm up the Founder agent by sending a lightweight ping request and retrying
until the session sandbox is ready.

Foundry hosted agents use per-session VM-isolated sandboxes. There is no
persistent container to tail. The sandbox provisions when the first request
arrives -- Foundry returns "not in Running state" while provisioning.
This script retries until the sandbox responds, logging each attempt.

Exit 0: sandbox ready
Exit 1: timeout exceeded
"""
import os
import re
import sys
import time

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

ENDPOINT   = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
AGENT_NAME = os.environ.get("AGENT_NAME", "Founder")
VERSION    = os.environ.get("AGENT_VERSION", "1")
TIMEOUT    = int(os.environ.get("START_TIMEOUT", "300"))
INTERVAL   = 15

NOT_READY_PHRASES = [
    "not in running state",
    "not in started state",
    "try again",
    "provisioning",
    "starting",
]

CODE_PATTERN = re.compile(r"Error code: (\d+)")

print(f"Warming up: {AGENT_NAME} v{VERSION}")
print(f"Endpoint:   {ENDPOINT}")
print(f"Timeout:    {TIMEOUT}s  interval: {INTERVAL}s")
print("")

client = AIProjectClient(
    endpoint=ENDPOINT,
    credential=DefaultAzureCredential(),
)
openai_client = client.get_openai_client()

elapsed = 0
attempt = 0

while elapsed < TIMEOUT:
    attempt += 1
    print(f"[{elapsed:3d}s] Attempt {attempt} - pinging agent...")

    try:
        response = openai_client.responses.create(
            input=[{"role": "user", "content": "ping"}],
            extra_body={
                "agent_reference": {
                    "name":    AGENT_NAME,
                    "version": VERSION,
                    "type":    "agent_reference",
                }
            },
        )
        text = getattr(response, "output_text", None) or str(response)
        print(f"[{elapsed:3d}s] READY after {attempt} attempt(s)")
        print(f"           status:   200 OK")
        print(f"           response: {text[:200]}")
        sys.exit(0)

    except Exception as e:
        error_str = str(e)
        code_match = CODE_PATTERN.search(error_str)
        http_code = code_match.group(1) if code_match else "?"
        msg_lower = error_str.lower()

        if any(phrase in msg_lower for phrase in NOT_READY_PHRASES):
            print(f"[{elapsed:3d}s] NOT READY  status: HTTP {http_code}")
            print(f"           message: {error_str[:200]}")
        else:
            print(f"[{elapsed:3d}s] ERROR      status: HTTP {http_code}")
            print(f"           message: {error_str[:200]}")

        print(f"           retrying in {INTERVAL}s...")

    time.sleep(INTERVAL)
    elapsed += INTERVAL

print(f"::error::Sandbox not ready after {TIMEOUT}s ({attempt} attempts)")
sys.exit(1)
