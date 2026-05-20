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
    from transformers import AutoModelForCausalLM
    from peft import PeftModel

    model = AutoModelForCausalLM.from_pretrained(
        base_model_name, torch_dtype="auto", device_map="auto"
    )
    peft_model = PeftModel(model)

    for name, path in adapters.items():
        peft_model.load_adapter(path, adapter_name=name)

    peft_model.set_adapter(active_adapter)
    return peft_model