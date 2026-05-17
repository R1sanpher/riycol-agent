"""
数据库单元测试 — core.db
=========================
测试: CRUD、并发、边界条件、异常处理
"""

import time

import pytest
from core.db import Database, DB


class TestDatabase:
    """数据库核心操作测试"""

    @pytest.fixture
    def db(self, tmp_path):
        """每个测试使用独立的临时数据库"""
        db_path = str(tmp_path / "test.db")
        d = Database(db_path=db_path)
        yield d
        d.close()

    # ========== 消息测试 ==========

    def test_add_message(self, db):
        """添加消息后统计数据应正确增加"""
        db.add_msg("session_1", "user", "你好")
        db.add_msg("session_1", "assistant", "你好！有什么可以帮助你的吗？")
        stats = db.stats()
        assert stats["messages"] == 2
        assert stats["sessions"] == 1

    def test_add_multiple_sessions(self, db):
        """多个会话应分别统计"""
        db.add_msg("s1", "user", "msg1")
        db.add_msg("s2", "user", "msg2")
        db.add_msg("s2", "assistant", "reply2")
        stats = db.stats()
        assert stats["messages"] == 3
        assert stats["sessions"] == 2

    def test_add_msg_empty_content(self, db):
        """空内容消息也应能正常添加"""
        db.add_msg("s1", "user", "")
        stats = db.stats()
        assert stats["messages"] == 1

    def test_add_msg_special_chars(self, db):
        """特殊字符消息应正常处理"""
        special = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~\n\t\\"
        db.add_msg("s1", "user", special)
        stats = db.stats()
        assert stats["messages"] == 1

    def test_add_msg_unicode(self, db):
        """Unicode 消息应正常处理"""
        unicode_text = "你好世界 🌍 こんにちは 안녕하세요"
        db.add_msg("s1", "user", unicode_text)
        stats = db.stats()
        assert stats["messages"] == 1

    # ========== 训练样本测试 ==========

    def test_add_sample(self, db):
        """添加训练样本"""
        db.add_sample("什么是AI?", "AI是人工智能的缩写", source="test")
        samples = db.get_samples("default", limit=10)
        assert len(samples) == 1
        assert samples[0]["instruction"] == "什么是AI?"
        assert samples[0]["output"] == "AI是人工智能的缩写"

    def test_get_samples_by_dataset(self, db):
        """按数据集名称筛选样本"""
        db.add_sample("q1", "a1", dataset="ds1")
        db.add_sample("q2", "a2", dataset="ds2")
        ds1 = db.get_samples("ds1")
        ds2 = db.get_samples("ds2")
        assert len(ds1) == 1
        assert len(ds2) == 1

    def test_get_samples_limit(self, db):
        """limit 参数应限制返回条数"""
        for i in range(5):
            db.add_sample(f"q{i}", f"a{i}")
        samples = db.get_samples("default", limit=3)
        assert len(samples) == 3

    def test_get_samples_min_score(self, db):
        """min_score 参数应过滤低质量样本"""
        db.add_sample("q1", "a1", quality=0.5)
        db.add_sample("q2", "a2", quality=0.8)
        high_q = db.get_samples("default", min_score=0.7)
        assert len(high_q) == 1
        assert high_q[0]["instruction"] == "q2"

    def test_add_sample_with_tokens(self, db):
        """带 token 计数的样本"""
        db.add_sample("instruction", "output", tokens=128)
        samples = db.get_samples("default")
        assert samples[0]["token_count"] == 128

    # ========== 边界条件测试 ==========

    def test_empty_db_stats(self, db):
        """空数据库统计应为零"""
        stats = db.stats()
        assert stats["messages"] == 0
        assert stats["sessions"] == 0
        assert stats["samples"] == 0
        assert stats["docs"] == 0

    def test_get_samples_empty(self, db):
        """没有样本时应返回空列表"""
        samples = db.get_samples("nonexistent")
        assert samples == []

    def test_large_content(self, db):
        """大文本内容应能正常存储"""
        large_text = "A" * 10000
        db.add_msg("s1", "user", large_text)
        stats = db.stats()
        assert stats["messages"] == 1

    # ========== 并发/连接测试 ==========

    def test_reopen_database(self, tmp_path):
        """数据库关闭后重新打开应能正常读写"""
        db_path = str(tmp_path / "test.db")
        d1 = Database(db_path=db_path)
        d1.add_msg("s1", "user", "hello")
        stats1 = d1.stats()
        d1.close()

        d2 = Database(db_path=db_path)
        stats2 = d2.stats()
        assert stats2["messages"] == stats1["messages"]
        d2.close()

    def test_multiple_databases(self, tmp_path):
        """多个数据库实例应互不干扰"""
        db1 = Database(db_path=str(tmp_path / "db1.db"))
        db2 = Database(db_path=str(tmp_path / "db2.db"))
        db1.add_msg("s1", "user", "msg")
        db2.add_msg("s2", "user", "msg")
        assert db1.stats()["messages"] == 1
        assert db2.stats()["messages"] == 1
        # 检查 session_id 不同
        assert db1.stats()["sessions"] == 1
        assert db2.stats()["sessions"] == 1
        db1.close()
        db2.close()

    # ========== 全局 DB 实例测试 ==========

    def test_global_db_instance(self):
        """全局 DB 实例应能正常连接"""
        assert DB is not None
        stats = DB.stats()
        assert isinstance(stats, dict)
        assert "messages" in stats


