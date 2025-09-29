"""
boardroom_repl_pro.py

Multi‑role LoRA REPL with:
- Shared global transcript
- Role‑specific private memories
- Parallel response volley
"""

import argparse
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

parser = argparse.ArgumentParser()
parser.add_argument("--base_model", type=str, required=True)
parser.add_argument("--adapter", action="append", help="name=path for each adapter")
parser.add_argument("--max_new_tokens", type=int, default=200)
args = parser.parse_args()

# Parse adapter mappings
adapters = {}
for apair in args.adapter:
    name, path = apair.split("=")
    adapters[name.strip()] = path.strip()

# Load base model & tokenizer
tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

base = AutoModelForCausalLM.from_pretrained(
    args.base_model, torch_dtype="auto", device_map="auto"
)

# Load first adapter
first_name, first_path = next(iter(adapters.items()))
model = PeftModel.from_pretrained(base, first_path)
model.set_adapter(first_name)

# Load remaining
for name, path in adapters.items():
    if name != first_name:
        model.load_adapter(path, adapter_name=name)

active = first_name
global_history = []        # All turns (role + text)
private_memories = {name: [] for name in adapters}

def generate(role, prompt):
    """Generate response for given role using its private + global context."""
    # Combine role's own memory with relevant context from global
    context = "\n".join(
        [f"[{r}] {t}" for r, t in private_memories[role]]
    ) + f"\n[{role}] {prompt}"
    inputs = tokenizer(context, return_tensors="pt").to(model.device)
    model.set_adapter(role)
    outputs = model.generate(**inputs, max_new_tokens=args.max_new_tokens)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

print(f"\nBoardroom REPL Pro — active: {active}")
print("Commands: /role <name>, /volley, /exit\n")

while True:
    try:
        user_input = input(f"[{active}] You: ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user_input:
        continue
    if user_input == "/exit":
        break
    if user_input.startswith("/role "):
        role_name = user_input.split(" ", 1)[1]
        if role_name in adapters:
            active = role_name
            print(f"Switched to {active}\n")
        else:
            print(f"No such role: {role_name}\n")
        continue
    if user_input == "/volley":
        msg = input("Volley prompt: ").strip()
        for role in adapters:
            resp = generate(role, msg)
            print(f"[{role}] {resp}\n")
            global_history.append((role, msg))
            global_history.append((role + "_AI", resp))
            private_memories[role].append(("User", msg))
            private_memories[role].append(("AI", resp))
        continue

    # Normal single-role exchange
    resp = generate(active, user_input)
    print(f"[{active}] AI: {resp}\n")
    global_history.append((active, user_input))
    global_history.append((active + "_AI", resp))
    private_memories[active].append(("User", user_input))
    private_memories[active].append(("AI", resp))