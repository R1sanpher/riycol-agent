"""
Import public Chinese instruction datasets into riycol DB.
Usage: python scripts/import_datasets.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.db import DB
from core.logger import log

DATASETS = [
    {
        "name": "alpaca-zh",
        "hf": "shibing624/alpaca-zh",
        "instruction_key": "instruction",
        "output_key": "output",
        "source": "alpaca-zh",
    },
    {
        "name": "Belle-0.5M",
        "hf": "BelleGroup/train_0.5M_CN",
        "instruction_key": "instruction",
        "output_key": "output",
        "source": "belle",
    },
    {
        "name": "firefly-1.1M",
        "hf": "YeungNLP/firefly-train-1.1M",
        "instruction_key": "input",
        "output_key": "target",
        "source": "firefly",
        "max_samples": 200000,
    },
    {
        "name": "Chinese-Vicuna",
        "hf": "Chinese-Vicuna/guanaco_belle_merge_v1.0",
        "instruction_key": "instruction",
        "output_key": "output",
        "source": "chinese-vicuna",
    },
]


def import_dataset(ds_info: dict) -> int:
    """Download and import a HuggingFace dataset. Returns count imported."""
    try:
        from datasets import load_dataset
    except ImportError:
        log.error("pip install datasets first")
        return 0

    log.info(f"Loading {ds_info['name']} from {ds_info['hf']}...")
    try:
        ds = load_dataset(ds_info["hf"], split="train")
    except Exception:
        try:
            ds = load_dataset(ds_info["hf"], split="train", streaming=True)
        except Exception as e:
            log.error(f"Failed to load {ds_info['name']}: {e}")
            return 0

    count = 0
    max_samples = ds_info.get("max_samples", 999999)
    ik = ds_info["instruction_key"]
    ok = ds_info["output_key"]
    source = ds_info["source"]

    for item in ds:
        if count >= max_samples:
            break
        inst = str(item.get(ik, "")).strip()
        out = str(item.get(ok, "")).strip()
        if not inst or not out or len(inst) < 5 or len(out) < 10:
            continue
        try:
            DB.add_sample(inst, out, source=source, dataset=ds_info["name"],
                          quality=1.0, tokens=len(inst) + len(out))
            count += 1
            if count % 1000 == 0:
                log.info(f"  {ds_info['name']}: {count} imported...")
        except Exception as e:
            log.warn(f"  skip: {e}")

    log.info(f"  {ds_info['name']}: DONE ({count} samples)")
    return count


def main():
    print("=" * 50)
    print("  Riycol Dataset Importer")
    print("=" * 50)
    print()

    total = 0
    for ds in DATASETS:
        n = import_dataset(ds)
        total += n

    print(f"\n{'=' * 50}")
    print(f"  Total imported: {total} samples")
    s = DB.stats()
    print(f"  DB total samples: {s['samples']}")
    print(f"{'=' * 50}")

    if total > 0:
        print("\n  Next: riycol finetune prepare  -- 导出训练集")
        print("        riycol finetune clean    -- 去重+质量过滤")
        print("        riycol finetune config   -- 生成训练配置")
        print("        pip install unsloth && python data/training/output/unsloth_train.py")


if __name__ == "__main__":
    main()
