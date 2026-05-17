# Auto-progress Hook — Updates session state on each tool use
param($inputJson)
$pyCode = @'
import sys, json, time; sys.path.insert(0, r"d:\riycol-agent")
try:
    from core.sync_v3 import update, heartbeat

    data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    tool = data.get("tool_name", data.get("tool", "?"))
    status = data.get("status", "success")

    # Map tool to progress description
    tool_map = {
        "Read": "Reading code",
        "Write": "Writing file",
        "Edit": "Editing code",
        "Bash": "Running command",
        "PowerShell": "Running command",
        "Grep": "Searching code",
        "Glob": "Finding files",
        "Agent": "Delegating to subagent",
        "WebFetch": "Fetching web content",
        "WebSearch": "Searching web",
    }
    action = tool_map.get(tool, f"Using {tool}")

    heartbeat()
    update(status="working", action=action)
except Exception:
    pass
'@
$jsonArg = if ($inputJson) { $inputJson | ConvertTo-Json -Compress } else { '{}' }
python -c "$pyCode" $jsonArg 2>$null
