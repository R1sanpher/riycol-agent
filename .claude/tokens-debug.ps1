# Debug: dump all stdin to a file to see what Claude Code sends
$input_json = $input | Out-String
$input_json | Out-File "d:/riycol-agent/.claude/statusline_input.json" -Encoding utf8
# Try to extract useful info
try {
    $data = $input_json | ConvertFrom-Json
    # Try various possible field names
    $result = @()
    if ($data.input_tokens) { $result += "in:$($data.input_tokens)" }
    if ($data.output_tokens) { $result += "out:$($data.output_tokens)" }
    if ($data.cache_read_input_tokens -and $data.cache_read_input_tokens -gt 0) { $result += "cache:$($data.cache_read_input_tokens)" }
    if ($data.usage) {
        $u = $data.usage
        if ($u.input_tokens) { $result += "in:$($u.input_tokens)" }
        if ($u.output_tokens) { $result += "out:$($u.output_tokens)" }
        if ($u.cache_read_input_tokens -and $u.cache_read_input_tokens -gt 0) { $result += "cache:$($u.cache_read_input_tokens)" }
    }
    if ($result.Count -gt 0) {
        Write-Output ($result -join " ")
    } else {
        Write-Output "tokens: ?"
    }
} catch {
    Write-Output "no data"
}
