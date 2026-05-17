"""
Security Sandbox — multi-layer safety for agent command execution.

Layers:
  L1 熔断 — dangerous pattern detection (blocks before execution)
  L2 预览 — preview mode, human confirmation required
  L3 自动 — auto-execute with whitelist + sandbox restrictions

Includes: command whitelist, pattern blacklist, path sandboxing, audit logging.
"""
import os, json, time, shlex, subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from core.logger import log
from core.config import CFG


SANDBOX_PATH = str(CFG.DATA / "sandbox")
AUDIT_LOG = str(CFG.DATA / "security_audit.log")

ALLOWED_COMMANDS = ["ls", "cp", "mv", "mkdir", "cat", "echo", "touch",
                    "rm", "python", "pip", "git", "dir", "Get-ChildItem"]

DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf ~", "rm -rf .",
    "dd if=", "mkfs.", "format",
    "/dev/", "/etc/passwd", "/etc/shadow",
    "> /dev/", "> /etc/",
    "DROP TABLE", "DROP DATABASE", "DELETE FROM",
    "curl", "wget",
    "删除所有文件", "删除所有数据", "格式化磁盘", "格式化硬盘",
    "清空数据库", "删除数据库", "删库",
    "执行任意命令", "提权", "获取root",
]

FORBIDDEN_OPERATIONS = [
    "delete all", "format disk", "shutdown system",
    "drop database", "truncate table", "remove everything",
    "删除所有", "全部删除", "清空所有", "清除一切",
    "批量删除", "一键删除", "销毁数据",
]


@dataclass
class SecurityCheck:
    """Result of a security check."""
    allowed: bool
    reason: str = "ok"
    layer: str = "L1"          # L1=meltdown, L2=preview, L3=auto
    action: str = ""


