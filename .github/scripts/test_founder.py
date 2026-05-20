"""
Integration test for FounderAgent hosted in Foundry Agent Service.

Invokes the agent with three test messages and validates:
  - Response is non-empty
  - Response ends with exactly one valid routing tag
  - Routing tag matches the expected tag for the input topic
  - No invalid tags present (e.g. HANDBACK which is specialist-only)

Exit code 0: all tests passed
Exit code 1: one or more tests failed
"""
import os
import re
import sys

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

ENDPOINT   = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
AGENT_NAME = os.environ.get("AGENT_NAME", "Founder")
VERSION    = os.environ.get("AGENT_VERSION", "1")

VALID_TAGS   = {"[ROUTE:CFO]", "[ROUTE:CMO]", "[COMPLETE]", "[HANDBACK]"}
INVALID_TAGS = {"[HANDBACK]"}  # orchestrators must never emit this
TAG_PATTERN  = re.compile(r"\[(ROUTE:CFO|ROUTE:CMO|COMPLETE|HANDBACK)\]", re.IGNORECASE)

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


def run_tests():
    print(f"Endpoint:   {ENDPOINT}")
    print(f"Agent:      {AGENT_NAME} v{VERSION}")
    print("")

    client = AIProjectClient(
        endpoint=ENDPOINT,
        credential=DefaultAzureCredential(),
    )
    openai_client = client.get_openai_client()

    passed = 0
    failed = 0
    results = []

    for i, test in enumerate(TESTS, 1):
        print(f"[{i}/{len(TESTS)}] {test['name']}")
        print(f"  Input: {test['input']}")

        try:
            response = openai_client.responses.create(
                input=[{"role": "user", "content": test["input"]}],
                extra_body={
                    "agent_reference": {
                        "name":    AGENT_NAME,
                        "version": VERSION,
                        "type":    "agent_reference",
                    }
                },
            )
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

        print("")

    # Summary
    print(f"Results: {passed} passed, {failed} failed out of {len(TESTS)} tests")

    # Write GitHub Actions step summary
    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if github_step_summary:
        with open(github_step_summary, "a") as fh:
            fh.write(f"## Founder Agent - Integration Test Results\n\n")
            fh.write(f"| Test | Status | Tag |\n")
            fh.write(f"|---|---|---|\n")
            for r in results:
                status = r["status"]
                tag    = r.get("tag", "n/a")
                errors = "; ".join(r.get("errors", [])) or r.get("error", "")
                detail = f" ({errors})" if errors else ""
                fh.write(f"| {r['test']} | {status}{detail} | {tag} |\n")
            fh.write(f"\n**{passed} passed, {failed} failed**\n")

    # Write GitHub output
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"passed={passed}\n")
            fh.write(f"failed={failed}\n")

    return failed


if __name__ == "__main__":
    sys.exit(run_tests())
