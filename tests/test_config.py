import os
import unittest

from everstory.config import build_client


class ConfigTest(unittest.TestCase):
    def tearDown(self):
        for key in [
            k
            for k in os.environ
            if k.startswith("LLM_STRONG")
            or k.startswith("LLM_CHEAP")
            or k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL_STRONG", "LLM_MODEL_CHEAP")
        ]:
            del os.environ[key]

    def test_strong_and_cheap_routes(self):
        os.environ["LLM_STRONG_BASE_URL"] = "https://qwen.test/v1"
        os.environ["LLM_STRONG_API_KEY"] = "kq"
        os.environ["LLM_STRONG_MODEL"] = "qwen-plus"
        os.environ["LLM_CHEAP_BASE_URL"] = "https://deepseek.test/v1"
        os.environ["LLM_CHEAP_API_KEY"] = "kd"
        os.environ["LLM_CHEAP_MODEL"] = "deepseek-chat"

        client = build_client(mode="stub")
        self.assertEqual(client.strong_base_url, "https://qwen.test/v1")
        self.assertEqual(client.strong_api_key, "kq")
        self.assertEqual(client.strong_model, "qwen-plus")
        self.assertEqual(client.cheap_base_url, "https://deepseek.test/v1")
        self.assertEqual(client.cheap_api_key, "kd")
        self.assertEqual(client.cheap_model, "deepseek-chat")

    def test_legacy_fallback(self):
        for key in (
            "LLM_STRONG_BASE_URL",
            "LLM_STRONG_API_KEY",
            "LLM_STRONG_MODEL",
            "LLM_CHEAP_BASE_URL",
            "LLM_CHEAP_API_KEY",
            "LLM_CHEAP_MODEL",
        ):
            os.environ.pop(key, None)
        os.environ["LLM_BASE_URL"] = "https://legacy.test/v1"
        os.environ["LLM_API_KEY"] = "klegacy"
        os.environ["LLM_MODEL_STRONG"] = "legacy-strong"
        os.environ["LLM_MODEL_CHEAP"] = "legacy-cheap"

        client = build_client(mode="stub")
        self.assertEqual(client.strong_base_url, "https://legacy.test/v1")
        self.assertEqual(client.strong_api_key, "klegacy")
        self.assertEqual(client.strong_model, "legacy-strong")
        self.assertEqual(client.cheap_model, "legacy-cheap")


if __name__ == "__main__":
    unittest.main()