class SecurityGuard:
    """Multi-layer security guard for agent command execution."""

    def __init__(self, auto_mode: bool = False, sandbox_path: str | None = None):
        self.auto_mode = auto_mode
        self.sandbox = Path(sandbox_path or SANDBOX_PATH)
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.violations: list[dict] = []

    # ---- L1: Pattern Detection ----

    def check_dangerous_patterns(self, text: str) -> SecurityCheck:
        """Scan text for dangerous patterns. Called before any execution."""
        lower = text.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern.lower() in lower:
                self._record_violation("L1_DANGEROUS_PATTERN", text, pattern)
                return SecurityCheck(False, f"危险模式: {pattern}", "L1", text)
        for op in FORBIDDEN_OPERATIONS:
            if op.lower() in lower:
                self._record_violation("L1_FORBIDDEN_OP", text, op)
                return SecurityCheck(False, f"禁止操作: {op}", "L1", text)
        return SecurityCheck(True, "ok", "L1", text)

    # ---- L2: Command Validation ----

    def validate_command(self, cmd_tokens: list[str]) -> SecurityCheck:
        """Validate a parsed command against whitelist and additional rules."""
        if not cmd_tokens:
            return SecurityCheck(False, "空命令", "L2")

        base = cmd_tokens[0]
        cmd_str = " ".join(cmd_tokens)

        # Whitelist check
        if base not in ALLOWED_COMMANDS:
            return SecurityCheck(False, f"命令 '{base}' 不在白名单", "L2", cmd_str)

        # Extra hardening for dangerous commands
        if base == "rm":
            if any(a in ("-rf", "-r", "-f", "/s", "/q") for a in cmd_tokens[1:]):
                return SecurityCheck(False, "rm 禁止递归/强制删除", "L2", cmd_str)
            for a in cmd_tokens[1:]:
                if a.startswith("/") or a.startswith("..") or a.startswith("C:\\"):
                    return SecurityCheck(False, "rm 禁止操作绝对/上级路径", "L2", cmd_str)

        # Pipe/redirect check
        for t in cmd_tokens:
            if t in ("|", ";", "&&", "||", ">", ">>"):
                return SecurityCheck(False, f"禁止管道/重定向: {t}", "L2", cmd_str)

        return SecurityCheck(True, "ok", "L2", cmd_str)

    # ---- L3: Sandbox Execution ----

    def execute(self, cmd_tokens: list[str], timeout: int = 30) -> dict:
        """Execute command inside sandbox directory. Returns {stdout, stderr, code}."""
        try:
            result = subprocess.run(
                cmd_tokens, shell=False, cwd=str(self.sandbox),
                capture_output=True, text=True, timeout=timeout,
            )
            self._audit(cmd_tokens, result.returncode)
            return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
        except subprocess.TimeoutExpired:
            self._audit(cmd_tokens, -1, "TIMEOUT")
            return {"stdout": "", "stderr": "执行超时", "code": -1}
        except Exception as e:
            self._audit(cmd_tokens, -1, str(e))
            return {"stdout": "", "stderr": str(e), "code": -1}

    # ---- Full Pipeline ----

    def process(self, intent: str, sandbox_cmd: list[str],
                auto_mode: bool | None = None) -> dict:
        """Full security pipeline: L1→L2→(confirm)→L3.

        Returns {"ok": bool, "result": dict, "layer": str, "reason": str}
        """
        auto = auto_mode if auto_mode is not None else self.auto_mode

        # L1: Pattern check
        l1 = self.check_dangerous_patterns(" ".join(sandbox_cmd))
        if not l1.allowed:
            log.warn(f"[Security L1] BLOCKED: {l1.reason}")
            return {"ok": False, "layer": "L1", "reason": l1.reason}

        # L2: Command validation
        l2 = self.validate_command(sandbox_cmd)
        if not l2.allowed:
            log.warn(f"[Security L2] BLOCKED: {l2.reason}")
            return {"ok": False, "layer": "L2", "reason": l2.reason}

        # L3: Preview or auto-execute
        if auto:
            result = self.execute(sandbox_cmd)
            log.info(f"[Security L3] AUTO: {intent} → code={result['code']}")
            return {"ok": True, "layer": "L3", "result": result}
        else:
            return {"ok": True, "layer": "L2_PREVIEW",
                    "preview": " ".join(sandbox_cmd),
                    "reason": "等待人工确认"}

    # ---- Threat Prediction ----

    def predict_threat(self, agent_output: str) -> dict:
        """Analyze agent output for potential threats before execution.

        Returns {"threat_level": "none|low|medium|high|critical", "signals": [...]}
        """
        lower = agent_output.lower()
        signals = []
        score = 0

        # File system destruction
        if any(p in lower for p in ["rm -rf", "delete all", "format", "mkfs"]):
            signals.append("文件系统破坏")
            score += 30
        # Network exfiltration
        if any(p in lower for p in ["curl", "wget", "upload", "send to"]):
            signals.append("网络外传")
            score += 20
        # Database destruction
        if any(p in lower for p in ["drop table", "drop database", "truncate"]):
            signals.append("数据库破坏")
            score += 30
        # Privilege escalation
        if any(p in lower for p in ["sudo", "admin", "root"]):
            signals.append("权限提升")
            score += 15
        # Code injection
        if any(p in lower for p in ["eval(", "exec(", "os.system", "subprocess"]):
            signals.append("代码注入")
            score += 20
        # Mass operation
        if any(p in lower for p in ["all files", "everything", "recursive", "bulk"]):
            signals.append("批量操作")
            score += 10

        if score >= 50:
            level = "critical"
        elif score >= 30:
            level = "high"
        elif score >= 15:
            level = "medium"
        elif score >= 5:
            level = "low"
        else:
            level = "none"

        return {"threat_level": level, "score": score, "signals": signals}

    # ---- Helpers ----

    def _record_violation(self, level: str, text: str, pattern: str):
        self.violations.append({
            "ts": time.time(), "level": level, "pattern": pattern,
            "text": text[:200],
        })

    def _audit(self, cmd: list[str], code: int, extra: str = ""):
        entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | EXECUTED(code={code}) | {' '.join(cmd)}"
        if extra:
            entry += f" | {extra}"
        entry += "\n"
        try:
            with open(AUDIT_LOG, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def stats(self) -> dict:
        return {
            "violations": len(self.violations),
            "recent": self.violations[-5:] if self.violations else [],
        }


# Global singleton
security = SecurityGuard()
