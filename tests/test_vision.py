"""
Vision module unit tests — core.vision
========================================
Tests: encode_image, describe fallback logic, tool wrapper.
"""
import pytest
from pathlib import Path


@pytest.fixture
def sample_image(tmp_path):
    """Create a minimal valid PNG for testing."""
    import struct, zlib
    img_path = tmp_path / "test.png"
    # Minimal 1x1 red PNG
    raw = b'\x89PNG\r\n\x1a\n'  # PNG signature
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
    raw += struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    # IDAT chunk (1 red pixel in filtered format)
    raw_idat = b'\x00\xff\x00\x00'  # filter none, RGB(255,0,0)
    compressed = zlib.compress(raw_idat)
    idat_crc = zlib.crc32(b'IDAT' + compressed)
    raw += struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
    # IEND
    raw += struct.pack('>I', 0) + b'IEND' + struct.pack('>I', zlib.crc32(b'IEND'))
    img_path.write_bytes(raw)
    return str(img_path)


class TestEncodeImage:
    def test_encode_valid_image(self, sample_image):
        from core.vision import encode_image
        result = encode_image(sample_image)
        assert result.startswith("data:image/png;base64,")
        assert len(result) > 50  # base64 data present

    def test_encode_file_not_found(self):
        from core.vision import encode_image
        with pytest.raises(FileNotFoundError):
            encode_image("/nonexistent/image.png")

    def test_encode_jpg_mime(self, tmp_path):
        from core.vision import encode_image
        jpg = tmp_path / "test.jpg"
        jpg.write_bytes(b"fake jpeg data")
        result = encode_image(str(jpg))
        assert result.startswith("data:image/jpeg;base64,")

    def test_encode_webp_mime(self, tmp_path):
        from core.vision import encode_image
        webp = tmp_path / "test.webp"
        webp.write_bytes(b"fake webp data")
        result = encode_image(str(webp))
        assert result.startswith("data:image/webp;base64,")


class TestDescribe:
    def test_describe_file_not_found(self):
        from core.vision import describe
        result = describe("/nonexistent/image.png")
        assert "not found" in result

    def test_describe_prefer_api_mocked(self, sample_image, monkeypatch):
        from core.vision import describe
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
        called = []

        def mock_api(path, prompt="", model="deepseek-chat"):
            called.append((path, prompt))
            return "mocked api description"

        import core.vision as vision
        monkeypatch.setattr(vision, "describe_image_api", mock_api)
        result = describe(sample_image, prefer="api")
        assert "mocked api description" in result
        assert len(called) == 1

    def test_describe_fallback_to_local(self, sample_image, monkeypatch):
        from core.vision import describe
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        def mock_local(path, prompt=""):
            return "mocked local description"

        import core.vision as vision
        monkeypatch.setattr(vision, "describe_image_local", mock_local)
        result = describe(sample_image, prefer="auto")
        assert "mocked local description" in result

    def test_describe_both_fail(self, sample_image, monkeypatch):
        from core.vision import describe
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        def fail_local(path, prompt=""):
            raise RuntimeError("local model not available")

        import core.vision as vision
        monkeypatch.setattr(vision, "describe_image_local", fail_local)
        result = describe(sample_image, prefer="auto")
        assert "Both API and local failed" in result


class TestToolDescribeImage:
    def test_tool_success(self, sample_image, monkeypatch):
        from core.vision import tool_describe_image
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        def mock_local(path, prompt=""):
            return "tool description result"

        import core.vision as vision
        monkeypatch.setattr(vision, "describe_image_local", mock_local)
        result = tool_describe_image(sample_image)
        assert result["description"] == "tool description result"
        assert result["filepath"] == sample_image

    def test_tool_error(self):
        from core.vision import tool_describe_image
        result = tool_describe_image("/nonexistent/image.png")
        assert "not found" in result.get("description", "").lower()
