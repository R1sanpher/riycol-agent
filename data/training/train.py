"""
riycol training pipeline
========================
Usage: python data/training/train.py [command]

Commands:
  prepare    Export data from database and split into train/val/test
  stats      Show training data statistics
  validate   Validate dataset format and quality

This pipeline prepares data for fine-tuning Qwen2.5 models.
"""

import sys, os, json, time, random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def ensure_dirs():
    exports_dir = Path(__file__).parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return exports_dir, output_dir


def cmd_stats():
    """Show training data statistics"""
    from core.db import DB
    stats = DB.stats()
    print("=" * 50)
    print("  Training Data Statistics")
    print("=" * 50)
    print(f"  Messages:    {stats['messages']}")
    print(f"  Sessions:    {stats['sessions']}")
    print(f"  Samples:     {stats['samples']}")
    print(f"  Documents:   {stats['docs']}")

    # Count by source
    rows = DB.conn.execute(
        "SELECT source, COUNT(*) as cnt FROM training_samples GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    if rows:
        print(f"\n  By source:")
        for r in rows:
            print(f"    {r['source'] or 'unknown'}: {r['cnt']}")

    # Count by dataset
    rows = DB.conn.execute(
        "SELECT dataset, COUNT(*) as cnt FROM training_samples GROUP BY dataset ORDER BY cnt DESC"
    ).fetchall()
    if rows:
        print(f"\n  By dataset:")
        for r in rows:
            print(f"    {r['dataset']}: {r['cnt']}")


def cmd_prepare():
    """Export training data from DB and split into train/val/test"""
    from core.db import DB
    from core.config import CFG

    samples = DB.get_samples('all', limit=50000, min_score=0.0)
    if not samples:
        print("  No training samples found. Collect data first by running the server.")
        return

    random.seed(42)
    random.shuffle(samples)

    n = len(samples)
    base_name = 'riycol_' + time.strftime('%Y%m%d_%H%M%S')
    exports_dir, _ = ensure_dirs()

    splits = [
        ('train', 0, int(n * 0.8)),
        ('val', int(n * 0.8), int(n * 0.9)),
        ('test', int(n * 0.9), n),
    ]

    print(f"  Total samples: {n}")
    print(f"  Exporting to: {exports_dir}")
    print()

    for split_name, i, j in splits:
        chunk = samples[i:j]
        if not chunk:
            continue
        path = exports_dir / f'{base_name}_{split_name}.jsonl'
        with open(path, 'w', encoding='utf-8') as f:
            for s in chunk:
                record = {
                    'instruction': s['instruction'],
                    'output': s['output'],
                    'source': s.get('source', ''),
                    'quality': s.get('quality', 1.0),
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(f"  [{split_name:5}] {len(chunk):6d} samples -> {path.name}")

    print(f"\n  Done! Use these files for fine-tuning.")


def cmd_validate():
    """Validate exported JSONL datasets"""
    exports_dir, _ = ensure_dirs()
    jsonl_files = list(exports_dir.glob("*.jsonl"))

    if not jsonl_files:
        print("  No exported JSONL files found in data/training/exports/")
        return

    for fp in sorted(jsonl_files):
        errors = []
        total = 0
        empty_instructions = 0
        empty_outputs = 0
        with open(fp, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                total += 1
                try:
                    data = json.loads(line)
                    if not isinstance(data, dict):
                        errors.append(f"  Line {i}: not a dict")
                    elif 'instruction' not in data:
                        errors.append(f"  Line {i}: missing 'instruction'")
                    elif 'output' not in data:
                        errors.append(f"  Line {i}: missing 'output'")
                    else:
                        if not data['instruction'].strip():
                            empty_instructions += 1
                        if not data['output'].strip():
                            empty_outputs += 1
                except json.JSONDecodeError:
                    errors.append(f"  Line {i}: invalid JSON")

        print(f"  {fp.name}:")
        print(f"    Total lines:   {total}")
        if empty_instructions:
            print(f"    WARN: {empty_instructions} empty instructions")
        if empty_outputs:
            print(f"    WARN: {empty_outputs} empty outputs")
        if errors:
            print(f"    ERRORS ({len(errors)}):")
            for e in errors[:5]:
                print(f"      {e}")
            if len(errors) > 5:
                print(f"      ... and {len(errors) - 5} more")
        else:
            print(f"    Valid: OK")


def cmd_convert():
    """Convert to Alpaca/ShareGPT format for common training frameworks"""
    from core.config import CFG
    exports_dir, output_dir = ensure_dirs()

    all_samples = []
    for fp in sorted(exports_dir.glob("*.jsonl")):
        with open(fp, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                instruction = data.get('instruction', '')
                output = data.get('output', '')
                if instruction and output:
                    all_samples.append({'instruction': instruction, 'output': output})

    if not all_samples:
        print("  No samples found to convert.")
        return

    random.seed(42)
    random.shuffle(all_samples)
    n = len(all_samples)

    # Alpaca format
    alpaca_path = output_dir / 'alpaca_format.json'
    alpaca_data = []
    for s in all_samples:
        alpaca_data.append({
            'instruction': s['instruction'],
            'input': '',
            'output': s['output'],
        })
    with open(alpaca_path, 'w', encoding='utf-8') as f:
        json.dump(alpaca_data, f, ensure_ascii=False, indent=2)
    print(f"  Alpaca format: {len(alpaca_data)} samples -> {alpaca_path.name}")

    # ShareGPT format (for axolotl, LLaMA-Factory, etc.)
    sharegpt_path = output_dir / 'sharegpt_format.jsonl'
    with open(sharegpt_path, 'w', encoding='utf-8') as f:
        for s in all_samples:
            conversation = {
                'conversations': [
                    {'from': 'human', 'value': s['instruction']},
                    {'from': 'gpt', 'value': s['output']},
                ]
            }
            f.write(json.dumps(conversation, ensure_ascii=False) + '\n')
    print(f"  ShareGPT format: {len(all_samples)} samples -> {sharegpt_path.name}")

    print(f"\n  Total converted: {n} samples")
    print(f"  Output directory: {output_dir}")


def cmd_clean():
    """Deduplicate and quality-filter exported JSONL files"""
    exports_dir, _ = ensure_dirs()
    jsonl_files = [f for f in exports_dir.glob("*.jsonl") if "_cleaned" not in f.stem]
    if not jsonl_files:
        print("  No JSONL files to clean.")
        return

    for fp in sorted(jsonl_files):
        seen = set()
        cleaned = []
        removed_dup = 0
        removed_short = 0
        removed_lowq = 0

        with open(fp, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                inst = data.get('instruction', '').strip()
                out = data.get('output', '').strip()
                quality = data.get('quality', 1.0)

                # Dedup by instruction hash
                key = inst[:100].lower()
                if key in seen:
                    removed_dup += 1
                    continue
                seen.add(key)

                # Length filter
                if len(inst) < 5 or len(out) < 10:
                    removed_short += 1
                    continue

                # Quality filter
                if quality < 0.3:
                    removed_lowq += 1
                    continue

                cleaned.append(data)

        # Overwrite with cleaned version
        clean_path = fp.with_name(fp.stem + '_cleaned.jsonl')
        with open(clean_path, 'w', encoding='utf-8') as f:
            for item in cleaned:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        print(f"  {fp.name}: {len(cleaned)} kept "
              f"(-{removed_dup} dup, -{removed_short} short, -{removed_lowq} lowq)")
    print(f"\n  Cleaned files saved with '_cleaned' suffix.")


def cmd_config():
    """Generate training config files for popular frameworks."""
    _, output_dir = ensure_dirs()
    from core.config import CFG

    # LLaMA-Factory config
    llama_factory = {
        "model_name_or_path": os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"),
        "stage": "sft",
        "do_train": True,
        "finetuning_type": "lora",
        "lora_target": "all",
        "dataset": "riycol_dataset",
        "template": "qwen",
        "cutoff_len": CFG.N_CTX,
        "output_dir": str(output_dir / "llama_factory_output"),
        "per_device_train_batch_size": 2,
        "gradient_accumulation_steps": 4,
        "lr_scheduler_type": "cosine",
        "logging_steps": 10,
        "save_steps": 500,
        "learning_rate": 5e-5,
        "num_train_epochs": 3,
        "warmup_ratio": 0.1,
        "bf16": True,
        "ddp_timeout": 180000000,
    }
    config_path = output_dir / "llama_factory_config.yaml"
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write("# LLaMA-Factory training config for riycol-agent\n")
        f.write(f"# Usage: llamafactory-cli train {config_path}\n\n")
        for k, v in llama_factory.items():
            if isinstance(v, bool):
                f.write(f"{k}: {str(v).lower()}\n")
            elif isinstance(v, str):
                f.write(f'{k}: "{v}"\n')
            else:
                f.write(f"{k}: {v}\n")
    print(f"  LLaMA-Factory config: {config_path}")

    # Unsloth config — use relative paths for cross-platform portability
    project_root = CFG.ROOT
    exports_path = './data/training/exports'
    unsloth_out = './data/training/output/unsloth_output'
    unsloth_final = './data/training/output/unsloth_output/final'

    unsloth_code = f'''# Unsloth fine-tuning script for riycol-agent
# Usage: python this_script.py
import os
from pathlib import Path
from unsloth import FastLanguageModel
from datasets import load_dataset
import torch

model_name = os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
max_seq_length = {CFG.N_CTX}

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=max_seq_length,
    dtype=None,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

dataset = load_dataset("json", data_files=str(Path(r"{exports_path}") / "*.jsonl"), split="train")

from trl import SFTTrainer
from transformers import TrainingArguments

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="instruction",
    max_seq_length=max_seq_length,
    args=TrainingArguments(
        output_dir=r"{unsloth_out}",
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_ratio=0.1,
        learning_rate=5e-5,
        num_train_epochs=3,
        logging_steps=10,
        save_steps=500,
        bf16=True,
    ),
)

trainer.train()
model.save_pretrained(r"{unsloth_final}")
print("Done! Model saved.")
'''
    unsloth_path = output_dir / "unsloth_train.py"
    with open(unsloth_path, 'w', encoding='utf-8') as f:
        f.write(unsloth_code)
    print(f"  Unsloth script: {unsloth_path}")


def cmd_all():
    """Full pipeline: prepare → clean → validate → convert (one-click)"""
    print("=" * 50)
    print("  Riycol Fine-Tuning Pipeline")
    print("=" * 50)

    steps = [
        ("1/4 PREPARE", cmd_prepare),
        ("2/4 CLEAN", cmd_clean),
        ("3/4 VALIDATE", cmd_validate),
        ("4/4 CONVERT", cmd_convert),
    ]

    for label, fn in steps:
        print(f"\n{'─' * 40}")
        print(f"  {label}")
        print(f"{'─' * 40}")
        try:
            fn()
        except Exception as e:
            print(f"  [FAIL] {label}: {e}")
            print("  Pipeline stopped. Fix the error and re-run.")
            return

    print(f"\n{'═' * 50}")
    print("  Pipeline complete! Training data ready.")
    print(f"  Output: data/training/output/")
    print(f"  Next: Fine-tune with LLaMA-Factory, Unsloth,")
    print(f"        or llama.cpp finetune using the exported data.")
    print(f"{'═' * 50}")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help', 'help'):
        print(__doc__)
        return

    commands = {
        'stats': cmd_stats,
        'prepare': cmd_prepare,
        'clean': cmd_clean,
        'validate': cmd_validate,
        'convert': cmd_convert,
        'config': cmd_config,
        'all': cmd_all,
    }

    cmd = args[0]
    if cmd in commands:
        commands[cmd]()
    else:
        print(f"Unknown command: {cmd}\n")
        print(__doc__)


if __name__ == '__main__':
    main()
