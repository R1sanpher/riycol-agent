$logFile = "discord_bot_output.log"
$process = Start-Process -NoNewWindow -PassThru -FilePath python -ArgumentList "riycol.py run discord" -RedirectStandardOutput $logFile -RedirectStandardError $logFile
$process.Id | Out-File -Encoding utf8 discord_bot.pid
Write-Host "PID: $($process.Id)"
