if __name__ == "__main__":
    # ===== Stage 1: Golden batch =====
    stage1 = Stage1RoleTrainer(
        adapter_name="founder_pg",
        model_name="meta-llama/Llama-2-7b-hf",
        data_file="datasets/founder_pg.json",
        output_dir="./out/founder_stage1",
        epochs=3,
        learning_rate=2e-4,
        batch_size=2,
        grad_accum=4,
        warmup_ratio=0.1
    )
    stage1.train()

    # ===== Stage 2: Expansion batch =====
    stage2 = Stage2RoleTrainer(
        golden_adapter_name="founder_pg",
        golden_adapter_path="./out/founder_stage1/adapters/founder_pg",
        new_adapter_name="founder_expansion",
        model_name="meta-llama/Llama-2-7b-hf",
        data_file="datasets/founder_expansion.json",
        output_dir="./out/founder_stage2",
        epochs=2,
        learning_rate=1e-4,
        batch_size=2,
        grad_accum=4,
        warmup_ratio=0.05
    )
    stage2.train()

    # ===== Inference: Multi‑adapter load =====
    adapters = {
        "founder_pg": "./out/founder_stage1/adapters/founder_pg",
        "founder_expansion": "./out/founder_stage2/adapters/founder_expansion"
    }
    model = load_with_adapters(
        base_model_name="meta-llama/Llama-2-7b-hf",
        adapters=adapters,
        active_adapter="founder_expansion"
    )