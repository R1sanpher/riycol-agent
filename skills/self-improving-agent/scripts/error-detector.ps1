# Self-Improvement Error Detector Hook (Windows PowerShell)
# Triggers on PostToolUse to detect command failures

$output = $env:CLAUDE_TOOL_OUTPUT ?? ""

$patterns = @(
    "error:", "Error:", "ERROR:",
    "failed", "FAILED",
    "command not found", "No such file",
    "Permission denied", "fatal:",
    "Exception", "Traceback",
    "npm ERR!", "ModuleNotFoundError",
    "SyntaxError", "TypeError",
    "exit code", "non-zero"
)

$hasError = $false
foreach ($p in $patterns) {
    if ($output -match [regex]::Escape($p)) {
        $hasError = $true
        break
    }
}

if ($hasError) {
    Write-Output @'
<error-detected>
A command error was detected. Consider logging this to .learnings/ERRORS.md if:
- The error was unexpected or non-obvious
- It required investigation to resolve
- It might recur in similar contexts

Use the self-improvement skill format: [ERR-YYYYMMDD-XXX]
</error-detected>
'@
}
