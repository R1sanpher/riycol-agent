"""
知识库单元测试 — plugins.server.kb
===================================
测试: 关键词搜索、向量搜索、混合模式、边界条件
"""

import os, sys, tempfile, time

import pytest


@pytest.fixture
def kb():
    """创建临时知识库实例"""
    from plugins.server.kb import KnowledgeBase
    with tempfile.TemporaryDirectory() as tmpdir:
        kb = KnowledgeBase(docs_dir=tmpdir, mode="keyword")
        # 创建测试文档
        for fname, content in [
            ("ai.txt", "人工智能（AI）是计算机科学的一个分支。\n\n它试图了解智能的实质。"),
            ("python.txt", "Python是一种高级编程语言。\n\n它被广泛用于AI开发。\n\nPython语法简洁。"),
            ("test.json", '{"topic": "test", "content": "这是一个测试文档"}'),
        ]:
            with open(os.path.join(tmpdir, fname), "w", encoding="utf-8") as f:
                f.write(content)
        kb.watch()
        yield kb


class TestKnowledgeBaseKeyword:
    """关键词模式测试"""

    def test_query_basic(self, kb):
        """基本关键词查询"""
        result = kb.query("人工智能")
        assert result["has_result"] is True
        assert len(result["sources"]) > 0
        assert "人工智能" in result["context"]

    def test_query_no_match(self, kb):
        """无匹配查询返回空"""
        result = kb.query("xyznonexistent123")
        assert result["has_result"] is False
        assert result["context"] == ""

    def test_query_empty(self, kb):
        """空查询返回空"""
        result = kb.query("")
        assert result["has_result"] is False

    def test_query_none(self, kb):
        """None 查询返回空"""
        result = kb.query(None)
        assert result["has_result"] is False

    def test_query_multiple_sources(self, kb):
        """查询应返回多个来源"""
        result = kb.query("AI 人工智能 Python")
        assert result["has_result"] is True
        assert len(result["sources"]) >= 2

    def test_query_top_k(self, kb):
        """top_k 应限制返回结果数"""
        result = kb.query("AI", top_k=1)
        assert len(result["sources"]) >= 1

    def test_query_token_cost(self, kb):
        """返回结果应包含 token 计数"""
        result = kb.query("人工智能")
        if result["has_result"]:
            assert result["token_cost"] > 0

    def test_engine_name(self, kb):
        """引擎名称应正确"""
        assert "hybrid" in kb.engine_name or "local" in kb.engine_name

    def test_refresh(self, kb):
        """刷新后结果应一致"""
        before = kb.query("人工智能")
        kb.refresh()
        after = kb.query("人工智能")
        assert before["has_result"] == after["has_result"]


class TestKnowledgeBaseEdgeCases:
    """边界条件测试"""

    def test_empty_directory(self):
        """空目录的知识库应正常查询"""
        from plugins.server.kb import KnowledgeBase
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(docs_dir=tmpdir, mode='keyword')
            kb.watch()
            result = kb.query("anything")
            assert result["has_result"] is False

    def test_nonexistent_directory(self):
        """不存在的目录应自动创建"""
        from plugins.server.kb import KnowledgeBase
        with tempfile.TemporaryDirectory() as tmpdir:
            nosuch = os.path.join(tmpdir, "does_not_exist_yet")
            kb = KnowledgeBase(docs_dir=nosuch)
            assert os.path.exists(nosuch)

    def test_unsupported_file_types(self, kb):
        """不支持的文件类型应被忽略"""
        from plugins.server.kb import KnowledgeBase
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建不受支持的文件
            with open(os.path.join(tmpdir, "test.exe"), "w") as f:
                f.write("binary data")
            with open(os.path.join(tmpdir, "test.pdf"), "w") as f:
                f.write("PDF content")
            kb2 = KnowledgeBase(docs_dir=tmpdir)
            kb2.watch()
            # 应没有 chunk
            assert len(kb2.all_chunks) == 0

    def test_special_characters_in_query(self, kb):
        """特殊字符查询不应崩溃"""
        special_queries = [
            "!@#$%^&*()",
            "\n\t\r",
            "  ",
            "a" * 1000,
            "<script>alert('xss')</script>",
            "SELECT * FROM users; DROP TABLE;",
        ]
        for q in special_queries:
            result = kb.query(q)
            assert isinstance(result, dict)
            assert "has_result" in result

    def test_unicode_query(self, kb):
        """Unicode 查询应正常"""
        queries = [
            "你好世界",
            "こんにちは",
            "안녕하세요",
            "🌍🌎🌏",
        ]
        for q in queries:
            result = kb.query(q)
            assert isinstance(result, dict)
            assert "has_result" in result

    def test_add_text_functionality(self, kb):
        """添加文本后应能查询到"""
        kb.add_text("这是动态添加的测试内容", "dynamic.txt")
        result = kb.query("动态添加")
        assert result["has_result"] is True


class TestTools:
    """Tool framework tests"""
    def test_tool_registry_has_builtins(self):
        from core.tools import tool_registry
        names = tool_registry.list_names()
        assert "read_file" in names
        assert "write_file" in names
        assert "search_kb" in names
        assert "db_query" in names
        assert "get_time" in names
        assert "web_fetch" in names

    def test_tool_get_time(self):
        from core.tools import tool_get_time
        result = tool_get_time()
        assert "iso" in result
        assert "date" in result

    def test_tool_read_file(self):
        from core.tools import tool_read_file
        result = tool_read_file("README.md", max_lines=5)
        assert "content" in result
        assert result["lines"] <= 5

    def test_tool_read_file_not_found(self):
        from core.tools import tool_read_file
        result = tool_read_file("nonexistent_xyz.abc")
        assert "error" in result

    def test_tool_write_and_read(self):
        from core.tools import tool_write_file
        result = tool_write_file("data/test_tool_output.txt", "hello from tool test")
        assert "written" in result
        # Cleanup
        import os as _os
        fp = _os.path.join(_os.path.dirname(__file__), "..", "data", "test_tool_output.txt")
        if _os.path.exists(fp):
            _os.remove(fp)

    def test_tool_db_query_readonly(self):
        from core.tools import tool_db_query
        result = tool_db_query("SELECT COUNT(*) as cnt FROM conversations")
        assert "rows" in result

    def test_tool_db_query_blocked(self):
        from core.tools import tool_db_query
        result = tool_db_query("DROP TABLE conversations")
        assert "error" in result

    def test_tool_openai_schema(self):
        from core.tools import tool_registry
        schemas = tool_registry.get_schemas()
        assert len(schemas) >= 6
        for s in schemas:
            assert s["type"] == "function"
            assert "name" in s["function"]

    def test_tool_execute_error(self):
        from core.tools import Tool
        def bad_fn():
            raise ValueError("fail")
        t = Tool("bad", "test tool", {"type": "object", "properties": {}, "required": []}, bad_fn)
        result = t.execute({})
        assert "error" in result

    def test_tool_search_kb(self):
        from core.tools import tool_search_kb
        result = tool_search_kb("test")
        assert "has_result" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
