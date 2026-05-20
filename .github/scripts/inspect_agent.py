"""
Diagnostic script - prints raw agent and version attributes from Foundry.
Uses multiple introspection methods to handle SDK objects with __slots__,
properties, or custom attribute storage.
"""
import os
import json
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

ENDPOINT   = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
AGENT_NAME = os.environ.get("AGENT_NAME", "Founder")
VERSION    = os.environ.get("AGENT_VERSION", "1")


def inspect_obj(label, obj):
    print(f"\n=== {label} ===")
    print(f"  type: {type(obj)}")
    print(f"  repr: {repr(obj)}")

    # Try vars()
    try:
        d = vars(obj)
        if d:
            print("  vars():")
            for k, v in sorted(d.items()):
                print(f"    {k}: {v}")
        else:
            print("  vars(): empty")
    except TypeError:
        print("  vars(): not supported")

    # Try __dict__
    try:
        d = obj.__dict__
        if d:
            print("  __dict__:")
            for k, v in sorted(d.items()):
                print(f"    {k}: {v}")
    except AttributeError:
        pass

    # Try dir() - all public attributes
    print("  public attributes via dir():")
    for attr in sorted(dir(obj)):
        if not attr.startswith("_"):
            try:
                val = getattr(obj, attr)
                if not callable(val):
                    print(f"    {attr}: {val}")
            except Exception:
                pass

    # Try JSON serialization
    try:
        print(f"  as_dict(): {obj.as_dict()}")
    except AttributeError:
        pass

    try:
        print(f"  model_dump(): {obj.model_dump()}")
    except AttributeError:
        pass

    try:
        print(f"  to_dict(): {obj.to_dict()}")
    except AttributeError:
        pass

    try:
        import json
        print(f"  json: {json.dumps(obj, default=str)}")
    except Exception:
        pass


client = AIProjectClient(
    endpoint=ENDPOINT,
    credential=DefaultAzureCredential(),
    allow_preview=True,
)

print(f"Endpoint: {ENDPOINT}")
print(f"Agent: {AGENT_NAME} v{VERSION}")

try:
    agent = client.agents.get(agent_name=AGENT_NAME)
    inspect_obj(f"Agent: {AGENT_NAME}", agent)
except Exception as e:
    print(f"ERROR getting agent: {e}")

try:
    ver = client.agents.get_version(agent_name=AGENT_NAME, agent_version=VERSION)
    inspect_obj(f"Version: {AGENT_NAME} v{VERSION}", ver)
except Exception as e:
    print(f"ERROR getting version: {e}")
