"""
inference_role.py

Usage examples:

# Run prompt through a specific role/stage adapter
python inference_role.py \
  --base_model meta-llama/Llama-3.1-8B-Instruct \
  --adapter founder_pg=./out/founder_stage1/adapters/founder_pg \
  --adapter founder_expansion=./out/founder_stage2/adapters/founder_expansion \
  --active founder_pg \
  --prompt "Evaluate this founder's plan to enter a saturated SaaS market."

# Switch to investor role
python inference_role.py \
  --base_model meta-llama/Llama-3.1-8B-Instruct \
  --adapter investor_pg=./out/investor_stage1/adapters/investor_pg \
  --adapter investor_expansion=./out/investor_stage2/adapters/investor_expansion \
  --active investor_expansion \
  --prompt "Assess this pitch deck's strengths and weaknesses."
"""

import argparse
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

parser = argparse.ArgumentParser()
parser.add_argument("--base_model", type=str, required=True, help="Base HF model or dir")
parser.add_argument("--adapter", action="append", help="name=path for each adapter to load")
parser.add_argument("--active", type=str, required=True, help="Adapter name to set active")
parser.add_argument("--prompt", type=str, required=True, help="Prompt to run")
parser.add_argument("--max_new_tokens", type=int, default=200)
args = parser.parse_args()

# Parse adapters into dict
adapters = {}
for apair in args.adapter:
    name, path = apair.split("=")
    adapters[name.strip()] = path.strip()

# Load base model & tokenizer
tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

base = AutoModelForCausalLM.from_pretrained(args.base_model, torch_dtype="auto", device_map="auto")

# Load first adapter
first_name, first_path = next(iter(adapters.items()))
model = PeftModel.from_pretrained(base, first_path)
model.set_adapter(first_name)

# Load remaining adapters
for name, path in list(adapters.items())[1:]:
    model.load_adapter(path, adapter_name=name)

# Set active adapter
model.set_adapter(args.active)

# Tokenize prompt
inputs = tokenizer(args.prompt, return_tensors="pt").to(model.device)

# Generate
outputs = model.generate(**inputs, max_new_tokens=args.max_new_tokens)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))