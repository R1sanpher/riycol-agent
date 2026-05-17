@echo off
chcp 65001 >nul
title Riycol Agent

echo ========================================
echo   Riycol Agent v2.2.0
echo ========================================
echo.
echo [1] 启动全部服务 (HTTP + Agent + 调度器)
echo [2] 仅 HTTP API 服务
echo [3] 仅 Agent Swarm
echo [4] 验证配置
echo [5] 运行测试
echo [0] 退出
echo.
set /p choice="选择 [1-5]: "

if "%choice%"=="1" (
    echo 启动全部服务...
    python riycol.py run all
) else if "%choice%"=="2" (
    echo 启动 HTTP API 服务...
    python riycol.py run server
) else if "%choice%"=="3" (
    echo 启动 Agent Swarm...
    python riycol.py run agent
) else if "%choice%"=="4" (
    python riycol.py validate
    pause
) else if "%choice%"=="5" (
    python -m pytest tests/ -v
    pause
) else if "%choice%"=="0" (
    exit
) else (
    echo 无效选择
    pause
)
