"""
Model Manager — download and list GGUF models.
"""
import os
from pathlib import Path
from core.config import CFG


HF_MIRROR = CFG.HF_MIRROR

MODEL_CATALOG = {
    "gemma4-e4b": {
        "name": "Gemma 4 E4B-Instruct (Q4_K_M) — 8B/4.5B active",
        "url": f"{HF_MIRROR}/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf",
        "size": "~5.5 GB",
        "ctx": 128000,
    },
    "gemma4-26b": {
        "name": "Gemma 4 26B-A4B-Instruct (IQ4_XS) — MoE 3.8B active",
        "url": f"{HF_MIRROR}/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-IQ4_XS.gguf",
        "size": "~13 GB",
        "ctx": 256000,
    },
    "qwen2.5-1.5b": {
        "name": "Qwen2.5-1.5B-Instruct (Q4_K_M)",
        "url": f"{HF_MIRROR}/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size": "~1.1 GB",
        "ctx": 2048,
    },
    "qwen2.5-3b": {
        "name": "Qwen2.5-3B-Instruct (Q4_K_M)",
        "url": f"{HF_MIRROR}/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        "size": "~2.0 GB",
        "ctx": 4096,
    },
    "qwen2.5-7b": {
        "name": "Qwen2.5-7B-Instruct (Q4_K_M)",
        "url": f"{HF_MIRROR}/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf",
        "size": "~4.4 GB",
        "ctx": 8192,
    },
    "llama3.2-3b": {
        "name": "Llama-3.2-3B-Instruct (Q4_K_M)",
        "url": f"{HF_MIRROR}/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "size": "~2.0 GB",
        "ctx": 4096,
    },
}


def list_models():
    print(f"{'Key':<16} {'Model':<40} {'Size':<10} {'Context':<8}")
    print("-" * 74)
    for key, info in MODEL_CATALOG.items():
        installed = "✓" if (CFG.ROOT / "models" / info["name"].split("(")[0].strip()).exists() or \
                    Path(CFG.MODEL_PATH).exists() else ""
        print(f"  {key:<14} {info['name']:<40} {info['size']:<10} {info['ctx']:<8} {installed}")
    print()
    print(f"  Current MODEL_PATH: {CFG.MODEL_PATH}")
    print(f"  Installed: {'yes' if Path(CFG.MODEL_PATH).exists() else 'NO - set MODEL_PATH or download below'}")
    print()
    print("  Download: riycol model download <key>")
    print("  Example:  riycol model download qwen2.5-1.5b")


def check_model():
    """Quick model status check."""
    from core.model_router import get_available_models
    from core.token_counter import count_name
    available = get_available_models()
    print(f"  Tokenizer:    {count_name()}")
    print(f"  Ollama:       {'RUNNING' if available.get('ollama') else 'not running'}")
    print(f"  Local model:  {'LOADED' if available.get('local') else 'not loaded'}")
    print(f"  DeepSeek API: {'CONFIGURED' if available.get('deepseek') else 'not set'}")
    model_path = Path(CFG.MODEL_PATH)
    if model_path.exists():
        size_mb = model_path.stat().st_size / 1024 / 1024
        print(f"  Model file:   {model_path} ({size_mb:.0f} MB)")
    else:
        print(f"  Model file:   NOT FOUND ({CFG.MODEL_PATH})")
    if not any(available.values()):
        print("\n  ACTION: Start Ollama, download a model, or set DEEPSEEK_API_KEY")
        print("  riycol model list          - see available models")
        print("  riycol model download ...  - download a model")


def download_model(key: str):
    if key not in MODEL_CATALOG:
        print(f"Unknown model: {key}")
        print(f"Available: {', '.join(MODEL_CATALOG.keys())}")
        return

    info = MODEL_CATALOG[key]
    dest_dir = CFG.ROOT / "models"
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = info["url"].split("/")[-1]
    dest = dest_dir / filename

    if dest.exists():
        print(f"Model already exists: {dest}")
        print(f"Set MODEL_PATH={dest} in .env to use it.")
        return

    print(f"Downloading {info['name']} ({info['size']})...")
    print(f"From: {info['url']}")
    print(f"To:   {dest}")
    print()

    try:
        import requests
        session = requests.Session()
        session.trust_env = False  # Bypass system proxy
        resp = session.get(info["url"], stream=True, timeout=300,
                          proxies={"http": None, "https": None})
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r  {downloaded / 1024 / 1024:.1f} MB / {total / 1024 / 1024:.1f} MB ({pct:.0f}%)", end="")
        print("\n  Done!")
        print(f"\n  Add to .env: MODEL_PATH={dest}")
    except ImportError:
        print("  pip install requests first, or download manually:")
        print(f"  {info['url']}")
    except Exception as e:
        print(f"  Download failed: {e}")
        print(f"  Download manually: {info['url']}")
        if dest.exists():
            dest.unlink()
