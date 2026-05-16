"""
multi_role_lora_trainer.py

Multi-role, two-stage LoRA fine-tuning for Llama-family models.

Roles:
    - Founder
    - Investor
    - Marketeer
    - ...extend with your own

Stages:
    - Stage 1: Golden batch imprint
    - Stage 2: Expansion pass (light LR, fewer epochs)

Adapters:
    - One per Stage per Role (e.g. founder_pg, founder_expansion)
    - Load/switch multiple adapters at inference
"""

import os
from typing import Optional, List, Dict
from datasets import load_dataset, DatasetDict
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    EarlyStoppingCallback
)
from peft import (
    LoraConfig,
    TaskType,
    get_peft_model,
    PeftModel
)

DEFAULT_TARGET_MODULES_LLAMA = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj"
]

# -------------------------
# Utility: Ensure `text` field exists
# -------------------------
def ensure_text_field(dataset: DatasetDict) -> DatasetDict:
    def format_record(ex):
        if "text" in ex and ex["text"]:
            return {"text": ex["text"]}

        prompt_parts, completion_parts = [], []
        pid = ex.get("principle_id", "UNKNOWN")
        prompt_parts.append(f"Principle: {pid}")

        for field in [
            "market_validation_signal", "risk_flag", "scrappy_tactic", "scalability_limit",
            "MVP_definition", "blocker_removal", "time_to_market_metric", "runway_calc",
            "cost_control", "market_size", "adjacent_opportunity", "entry_risk", "impact_metric",
            "distraction_flag", "focus_index", "competitor_noise_filter", "core_progress",
            "early_adopter_profile", "tight_loop_feedback", "user_interview_exemplar", "pain_point_map"
        ]:
            if ex.get(field):
                prompt_parts.append(f"{field.replace('_',' ').capitalize()}: {ex[field]}")

        for field in [
            "founder_action", "next_move", "priority_shift", "growth_trigger",
            "revenue_path", "insight_derivation"
        ]:
            if ex.get(field):
                completion_parts.append(f"{field.replace('_',' ').capitalize()}: {ex[field]}")

        prompt = "\n".join(prompt_parts)
        completion = "\n".join(completion_parts) if completion_parts else "Action: Provide the most impactful next step."

        return {"text": f"{prompt}\n###\n{completion}"}

    for split in dataset.keys():
        dataset[split] = dataset[split].map(format_record)

    return dataset

# -------------------------
# Base LoRA Trainer Class
# -------------------------
class BaseLoRATrainer:
    def __init__(
        self,
        model_name: str,
        data_file: str,
        output_dir: str,
        epochs: int,
        learning_rate: float,
        batch_size: int,
        grad_accum: int,
        warmup_ratio: float,
        eval_ratio: float = 0.2,
        seed: int = 42
    ):
        self.model_name = model_name
        self.data_file = data_file
        self.output_dir = output_dir
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.grad_accum = grad_accum
        self.warmup_ratio = warmup_ratio
        self.eval_ratio = eval_ratio
        self.seed = seed

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, use_fast=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = None

    def load_dataset(self) -> DatasetDict:
        raw = load_dataset("json", data_files=self.data_file)
        if "validation" not in raw:
            split = raw["train"].train_test_split(test_size=self.eval_ratio, seed=self.seed)
            ds = DatasetDict(train=split["train"], validation=split["test"])
        else:
            ds = raw
        return ensure_text_field(ds)

    def tokenize_dataset(self, ds: DatasetDict) -> DatasetDict:
        def tok(batch):
            return self.tokenizer(batch["text"], truncation=True, max_length=2048)
        cols = ds["train"].column_names
        return DatasetDict(
            train=ds["train"].map(tok, batched=True, remove_columns=cols),
            validation=ds["validation"].map(tok, batched=True, remove_columns=cols)
        )

    def create_lora_config(self, r=16, alpha=32, dropout=0.05) -> LoraConfig:
        return LoraConfig(
            r=r,
            lora_alpha=alpha,
            lora_dropout=dropout,
            task_type=TaskType.CAUSAL_LM,
            target_modules=DEFAULT_TARGET_MODULES_LLAMA
        )

    def build_model_with_adapter(self, adapter_name: str, lora_cfg: LoraConfig, resume_from: Optional[str] = None):
        base_model_path = resume_from if resume_from else self.model_name
        base = AutoModelForCausalLM.from_pretrained(base_model_path, torch_dtype="auto", device_map="auto")
        self.model = get_peft_model(base, lora_cfg, adapter_name=adapter_name)
        self.model.set_adapter(adapter_name)

    def load_existing_adapter(self, adapter_name: str, adapter_path: str):
        self.model.load_adapter(adapter_path, adapter_name=adapter_name)

    def build_trainer(self, tokenized: DatasetDict) -> Trainer:
        args = TrainingArguments(
            output_dir=self.output_dir,
            overwrite_output_dir=True,
            num_train_epochs=self.epochs,
            per_device_train_batch_size=self.batch_size,
            gradient_accumulation_steps=self.grad_accum,
            learning_rate=self.learning_rate,
            warmup_ratio=self.warmup_ratio,
            fp16=True,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=2,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            logging_dir=os.path.join(self.output_dir, "logs"),
            logging_steps=10,
            report_to="none",
            seed=self.seed
        )
        collator = DataCollatorForLanguageModeling(tokenizer=self.tokenizer, mlm=False)
        return Trainer(
            model=self.model,
            args=args,
            train_dataset=tokenized["train"],
            eval_dataset=tokenized["validation"],
            tokenizer=self.tokenizer,
            data_collator=collator,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=1)]
        )

    def train(self):
        ds = self.load_dataset()
        tokenized = self.tokenize_dataset(ds)
        trainer = self.build_trainer(tokenized)
        trainer.train()
        trainer.save_model(self.output_dir)
        self.tokenizer.save_pretrained(self.output_dir)

