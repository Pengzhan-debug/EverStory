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

    def test_role_mix_routes_endpoints(self):
        os.environ["LLM_PROVIDERS"] = "qwen,deepseek"
        os.environ["LLM_PROVIDER_QWEN_BASE_URL"] = "https://qwen.test/v1"
        os.environ["LLM_PROVIDER_QWEN_API_KEY"] = "kq"
        os.environ["LLM_PROVIDER_QWEN_STRONG_MODEL"] = "qwen-plus"
        os.environ["LLM_PROVIDER_DEEPSEEK_BASE_URL"] = "https://deepseek.test/v1"
        os.environ["LLM_PROVIDER_DEEPSEEK_API_KEY"] = "kd"
        os.environ["LLM_PROVIDER_DEEPSEEK_CHEAP_MODEL"] = "deepseek-chat"
        os.environ["LLM_ROLE_STRONG"] = "qwen"
        os.environ["LLM_ROLE_CHEAP"] = "deepseek"

        from everstory.config import build_role_client

        client = build_role_client(mode="stub")
        self.assertEqual(client.strong_base_url, "https://qwen.test/v1")
        self.assertEqual(client.strong_api_key, "kq")
        self.assertEqual(client.strong_model, "qwen-plus")
        self.assertEqual(client.cheap_base_url, "https://deepseek.test/v1")
        self.assertEqual(client.cheap_api_key, "kd")
        self.assertEqual(client.cheap_model, "deepseek-chat")


if __name__ == "__main__":
    unittest.main()
