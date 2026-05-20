"""
Integration test for FounderAgent hosted in Foundry Agent Service.

The agent uses scale-to-zero. After 15 minutes idle the container is
deprovisioned. The first request triggers a cold start which Foundry
handles transparently -- the invocation blocks until the container is
ready. This script retries on cold-start errors to handle the case
where Foundry returns an explicit "not ready" response.

Status field: ver.status == AgentVersionStatus.ACTIVE (not "Started"/"Running")

Exit code 0: all tests passed
Exit code 1: one or more tests failed
"""
import os
import re
import sys
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AgentVersionStatus
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential

ENDPOINT     = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
AGENT_NAME   = os.environ.get("AGENT_NAME", "Founder")
VERSION      = os.environ.get("AGENT_VERSION", "1")
COLD_START_TIMEOUT  = int(os.environ.get("COLD_START_TIMEOUT", "120"))
COLD_START_INTERVAL = 10

TAG_PATTERN  = re.compile(r"\[(ROUTE:CFO|ROUTE:CMO|COMPLETE|HANDBACK)\]", re.IGNORECASE)
INVALID_TAGS = {"[HANDBACK]"}

COLD_START_PHRASES = [
    "not in running state",
    "not in started state",
    "not in active state",
    "starting",
    "provisioning",
    "cold start",
    "try again",
]

TESTS = [
    {
        "name":     "Financial topic -> ROUTE:CFO",
        "input":    "What should our burn rate strategy be for the next 18 months?",
        "expected": "[ROUTE:CFO]",
    },
    {
        "name":     "Marketing topic -> ROUTE:CMO",
        "input":    "How should we position ASI Saga to enterprise customers?",
        "expected": "[ROUTE:CMO]",
    },
    {
        "name":     "Resolved topic -> COMPLETE",
        "input":    "The agenda is fully resolved and all decisions are made. Confirm completion.",
        "expected": "[COMPLETE]",
    },
]


def extract_tag(text):
    tail = text[-200:] if len(text) > 200 else text
    match = TAG_PATTERN.search(tail)
    return f"[{match.group(1).upper()}]" if match else None


def is_cold_start_error(e):
    msg = str(e).lower()
    return any(phrase in msg for phrase in COLD_START_PHRASES)


def check_agent_active(client):
    """Verify agent status is ACTIVE before running tests."""
    try:
        ver = client.agents.get_version(
            agent_name=AGENT_NAME,
            agent_version=VERSION,
        )
        status = ver.status
        print(f"Agent status: {status}")
        if status == AgentVersionStatus.ACTIVE:
            print("Agent is ACTIVE - proceeding with tests.")
            return True
        else:
            print(f"::warning::Agent status is {status} - tests may fail.")
            return True  # Still attempt tests
    except Exception as e:
        print(f"::warning::Could not verify agent status: {e}")
        return True  # Still attempt tests


def invoke_with_retry(openai_client, input_text):
    """Invoke agent, retrying on cold-start errors until timeout."""
    elapsed = 0
    while True:
        try:
            return openai_client.responses.create(
                input=[{"role": "user", "content": input_text}],
                extra_body={
                    "agent_reference": {
                        "name":    AGENT_NAME,
                        "version": VERSION,
                        "type":    "agent_reference",
                    }
                },
            )
        except Exception as e:
            if is_cold_start_error(e) and elapsed < COLD_START_TIMEOUT:
                print(f"  Cold start ({elapsed}s) - retrying in {COLD_START_INTERVAL}s: {e}")
                time.sleep(COLD_START_INTERVAL)
                elapsed += COLD_START_INTERVAL
            else:
                raise


def run_tests(openai_client):
    passed = 0
    failed = 0
    results = []

    for i, test in enumerate(TESTS, 1):
        print(f"\n[{i}/{len(TESTS)}] {test['name']}")
        print(f"  Input: {test['input']}")

        try:
            response = invoke_with_retry(openai_client, test["input"])
            text = response.output_text or ""
            print(f"  Response ({len(text)} chars): {text[:300]}{'...' if len(text) > 300 else ''}")

            tag = extract_tag(text)
            print(f"  Detected tag: {tag}")

            errors = []
            if not text.strip():
                errors.append("EMPTY response")
            if tag is None:
                errors.append("No routing tag found in response tail")
            if tag in INVALID_TAGS:
                errors.append(f"Invalid tag for orchestrator: {tag}")
            if test["expected"] and tag != test["expected"]:
                errors.append(f"Expected {test['expected']}, got {tag}")

            if errors:
                print(f"  FAIL: {'; '.join(errors)}")
                failed += 1
                results.append({"test": test["name"], "status": "FAIL", "errors": errors, "tag": tag})
            else:
                print(f"  PASS")
                passed += 1
                results.append({"test": test["name"], "status": "PASS", "tag": tag})

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
            results.append({"test": test["name"], "status": "ERROR", "error": str(e)})

    return passed, failed, results


def write_outputs(passed, failed, results):
    summary = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary:
        with open(summary, "a") as fh:
            fh.write("## Founder Agent - Integration Test Results\n\n")
            fh.write("| Test | Status | Tag |\n")
            fh.write("|---|---|---|\n")
            for r in results:
                tag    = r.get("tag", "n/a")
                errors = "; ".join(r.get("errors", [])) or r.get("error", "")
                detail = f" ({errors})" if errors else ""
                fh.write(f"| {r['test']} | {r['status']}{detail} | {tag} |\n")
            fh.write(f"\n**{passed} passed, {failed} failed**\n")

    output = os.environ.get("GITHUB_OUTPUT", "")
    if output:
        with open(output, "a") as fh:
            fh.write(f"passed={passed}\n")
            fh.write(f"failed={failed}\n")


if __name__ == "__main__":
    print(f"Endpoint:   {ENDPOINT}")
    print(f"Agent:      {AGENT_NAME} v{VERSION}")
    print(f"Cold start timeout: {COLD_START_TIMEOUT}s")
    print("")

    client = AIProjectClient(
        endpoint=ENDPOINT,
        credential=DefaultAzureCredential(),
    )

    check_agent_active(client)

    openai_client = client.get_openai_client()
    passed, failed, results = run_tests(openai_client)

    print(f"\nResults: {passed} passed, {failed} failed out of {len(TESTS)} tests")
    write_outputs(passed, failed, results)

    sys.exit(0 if failed == 0 else 1)