# -------------------------
# Stage‑1 Trainer
# -------------------------
class Stage1RoleTrainer(BaseLoRATrainer):
    def __init__(self, adapter_name: str, **kwargs):
        super().__init__(**kwargs)
        self.adapter_name = adapter_name

    def train(self):
        cfg = self.create_lora_config()
        self.build_model_with_adapter(self.adapter_name, cfg)
        super().train()
        adapter_dir = os.path.join(self.output_dir, "adapters", self.adapter_name)
        os.makedirs(adapter_dir, exist_ok=True)
        self.model.save_pretrained(adapter_dir)

# -------------------------
# Stage‑2 Trainer
# -------------------------
class Stage2RoleTrainer(BaseLoRATrainer):
    def __init__(self, golden_adapter_name: str, golden_adapter_path: str, new_adapter_name: str, **kwargs):
        super().__init__(**kwargs)
        self.golden_adapter_name = golden_adapter_name
        self.golden_adapter_path = golden_adapter_path
        self.new_adapter_name = new_adapter_name

    def train(self):
        cfg = self.create_lora_config()
        # Start from base, load golden adapter
        base = AutoModelForCausalLM.from_pretrained(self.model_name, torch_dtype="auto", device_map="auto")
        self.model = get_peft_model(base, cfg, adapter_name=self.new_adapter_name)
        self.model.load_adapter(self.golden_adapter_path, adapter_name=self.golden_adapter_name)
        self.model.set_adapter(self.new_adapter_name)
        super().train()
        adapter_dir = os.path.join(self.output_dir, "adapters", self.new_adapter_name)
        os.makedirs(adapter_dir, exist_ok=True)
        self.model.save_pretrained(adapter_dir)

# -------------------------
# Multi‑adapter loader
# -------------------------
def load_with_adapters(
    base_model_name: str,
    adapters: Dict[str, str],
    active_adapter: str
) -> PeftModel:
    """
    Load base model and multiple LoRA adapters, set active one.

    Args:
        base_model_name: Hugging Face model hub id or local dir
        adapters: { adapter_name: adapter_path }
        active_adapter: Which adapter_name to activate
    """
    base = AutoModelForCausalLM.from_pretrained(
        base_model_name, torch_dtype="auto", device_map="auto"
    )
    first_name, first_path = next(iter(adapters.items()))
    model = PeftModel.from_pretrained(base, first_path, adapter_name=first_name)
    for name, path in list(adapters.items())[1:]:
        model.load_adapter(path, adapter_name=name)
    model.set_adapter(active_adapter)
    return model