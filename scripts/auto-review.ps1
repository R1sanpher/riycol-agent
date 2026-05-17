<#
.SYNOPSIS
Continue 自动化代码审查脚本
.DESCRIPTION
使用 Continue CLI (cn) 自动审查最新代码变更，生成审查报告
.PARAMETER Scope
审查范围: staged (暂存区) | commit (最新提交) | all (完整项目)
.PARAMETER OutputPath
报告输出路径 (默认: review_report.md)
.EXAMPLE
.\scripts\auto-review.ps1 -Scope commit
.\scripts\auto-review.ps1 -Scope all -OutputPath docs/code_review.md
#>

param(
    [ValidateSet("staged", "commit", "all")]
    [string]$Scope = "commit",
    [string]$OutputPath = "review_report.md"
)

# 设置错误时停止
$ErrorActionPreference = "Stop"

# 检查 cn (Continue CLI) 是否可用
$cnAvailable = Get-Command "cn" -ErrorAction SilentlyContinue
if (-not $cnAvailable) {
    Write-Warning "Continue CLI (cn) 未安装。正在尝试安装..."
    try {
        pip install continuedev
        Write-Host "安装完成，请重启终端后重试。" -ForegroundColor Green
        exit 0
    }
    catch {
        Write-Error "安装 failed: $_"
        Write-Host "请手动安装: pip install continuedev" -ForegroundColor Yellow
        exit 1
    }
}

# 创建报告头部
$reportHeader = @"
# Code Review Report

**时间**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**审查范围**: $Scope
**项目**: riycol-agent

---

"@

$reportHeader | Out-File -FilePath $OutputPath -Encoding utf8

Write-Host "=" * 50 -ForegroundColor Cyan
Write-Host "  Continue 自动化代码审查" -ForegroundColor Cyan
Write-Host "  范围: $Scope" -ForegroundColor Cyan
Write-Host "  输出: $OutputPath" -ForegroundColor Cyan
Write-Host "=" * 50 -ForegroundColor Cyan

# 根据范围准备审查内容
switch ($Scope) {
    "staged" {
        Write-Host "[1/3] 获取暂存区变更..." -ForegroundColor Green
        $diff = git diff --cached
        if (-not $diff) {
            Write-Host "  暂存区无变更" -ForegroundColor Yellow
            return
        }
        
        Write-Host "[2/3] 提交代码审查请求到 Continue..." -ForegroundColor Green
        $prompt = @"
请审查以下 Git 暂存区代码变更，检查：
1. 安全漏洞 (SQL注入、路径遍历、XSS等)
2. 性能问题 (不必要的循环、重复计算、内存泄漏)
3. 代码质量 (可读性、维护性、最佳实践)
4. 错误处理 (异常处理是否合理)
5. 潜在 Bug

用中文总结，按严重程度排序。

代码变更:
$diff
"@
        
        Write-Host "[3/3] 等待 Continue 分析..." -ForegroundColor Green
        try {
            # 使用 cn 命令执行审查
            $result = cn -p $prompt --allow "Read,Terminal" --silent
            
            $reportBody = @"

## 审查结果 (暂存区变更)

$result

---
*由 Continue CLI 自动生成*
"@
            $reportBody | Out-File -FilePath $OutputPath -Encoding utf8 -Append
            Write-Host "  审查完成!" -ForegroundColor Green
        }
        catch {
            Write-Error "审查过程出错: $_"
        }
    }
    
    "commit" {
        Write-Host "[1/3] 获取最新提交..." -ForegroundColor Green
        $lastCommitMsg = git log -1 --pretty=%B
        $lastCommitDiff = git diff HEAD~1..HEAD 2>$null
        if (-not $lastCommitDiff) {
            $lastCommitDiff = git show --stat HEAD
        }
        
        Write-Host "  最新提交: $lastCommitMsg" -ForegroundColor Gray
        
        Write-Host "[2/3] 提交代码审查请求到 Continue..." -ForegroundColor Green
        $prompt = @"
请审查以下 Git 最新提交的代码变更，检查：
1. 安全漏洞
2. 性能问题
3. 代码质量
4. 错误处理
5. 潜在 Bug

提交信息: $lastCommitMsg

用中文总结，按严重程度排序。

代码变更:
$lastCommitDiff
"@
        
        Write-Host "[3/3] 等待 Continue 分析..." -ForegroundColor Green
        try {
            $result = cn -p $prompt --allow "Read,Terminal" --silent
            
            $reportBody = @"

## 审查结果 (最新提交)

**提交**: $lastCommitMsg

$result

---
*由 Continue CLI 自动生成*
"@
            $reportBody | Out-File -FilePath $OutputPath -Encoding utf8 -Append
            Write-Host "  审查完成!" -ForegroundColor Green
        }
        catch {
            Write-Error "审查过程出错: $_"
        }
    }
    
    "all" {
        Write-Host "[1/3] 收集项目文件清单..." -ForegroundColor Green
        $pyFiles = Get-ChildItem -Recurse -Filter "*.py" | Where-Object { 
            $_.FullName -notmatch "__pycache__|\.continue|exports|output" 
        }
        Write-Host "  发现 $($pyFiles.Count) 个 Python 文件"
        
                Write-Host "[2/3] 生成项目概览..." -ForegroundColor Green
        Write-Host "[3/3] 提交全面审查请求到 Continue..." -ForegroundColor Green
        $prompt = @"
请对以下 riycol-agent 项目进行全面的代码审查。

项目结构:
$(Get-ChildItem -Directory | Where-Object { $_.Name -notmatch '^\.|__pycache__|exports|output' } | ForEach-Object { "  - $($_.Name)" })

请检查:
1. 整体架构安全性
2. 各模块间的接口一致性
3. 配置文件安全性 (API密钥管理)
4. 数据库操作安全性 (SQL注入)
5. API 端点安全性 (鉴权、限流)
6. 文件路径操作安全性 (路径遍历)
7. 异常处理完整性
8. 性能优化建议

用中文总结，按严重程度 (严重/中等/建议) 排序。
"@
        
        try {
            $result = cn -p $prompt --allow "Read,Terminal" --silent
            
            $reportBody = @"

## 审查结果 (完整项目)

$result

---
*由 Continue CLI 自动生成*
"@
            $reportBody | Out-File -FilePath $OutputPath -Encoding utf8 -Append
            Write-Host "  审查完成!" -ForegroundColor Green
        }
        catch {
            Write-Error "审查过程出错: $_"
        }
    }
}

Write-Host "=" * 50 -ForegroundColor Cyan
Write-Host "报告已生成: $OutputPath" -ForegroundColor Green
Write-Host "=" * 50 -ForegroundColor Cyan
