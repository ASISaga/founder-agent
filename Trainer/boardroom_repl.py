"""
boardroom_repl.py

Run an interactive shell with multiple role adapters loaded.  
Switch active roles mid‑session, keep shared conversation history.

Example:
python boardroom_repl.py \
  --base_model meta-llama/Llama-3.1-8B-Instruct \
  --adapter founder_pg=./out/founder_stage1/adapters/founder_pg \
  --adapter founder_expansion=./out/founder_stage2/adapters/founder_expansion \
  --adapter investor_pg=./out/investor_stage1/adapters/investor_pg
"""

import argparse, sys
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

parser = argparse.ArgumentParser()
parser.add_argument("--base_model", type=str, required=True)
parser.add_argument("--adapter", action="append", help="name=path for each adapter")
parser.add_argument("--max_new_tokens", type=int, default=200)
args = parser.parse_args()

# Parse adapter definitions
adapters = {}
for apair in args.adapter:
    name, path = apair.split("=")
    adapters[name.strip()] = path.strip()

# Load base model and tokenizer
tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

base = AutoModelForCausalLM.from_pretrained(args.base_model, torch_dtype="auto", device_map="auto")

# Load first adapter
first_name, first_path = next(iter(adapters.items()))
model = PeftModel.from_pretrained(base, first_path)
model.set_adapter(first_name)

# Load remaining adapters
for name, path in adapters.items():
    if name != first_name:
        model.load_adapter(path, adapter_name=name)

# Active role
active = first_name
history = []

print(f"\nBoardroom REPL — active role: {active}\nType '/role <name>' to switch, '/exit' to quit.\n")

while True:
    try:
        user_input = input(f"[{active}] You: ").strip()
    except (EOFError, KeyboardInterrupt):
        break

    if not user_input:
        continue

    if user_input.lower() == "/exit":
        break

    if user_input.startswith("/role "):
        role_name = user_input.split(" ", 1)[1]
        if role_name in adapters:
            active = role_name
            model.set_adapter(active)
            print(f"Switched to role: {active}\n")
        else:
            print(f"No such role loaded: {role_name}\n")
        continue

    # Append to history and build prompt
    history.append((active, user_input))
    chat_context = "\n".join(f"[{r}] {t}" for r, t in history)
    inputs = tokenizer(chat_context, return_tensors="pt").to(model.device)

    outputs = model.generate(**inputs, max_new_tokens=args.max_new_tokens)
    response_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Print and record model output
    print(f"[{active}] AI: {response_text}\n")
    history.append((active + "_AI", response_text))