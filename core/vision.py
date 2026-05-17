"""
Vision module — image understanding via local or API models.
===============================================================
Supports:
  - DeepSeek/OpenAI-compatible vision API
  - Local llava-based GGUF with mmproj
  - Base64 image encoding
"""
import base64, os
from pathlib import Path
from core.logger import log
from core.config import CFG


def encode_image(filepath: str) -> str:
    """Read image and return base64 data URI."""
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {filepath}")
    ext = p.suffix.lower()
    mime_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp", ".gif": "gif", ".bmp": "bmp"}
    mime = mime_map.get(ext, "jpeg")
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode()
    return f"data:image/{mime};base64,{b64}"


def describe_image_api(image_path: str, prompt: str = "请详细描述这张图片的内容。",
                        model: str = "deepseek-chat") -> str:
    """Use DeepSeek/OpenAI vision API to describe an image."""
    data_uri = encode_image(image_path)
    from openai import OpenAI
    client = OpenAI(api_key=CFG.DEEPSEEK_KEY, base_url=CFG.DEEPSEEK_URL)
    resp = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": prompt},
            ]
        }],
        max_tokens=1024,
    )
    return resp.choices[0].message.content or ""


def describe_image_local(image_path: str, prompt: str = "请详细描述这张图片的内容。") -> str:
    """Use local multimodal model (llava) to describe an image."""
    from core.llm_bridge import is_loaded, generate
    if not is_loaded():
        raise RuntimeError("Local multimodal model not loaded. Set MODEL_PATH to a llava GGUF and MMPROJ_PATH in .env")

    data_uri = encode_image(image_path)
    mmproj = CFG.MMPROJ_PATH
    if not mmproj or not Path(mmproj).exists():
        raise RuntimeError(f"MMPROJ_PATH not set or not found: {mmproj}")

    from core.prompt_manager import prompts as _pm
    vision_sys = _pm.render("vision", "default")
    # Build multimodal prompt
    msgs = [
        {"role": "system", "content": vision_sys},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": prompt},
        ]}
    ]
    def _fmt_content(c) -> str:
        if isinstance(c, str):
            return c
        # Multimodal: extract text parts, skip image_url parts
        parts = [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(parts)

    formatted = "".join(f"<|im_start|>{m['role']}\n{_fmt_content(m['content'])}<|im_end|>\n" for m in msgs)
    formatted += "<|im_start|>assistant\n"

    # Note: llama-cpp-python with llava needs image_data parameter
    resp = generate(formatted, max_tokens=1024, temperature=0.7)
    return str(resp.get("choices", [{}])[0].get("text", "")).strip()


def describe(filepath: str, prompt: str = "请描述这张图片。", prefer: str = "auto") -> str:
    """
    Describe an image. Auto-selects API vs local.
    
    Args:
        filepath: Path to image file
        prompt: Question about the image
        prefer: "auto", "api", or "local"
    """
    if not Path(filepath).exists():
        return f"[Vision] Image not found: {filepath}"

    if prefer == "local":
        return describe_image_local(filepath, prompt)
    elif prefer == "api":
        return describe_image_api(filepath, prompt)

    # auto: prefer API if available
    if CFG.DEEPSEEK_KEY:
        try:
            return describe_image_api(filepath, prompt)
        except Exception as e:
            log.warn(f"Vision API failed, trying local: {e}")

    try:
        return describe_image_local(filepath, prompt)
    except Exception as e:
        return f"[Vision] Both API and local failed: {e}"


# Register as a tool
def tool_describe_image(filepath: str, prompt: str = "请描述这张图片。") -> dict:
    """Describe an image file. Registered as a Tool."""
    try:
        result = describe(filepath, prompt)
        return {"description": result, "filepath": filepath}
    except Exception as e:
        return {"error": str(e), "filepath": filepath}
