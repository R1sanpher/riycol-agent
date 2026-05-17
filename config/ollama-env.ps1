# Ollama performance env vars for RTX 5060 Ti (16GB VRAM)
# Run as Administrator, then restart Ollama service

[Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION", "1", "Machine")
[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "q4_0", "Machine")
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "1", "Machine")
[Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS", "1", "Machine")

Write-Host "Ollama env vars set. Restart Ollama to apply:"
Write-Host "  Restart-Service Ollama -Force"
Write-Host "Or restart Ollama from system tray."
