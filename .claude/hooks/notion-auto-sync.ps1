# Notion Auto-Sync Hook — throttled to run max once per 5 minutes
$lockFile = "C:\Users\Administrator\AppData\Local\Temp\riycol_notion_sync.txt"
$now = Get-Date
$lastSync = if (Test-Path $lockFile) { Get-Item $lockFile | Get-Content -Raw | ForEach-Object { if ($_) { [datetime]$_ } else { [datetime]"2000-01-01" } } } else { [datetime]"2000-01-01" }
$elapsed = ($now - $lastSync).TotalMinutes
if ($elapsed -ge 5) {
    $now.ToString("o") | Out-File $lockFile -Encoding utf8
    python -c "import sys; sys.path.insert(0, r'd:\riycol-agent'); from core.sync_notion import sync; sync()" 2>$null
}