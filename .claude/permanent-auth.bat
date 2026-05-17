@echo off
echo ============================================
echo   Permanent PowerShell Authorization
echo ============================================
echo.
echo This creates the final auth state. After running:
echo   1. Exit Claude Code (type /quit)
echo   2. Reopen Claude Code
echo   3. PowerShell will NEVER prompt again
echo.
echo Verifying current config...

python -c "import json; lc=json.load(open('d:/riycol-agent/.claude/settings.local.json')); gl=json.load(open('C:/Users/Administrator/.claude/settings.json')); print('Global bypass:', gl.get('permissions',{}).get('defaultMode')); print('Local bypass:', lc['permissions'].get('defaultMode')); print('PowerShell(*):', 'PowerShell(*)' in lc['permissions']['allow']); print('Bash(*):', 'Bash(*)' in lc['permissions']['allow']); print('skipDanger:', gl.get('skipDangerousModePermissionPrompt')); print('skipAuto:', gl.get('skipAutoPermissionPrompt'))"

echo.
echo If all above show True/bypassPermissions, config is correct.
echo You MUST restart Claude Code after this.
echo.
pause