class TestDatabaseErrorHandling:
    """数据库错误处理测试"""

    def test_invalid_db_path(self, tmp_path):
        """无效路径应能正常创建目录"""
        deep_path = str(tmp_path / "a" / "b" / "c" / "test.db")
        d = Database(db_path=deep_path)
        d.add_msg("s1", "user", "test")
        assert d.stats()["messages"] == 1
        d.close()

    def test_special_session_id(self, tmp_path):
        """特殊 session_id 应能正常使用"""
        d = Database(db_path=str(tmp_path / "special.db"))
        special_ids = ["", "  ", "123", "user@host", "path/to/session"]
        for sid in special_ids:
            d.add_msg(sid, "user", "test")
        stats = d.stats()
        assert stats["sessions"] == len(special_ids)
        d.close()


class TestMemoryStore:
    """Persistent memory store tests"""

    @pytest.fixture
    def ms(self, tmp_path):
        from core.db import Database
        from core.memory_store import MemoryStore
        db = Database(db_path=str(tmp_path / "test_mem.db"))
        store = MemoryStore(db=db)
        yield store
        db.close()

    def test_put_and_get(self, ms):
        ms.put("test_agent", "key1", {"data": "hello"})
        val = ms.get("test_agent", "key1")
        assert val == {"data": "hello"}

    def test_get_default(self, ms):
        val = ms.get("nonexistent", "key", default=[])
        assert val == []

    def test_list_keys(self, ms):
        ms.put("agent_a", "k1", "v1")
        ms.put("agent_a", "k2", "v2")
        keys = ms.list_keys("agent_a")
        assert "k1" in keys
        assert "k2" in keys

    def test_delete(self, ms):
        ms.put("agent_x", "temp", "val")
        ms.delete("agent_x", "temp")
        assert ms.get("agent_x", "temp") is None

    def test_clear_agent(self, ms):
        ms.put("agent_c", "a", 1)
        ms.put("agent_c", "b", 2)
        ms.clear_agent("agent_c")
        assert ms.list_keys("agent_c") == []

    def test_stats(self, ms):
        ms.put("stats_test", "x", 42)
        s = ms.stats()
        assert s["total_entries"] >= 1


class TestScheduler:
    """Task scheduler tests"""
    def test_add_task(self):
        from core.scheduler import TaskScheduler
        s = TaskScheduler()
        calls = []
        s.add("test", lambda: calls.append(1), every_seconds=0.01)
        s.start()
        time.sleep(0.05)
        s.stop()
        assert len(calls) >= 1

    def test_task_snapshot(self):
        from core.scheduler import TaskScheduler
        s = TaskScheduler()
        s.add("snap_test", lambda: None, every_seconds=60)
        snap = s.snapshot()
        assert snap["task_count"] == 1
        assert snap["tasks"][0]["name"] == "snap_test"

    def test_disable_enable(self):
        from core.scheduler import TaskScheduler
        s = TaskScheduler()
        s.add("toggle", lambda: None, every_seconds=0.01)
        s.disable("toggle")
        assert not s._tasks["toggle"].enabled
        s.enable("toggle")
        assert s._tasks["toggle"].enabled

    def test_run_once(self):
        from core.scheduler import TaskScheduler
        s = TaskScheduler()
        results = []
        s.add("once", lambda: results.append("done"), every_seconds=999)
        s.run_once("once")
        assert results == ["done"]

    def test_remove_task(self):
        from core.scheduler import TaskScheduler
        s = TaskScheduler()
        s.add("rm_me", lambda: None, every_seconds=1)
        s.remove("rm_me")
        assert "rm_me" not in s._tasks


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
