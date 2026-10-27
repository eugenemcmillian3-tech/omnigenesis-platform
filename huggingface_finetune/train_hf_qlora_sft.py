#!/usr/bin/env python3
# OMNIGENESIS-Ω Step 42: HuggingFace 4-Bit QLoRA SFT Trainer (deepseek-ai/DeepSeek-R1-Distill-Qwen-7B)
# Usage: pip install -U torch transformers datasets peft trl bitsandbytes accelerate
import argparse
import torch
from datasets import load_dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

def main() -> None:
    parser = argparse.ArgumentParser(description='OMNIGENESIS-Ω 4-bit QLoRA SFT Trainer')
    parser.add_argument('--base_model', type=str, default='deepseek-ai/DeepSeek-R1-Distill-Qwen-7B')
    parser.add_argument('--dataset', type=str, default='omnigenesis_5th_paradigm_hf_dataset.jsonl')
    parser.add_argument('--output_dir', type=str, default='./checkpoints/omnigenesis-omega-qlora')
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--lr', type=float, default=2e-4)
    args = parser.parse_args()

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type='nf4',
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, quantization_config=bnb_config, device_map='auto', trust_remote_code=True
    )
    model = prepare_model_for_kbit_training(model)
    peft_config = LoraConfig(
        r=32, lora_alpha=64, lora_dropout=0.05, bias='none', task_type='CAUSAL_LM',
        target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
    )
    dataset = load_dataset('json', data_files=args.dataset, split='train')
    sft_config = SFTConfig(
        output_dir=args.output_dir, num_train_epochs=args.epochs,
        per_device_train_batch_size=2, gradient_accumulation_steps=4,
        learning_rate=args.lr, bf16=True, logging_steps=5, max_seq_length=4096,
    )
    trainer = SFTTrainer(model=model, train_dataset=dataset, peft_config=peft_config, processing_class=tokenizer, args=sft_config)
    trainer.train()
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

if __name__ == '__main__':
    main()
