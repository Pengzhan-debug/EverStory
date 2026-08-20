import os
import unittest

from everstory.config import load_providers


class ProviderConfigTest(unittest.TestCase):
    def tearDown(self):
        for key in [k for k in os.environ if k.startswith("LLM_PROVIDER")]:
            del os.environ[key]
        os.environ["LLM_PROVIDERS"] = ""

    def test_legacy_fallback(self):
        os.environ["LLM_PROVIDERS"] = ""
        providers = load_providers()
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0].name, "default")

    def test_multiple_providers(self):
        os.environ["LLM_PROVIDERS"] = "qwen,deepseek"
        os.environ["LLM_PROVIDER_QWEN_BASE_URL"] = "https://qwen.test/v1"
        os.environ["LLM_PROVIDER_QWEN_API_KEY"] = "k1"
        os.environ["LLM_PROVIDER_DEEPSEEK_API_KEY"] = "k2"
        providers = load_providers()
        self.assertEqual([p.name for p in providers], ["qwen", "deepseek"])
        self.assertEqual(providers[0].base_url, "https://qwen.test/v1")
        self.assertEqual(providers[0].api_key, "k1")
        self.assertEqual(providers[1].api_key, "k2")

    def test_filter_requested(self):
        os.environ["LLM_PROVIDERS"] = "qwen,deepseek"
        providers = load_providers()
        self.assertEqual(
            [p.name for p in providers if p.name in ("deepseek",)],
            ["deepseek"],
        )


if __name__ == "__main__":
    unittest.main()
