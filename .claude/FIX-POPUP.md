# PowerShell Popup Fix

## What's happening
VSCode's Claude Code extension shows permission prompts BEFORE Claude Code's
own permission system. Your Claude Code config is correct — the prompt comes
from VSCode's terminal security layer.

## Fix (pick one)

### Fix 1: VSCode Setting
Open VSCode settings (Ctrl+,), search for:
```
security.workspace.trust.enabled
```
Set it to `false` to disable workspace trust prompts.

Also search:
```
claude-code.terminal.trust
```

### Fix 2: Start Claude Code outside VSCode
Open a standalone terminal (PowerShell):
```
claude
```
Or:
```
claude --project d:\riycol-agent
```
The standalone CLI respects your Claude Code permission settings.

### Fix 3: Auto-accept in VSCode
In VSCode settings.json (Ctrl+Shift+P -> "Open User Settings JSON"), add:
```json
"security.workspace.trust.enabled": false,
"extensions.experimental.trustPolicies": true
```
