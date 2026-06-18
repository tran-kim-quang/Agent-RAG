import os

from backend.process_raw_data.vision_service import vision_service


def test_describe_image_file_uses_vision_model_name(tmp_path, monkeypatch):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"png-data")

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "A concise image description",
                        }
                    }
                ]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("VISION_MODEL_NAME", "vision-model-test")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OLLAMA_API_KEY", "secret-key")
    monkeypatch.setattr(vision_service.requests, "post", fake_post)

    result = vision_service.describe_image_file(image_path)

    assert result == "A concise image description"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    assert captured["json"]["model"] == "vision-model-test"
    assert captured["json"]["messages"][1]["content"][1]["type"] == "image_url"
