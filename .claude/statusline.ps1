# Claude Code status line — reads JSON from stdin, outputs model + time
$input_json = $input | Out-String
try {
    $data = $input_json | ConvertFrom-Json
    $model = $data.model -replace '.*/'
    $tokens = if ($data.usage) { "in:$($data.usage.input_tokens) out:$($data.usage.output_tokens)" } else { "" }
    "$model $tokens"
} catch {
    "riycol-agent"
}
