<#
.SYNOPSIS
安装 Git hooks + Continue 自动化工作流
.DESCRIPTION
一键配置项目的自动化代码审查和提交前检查
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "=" -ForegroundColor Cyan * 50
Write-Host "  riycol-agent 自动化工作流安装" -ForegroundColor Cyan
Write-Host "=" -ForegroundColor Cyan * 50

# 1. 安装 Git hooks
Write-Host "`n[1/4] 安装 Git hooks..." -ForegroundColor Green
$hooksDir = Join-Path $root ".githooks"
if (Test-Path $hooksDir) {
    git config core.hooksPath ".githooks"
    Write-Host "  Git hooks 已配置: $hooksDir" -ForegroundColor Green
} else {
    Write-Warning "  .githooks 目录不存在"
}

# 2. 检查 Continue CLI
Write-Host "`n[2/4] 检查 Continue CLI..." -ForegroundColor Green
$cnAvailable = Get-Command "cn" -ErrorAction SilentlyContinue
if ($cnAvailable) {
    Write-Host "  Continue CLI (cn) 已安装" -ForegroundColor Green
} else {
    Write-Host "  Continue CLI 未安装，正在安装..." -ForegroundColor Yellow
    pip install continuedev 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Continue CLI 安装成功" -ForegroundColor Green
    } else {
        Write-Warning "  安装失败，请手动安装: pip install continuedev"
    }
}

# 3. 检查 .env 配置
Write-Host "`n[3/4] 检查环境配置..." -ForegroundColor Green
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "  创建 .env 模板..." -ForegroundColor Yellow
    @"
# riycol-agent 配置
# 模型路径 (GGUF)
MODEL_PATH=models/qwen2.5-1.5b.gguf

# 服务器配置
PORT=8000
N_CTX=2048
N_THREADS=8
DEBUG=0

# Telegram (可选)
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USERS=

# DeepSeek API (可选)
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
"@ | Out-File -FilePath $envFile -Encoding utf8
    Write-Host "  .env 文件已创建，请编辑配置" -ForegroundColor Yellow
} else {
    Write-Host "  .env 文件已存在" -ForegroundColor Green
}

# 4. 创建数据目录
Write-Host "`n[4/4] 创建数据目录..." -ForegroundColor Green
$dirs = @(
    "data/conversations",
    "data/docs",
    "data/training/exports",
    "data/training/output",
    "models"
)
foreach ($d in $dirs) {
    $path = Join-Path $root $d
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "  创建: $d" -ForegroundColor Gray
    } else {
        Write-Host "  已存在: $d" -ForegroundColor DarkGray
    }
}

# 完成
Write-Host "`n" -NoNewline
Write-Host "=" -ForegroundColor Cyan * 50
Write-Host "  安装完成!" -ForegroundColor Green
Write-Host "=" -ForegroundColor Cyan * 50
Write-Host "`n可用命令:"
Write-Host "  自动审查提交:  git commit (自动触发)" -ForegroundColor White
Write-Host "  手动代码审查:  .\scripts\auto-review.ps1 -Scope commit" -ForegroundColor White
Write-Host "  启动服务:      python main.py run server" -ForegroundColor White
Write-Host "  运行智能体:    python main.py agent run `"你好`"" -ForegroundColor White

