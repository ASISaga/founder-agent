"""
founderops_trainer.py

Modular fine-tuning pipeline for a two-stage training strategy:
    Stage 1: Fine-tune on "golden batch" to imprint tone & schema.
    Stage 2: Resume from Stage 1 checkpoint, fine-tune lightly on full corpus.

Author: Shabeer Dewan founder-ops build
"""

import os
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    EarlyStoppingCallback
)

class FounderOpsFineTuner:
    """
    Base trainer class that handles:
      - Dataset loading (JSONL)
      - Tokenization
      - Trainer configuration & execution
    """

    def __init__(self, model_name, data_file, output_dir,
                 epochs=3, learning_rate=3e-5,
                 batch_size=2, grad_accum=8, warmup_ratio=0.05,
                 resume_from=None):
        self.model_name = model_name
        self.data_file = data_file
        self.output_dir = output_dir
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.grad_accum = grad_accum
        self.warmup_ratio = warmup_ratio
        self.resume_from = resume_from

        # Load tokenizer (from base model or checkpoint)
        self.tokenizer = AutoTokenizer.from_pretrained(
            resume_from if resume_from else model_name
        )
        self.tokenizer.pad_token = self.tokenizer.eos_token

    def load_and_tokenize(self):
        dataset = load_dataset("json", data_files=self.data_file)

        def tokenize_fn(batch):
            return self.tokenizer(
                batch["text"],
                truncation=True,
                max_length=2048
            )

        tokenized = dataset.map(
            tokenize_fn,
            batched=True,
            remove_columns=dataset["train"].column_names
        )
        return tokenized

    def train(self):
        tokenized_datasets = self.load_and_tokenize()

        # Load model
        model = AutoModelForCausalLM.from_pretrained(
            self.resume_from if self.resume_from else self.model_name
        )

        # Collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False
        )

        training_args = TrainingArguments(
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
            report_to="none"
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_datasets["train"],
            tokenizer=self.tokenizer,
            data_collator=data_collator,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=1)]
        )

        trainer.train(resume_from_checkpoint=bool(self.resume_from))
        trainer.save_model(self.output_dir)
        self.tokenizer.save_pretrained(self.output_dir)

class Stage1GoldenTrainer(FounderOpsFineTuner):
    """
    Stage 1 — Train from base model on golden batch dataset.
    """
    def __init__(self):
        super().__init__(
            model_name="meta-llama/Llama-3.1-8B-Instruct",
            data_file="founder_ops_50.jsonl",       # Golden batch
            output_dir="./llama3_1_8b_founderops_golden",
            epochs=5,
            learning_rate=3e-5,
            batch_size=2,
            grad_accum=8,
            warmup_ratio=0.05
        )

class Stage2ExpansionTrainer(FounderOpsFineTuner):
    """
    Stage 2 — Resume from Stage 1 checkpoint on the rest of the corpus.
    """
    def __init__(self):
        super().__init__(
            model_name="meta-llama/Llama-3.1-8B-Instruct",
            data_file="founder_ops_rest.jsonl",     # Full corpus minus golden
            output_dir="./llama3_1_8b_founderops_full",
            epochs=2,
            learning_rate=1e-5,   # Gentle updates
            batch_size=2,
            grad_accum=8,
            warmup_ratio=0.03,
            resume_from="./llama3_1_8b_founderops_golden"  # Stage 1 output dir
        )