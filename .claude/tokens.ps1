# Claude Code status line — displays token usage
$input_json = $input | Out-String
try {
    $data = $input_json | ConvertFrom-Json
    $tokens = ""
    if ($data.usage) {
        $in = $data.usage.input_tokens
        $cache = $data.usage.cache_read_input_tokens
        $out = $data.usage.output_tokens
        $tokens = "in:$in"
        if ($cache -gt 0) { $tokens += " cache:$cache" }
        $tokens += " out:$out"
    }
    Write-Output $tokens
} catch {
    Write-Output ""
}
