# Self-Improvement Activator Hook (Windows PowerShell)
# Triggers on UserPromptSubmit to remind about learning capture.
# Filters noise from test/CI/install commands.

$inputLine = $env:CLAUDE_PROMPT_INPUT
if (-not $inputLine) { $inputLine = "" }
$skipPatterns = @("pytest", "test_", "ruff check", "pip install", "npm install", "npx repomix", "sgpt ")

$shouldSkip = $false
foreach ($p in $skipPatterns) {
    if ($inputLine -match $p) {
        $shouldSkip = $true
        break
    }
}

if (-not $shouldSkip) {
    Write-Output @'
<self-improvement-reminder>
After completing this task, evaluate if extractable knowledge emerged:
- Non-obvious solution discovered through investigation?
- Workaround for unexpected behavior?
- Project-specific pattern learned?
- Error required debugging to resolve?

If yes: Log to .learnings/ using the self-improvement skill format.
If high-value (recurring, broadly applicable): Consider skill extraction.
</self-improvement-reminder>
'@
}
