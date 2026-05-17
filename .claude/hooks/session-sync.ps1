# Session Sync Hook v3 — Real-time cross-session context with heartbeat
$pyCode = @'
import sys; sys.path.insert(0, r"d:\riycol-agent")
from core.sync_v3 import init_session, heartbeat, hook_inject
init_session("claude-main")
heartbeat()
output = hook_inject()
if output:
    print(output)
'@
python -c "$pyCode" 2>$null
