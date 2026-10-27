#!/usr/bin/env python3
# OMNIGENESIS-Ω Step 44: Merge HuggingFace LoRA, Push to Hub (omnigenesis-lab) & Convert to Ollama GGUF
import argparse
from pathlib import Path
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

def merge_and_export(base_model: str, lora_dir: str, merged_dir: str, hf_repo: str = '') -> None:
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=torch.float16, device_map='cpu')
    model = PeftModel.from_pretrained(base, lora_dir)
    merged = model.merge_and_unload()
    Path(merged_dir).mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(merged_dir, safe_serialization=True)
    tokenizer.save_pretrained(merged_dir)
    if hf_repo:
        merged.push_to_hub(hf_repo)
        tokenizer.push_to_hub(hf_repo)
    modelfile_custom = Path(merged_dir) / 'Modelfile.finetuned'
    modelfile_custom.write_text(
        'FROM ./omnigenesis-omega-q4_k_m.gguf\nPARAMETER temperature 0.2\nPARAMETER num_ctx 16384\n',
        encoding='utf-8',
    )

if __name__ == '__main__':
    print('Ready to merge deepseek-ai/DeepSeek-R1-Distill-Qwen-7B -> omnigenesis-omega-q4_k_m.gguf')
