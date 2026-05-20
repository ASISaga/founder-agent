"""
train_role.py

CLI launcher for multi_role_lora_trainer.
Usage examples:

# Stage 1 (Golden batch)
python train_role.py \
  --stage 1 \
  --role founder \
  --adapter_name founder_pg \
  --data_file datasets/founder_pg.json \
  --output_dir ./out/founder_stage1

# Stage 2 (Expansion)
python train_role.py \
  --stage 2 \
  --role founder \
  --golden_adapter_name founder_pg \
  --golden_adapter_path ./out/founder_stage1/adapters/founder_pg \
  --new_adapter_name founder_expansion \
  --data_file datasets/founder_expansion.json \
  --output_dir ./out/founder_stage2
"""

import argparse
from multi_role_lora_trainer import Stage1RoleTrainer, Stage2RoleTrainer

parser = argparse.ArgumentParser()
parser.add_argument("--stage", type=int, choices=[1, 2], required=True)
parser.add_argument("--role", type=str, required=True)
parser.add_argument("--model_name", type=str, default="meta-llama/Llama-2-7b-hf")
parser.add_argument("--adapter_name", type=str)
parser.add_argument("--golden_adapter_name", type=str)
parser.add_argument("--golden_adapter_path", type=str)
parser.add_argument("--new_adapter_name", type=str)
parser.add_argument("--data_file", type=str, required=True)
parser.add_argument("--output_dir", type=str, required=True)
parser.add_argument("--epochs", type=int, default=3)
parser.add_argument("--learning_rate", type=float, default=2e-4)
parser.add_argument("--batch_size", type=int, default=2)
parser.add_argument("--grad_accum", type=int, default=4)
parser.add_argument("--warmup_ratio", type=float, default=0.1)

args = parser.parse_args()

if args.stage == 1:
    trainer = Stage1RoleTrainer(
        adapter_name=args.adapter_name or f"{args.role}_pg",
        model_name=args.model_name,
        data_file=args.data_file,
        output_dir=args.output_dir,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        warmup_ratio=args.warmup_ratio
    )
elif args.stage == 2:
    trainer = Stage2RoleTrainer(
        golden_adapter_name=args.golden_adapter_name or f"{args.role}_pg",
        golden_adapter_path=args.golden_adapter_path,
        new_adapter_name=args.new_adapter_name or f"{args.role}_expansion",
        model_name=args.model_name,
        data_file=args.data_file,
        output_dir=args.output_dir,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        warmup_ratio=args.warmup_ratio
    )

trainer.train()