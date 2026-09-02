import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi/httpx not installed")
class ApiTest(unittest.TestCase):
    @staticmethod
    def authorize_writes(client):
        client.get("/api/auth/session")
        client.headers.update(
            {"X-CSRF-Token": client.cookies.get("everstory_csrf")}
        )

    def setUp(self):
        import os

        self._old_mode = os.environ.get("LLM_MODE")
        os.environ["LLM_MODE"] = "stub"  # keep tests offline/deterministic
        from everstory.api.main import app

        self.client = TestClient(app)
        self.authorize_writes(self.client)
        self.client.post("/api/reset")

    def tearDown(self):
        import os

        if self._old_mode is None:
            os.environ.pop("LLM_MODE", None)
        else:
            os.environ["LLM_MODE"] = self._old_mode

    def test_health_and_world(self):
        self.assertEqual(self.client.get("/api/health").json()["status"], "ok")
        world = self.client.get("/api/world").json()
        self.assertIn("locations", world)
        self.assertIn("player", world)
        self.assertIn("scene", world)
        self.assertEqual(world["scene"]["location"]["name"], "Storm Shore")
        self.assertIn("investigation team", world["scene"]["objective"])
        self.assertGreater(len(world["scene"]["suggestions"]), 1)

    def test_guest_identity_uses_separate_auth_and_runtime_cookies(self):
        data = self.client.get("/api/auth/session").json()

        self.assertEqual(data["user"]["kind"], "guest")
        self.assertFalse(data["user"]["registered"])
        self.assertEqual(
            data["runtime_id"], self.client.cookies.get("everstory_runtime")
        )
        self.assertEqual(len(self.client.cookies.get("everstory_auth")), 64)
        self.assertEqual(len(self.client.cookies.get("everstory_runtime")), 32)

    def test_unknown_auth_cookie_is_replaced_by_server_credential(self):
        attacker_selected = "a" * 64
        self.client.cookies.set("everstory_auth", attacker_selected)

        response = self.client.get("/api/auth/session")

        self.assertEqual(response.status_code, 200)
        issued = response.cookies.get("everstory_auth")
        self.assertNotEqual(issued, attacker_selected)
        self.assertEqual(len(issued), 64)

    def test_csrf_rejects_cookie_authenticated_write_without_header(self):
        attacker = TestClient(self.client.app)
        try:
            attacker.get("/api/auth/session")
            rejected = attacker.post("/api/reset")
            self.assertEqual(rejected.status_code, 403)
            attacker.headers.update(
                {"X-CSRF-Token": attacker.cookies.get("everstory_csrf")}
            )
            self.assertEqual(attacker.post("/api/reset").status_code, 200)
        finally:
            attacker.close()

    def test_email_code_upgrades_guest_without_losing_runtime(self):
        import os
        from unittest.mock import patch

        before = self.client.get("/api/auth/session").json()
        self.client.post("/api/turn", json={"text": "wait"})
        with patch.dict(
            os.environ,
            {"AUTH_EMAIL_MODE": "development", "AUTH_DEV_EXPOSE_CODE": "true"},
        ):
            challenge = self.client.post(
                "/api/auth/email/request",
                json={"email": "player@example.com", "locale": "en"},
            )
            self.assertEqual(challenge.status_code, 202)
            challenge_data = challenge.json()
            verified = self.client.post(
                "/api/auth/email/verify",
                json={
                    "challenge_id": challenge_data["challenge_id"],
                    "email": "player@example.com",
                    "code": challenge_data["development_code"],
                },
            )

        self.assertEqual(verified.status_code, 200)
        data = verified.json()
        self.assertTrue(data["user"]["registered"])
        self.assertEqual(data["runtime_id"], before["runtime_id"])
        self.assertEqual(self.client.get("/api/world").json()["turn"], 1)
        self.client.headers.update(
            {"X-CSRF-Token": self.client.cookies.get("everstory_csrf")}
        )
        sessions = self.client.get("/api/auth/sessions").json()["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertTrue(sessions[0]["current"])
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        after_logout = self.client.get("/api/auth/session").json()
        self.assertFalse(after_logout["user"]["registered"])

    def test_registered_account_can_resume_owned_investigation_across_clients(self):
        import os
        from unittest.mock import patch

        primary = TestClient(self.client.app)
        secondary = TestClient(self.client.app)
        outsider = TestClient(self.client.app)
        try:
            self.authorize_writes(primary)
            primary_turn = primary.post(
                "/api/turn", json={"text": "wait", "locale": "en"}
            ).json()["world"]["turn"]
            primary_runtime = primary.get("/api/auth/session").json()["runtime_id"]
            with patch.dict(
                os.environ,
                {"AUTH_EMAIL_MODE": "development", "AUTH_DEV_EXPOSE_CODE": "true"},
            ):
                first_challenge = primary.post(
                    "/api/auth/email/request",
                    json={"email": "switching@example.com", "locale": "en"},
                ).json()
                self.assertEqual(
                    primary.post(
                        "/api/auth/email/verify",
                        json={
                            "challenge_id": first_challenge["challenge_id"],
                            "email": "switching@example.com",
                            "code": first_challenge["development_code"],
                        },
                    ).status_code,
                    200,
                )

                self.authorize_writes(secondary)
                secondary.post("/api/turn", json={"text": "wait", "locale": "en"})
                secondary_runtime = secondary.get("/api/auth/session").json()[
                    "runtime_id"
                ]
                second_challenge = secondary.post(
                    "/api/auth/email/request",
                    json={"email": "switching@example.com", "locale": "en"},
                ).json()
                self.assertEqual(
                    secondary.post(
                        "/api/auth/email/verify",
                        json={
                            "challenge_id": second_challenge["challenge_id"],
                            "email": "switching@example.com",
                            "code": second_challenge["development_code"],
                        },
                    ).status_code,
                    200,
                )

            secondary.headers.update(
                {"X-CSRF-Token": secondary.cookies.get("everstory_csrf")}
            )
            investigations = secondary.get("/api/auth/investigations").json()[
                "investigations"
            ]
            self.assertEqual(
                {item["id"] for item in investigations},
                {primary_runtime, secondary_runtime},
            )
            self.assertTrue(
                next(
                    item for item in investigations if item["id"] == secondary_runtime
                )["current"]
            )

            self.authorize_writes(outsider)
            outsider_runtime = outsider.get("/api/auth/session").json()["runtime_id"]
            self.assertEqual(
                outsider.get("/api/auth/investigations").status_code, 403
            )
            self.assertEqual(
                secondary.post(
                    f"/api/auth/investigations/{outsider_runtime}/activate",
                    json={},
                ).status_code,
                404,
            )

            activated = secondary.post(
                f"/api/auth/investigations/{primary_runtime}/activate", json={}
            )
            self.assertEqual(activated.status_code, 200)
            self.assertEqual(activated.json()["runtime_id"], primary_runtime)
            self.assertEqual(
                secondary.cookies.get("everstory_runtime"), primary_runtime
            )
            self.assertEqual(secondary.get("/api/world").json()["turn"], primary_turn)
        finally:
            primary.close()
            secondary.close()
            outsider.close()

    def test_forged_runtime_cookie_is_not_an_authority_boundary(self):
        other = TestClient(self.client.app)
        try:
            other.get("/api/auth/session")
            stolen_runtime = self.client.cookies.get("everstory_runtime")
            other.cookies.set("everstory_runtime", stolen_runtime)

            identity = other.get("/api/auth/session").json()

            self.assertNotEqual(identity["user"]["id"], self.client.get(
                "/api/auth/session"
            ).json()["user"]["id"])
            self.assertNotEqual(identity["runtime_id"], stolen_runtime)
        finally:
            other.close()

    def test_game_shell_exposes_shared_chinese_english_locale(self):
        page = self.client.get("/").text
        locale = self.client.get("/static/i18n.js").text
        self.assertIn('id="game-language"', page)
        self.assertIn('id="account-btn"', page)
        self.assertIn('id="account-panel"', page)
        self.assertIn('src="/static/auth.js?v=4"', page)
        self.assertIn('data-i18n="worldStable"', page)
        self.assertIn('src="/static/i18n.js?v=7"', page)
        self.assertIn('localStorage.getItem("everstory_locale")', locale)
        self.assertIn("证明灯塔遭到人为破坏", locale)
        self.assertIn('"lighthouse_lit": "灯塔已点亮"', locale)
        self.assertIn("You move to the", locale)

    def test_chinese_locale_controls_runtime_and_team_outputs(self):
        turn = self.client.post(
            "/api/turn",
            json={"text": "move to lighthouse_ground", "locale": "zh-CN"},
        )
        self.assertEqual(turn.status_code, 200)
        self.assertIn("你", turn.json()["reply"])

        team = self.client.post(
            "/api/agents/chat",
            json={"text": "检查当前位置", "locale": "zh-CN"},
        )
        self.assertEqual(team.status_code, 200)
        agent_messages = [
            item["text"] for item in team.json()["new_messages"] if not item["human"]
        ]
        self.assertTrue(agent_messages)
        self.assertTrue(any("我" in text or "假设" in text for text in agent_messages))

        gameplay = self.client.get("/static/gameplay-core.js").text
        team_script = self.client.get("/static/team-chat.js").text
        self.assertIn("EverStoryI18n?.locale()", gameplay)
        self.assertIn("EverStoryI18n?.locale()", team_script)

    def test_console_navigation_preserves_the_game_tab(self):
        game = self.client.get("/").text
        console = self.client.get("/settings").text
        gameplay = self.client.get("/static/gameplay-core.js").text
        app_script = self.client.get("/static/app.js").text
        settings = self.client.get("/static/settings.js").text
        auth = self.client.get("/static/auth.js").text

        self.assertIn('target="_blank"', game)
        self.assertIn('rel="opener"', game)
        self.assertNotIn('window.open("/settings"', gameplay)
        self.assertIn(
            'window.open(settingsButton.href, "everstory-api-console")',
            app_script,
        )
        self.assertIn('app.js?v=20', game)
        self.assertIn('id="back-to-game"', console)
        self.assertIn('href="/?resume=1"', console)
        self.assertIn("window.opener.focus()", settings)
        self.assertIn("window.close()", settings)
        self.assertIn('headers.set("X-CSRF-Token", csrf)', auth)

    def test_large_workspace_shells_are_available(self):
        page = self.client.get("/").text
        team_css = self.client.get("/static/team-chat.css").text
        ui_css = self.client.get("/static/ui-tweaks.css").text

        self.assertIn('id="truth-backdrop"', page)
        self.assertIn("width: min(1180px, calc(100vw - 48px))", team_css)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", ui_css)

    def test_main_dialogue_is_separated_from_the_intel_rail(self):
        page = self.client.get("/").text
        ui_css = self.client.get("/static/ui-tweaks.css").text

        self.assertIn('ui-tweaks.css?v=20', page)
        self.assertIn("left: clamp(390px, 31vw, 470px)", ui_css)
        self.assertIn("#messages { left: 7%; right: 7%; }", ui_css)
        self.assertIn(".scene-presence:not(:has(.presence-card))", ui_css)
        self.assertIn("left: 11%", ui_css)
        self.assertIn("font-size: 16px", ui_css)
        gameplay = self.client.get("/static/gameplay-core.js").text
        app_script = self.client.get("/static/app.js").text
        self.assertIn("worldNarrator", gameplay)
        self.assertIn("assistant-speaker", gameplay)
        self.assertNotIn('<rect x="4" y="8"', app_script)

    def test_main_chat_shows_player_and_humanizes_shortcut_commands(self):
        page = self.client.get("/").text
        ui_css = self.client.get("/static/ui-tweaks.css").text
        gameplay = self.client.get("/static/gameplay-core.js").text
        app_script = self.client.get("/static/app.js").text

        self.assertNotIn(".msg.user { display: none; }", ui_css)
        self.assertIn(".user-message-content", ui_css)
        self.assertIn("data-player-speaker", app_script)
        self.assertIn("data-display", app_script)
        self.assertIn("send(text, displayText = text)", gameplay)
        self.assertIn('addMessage("user", displayText)', gameplay)
        self.assertIn('gameplay-core.js?v=8', page)

    def test_console_and_game_share_the_same_locale_values(self):
        console = self.client.get("/settings").text
        settings = self.client.get("/static/settings.js").text

        self.assertIn('<option value="en">English</option>', console)
        self.assertNotIn('<option value="en-US">', console)
        self.assertIn('storedLocale==="en-US"?"en"', settings)
        self.assertIn("window.opener.EverStoryI18n?.setLocale(locale)", settings)

    def test_signal_console_and_session_settings(self):
        self.assertEqual(self.client.get("/settings").status_code, 200)
        initial = self.client.get("/api/llm/settings").json()
        self.assertEqual(initial["mode"], "stub")
        self.assertNotIn("api_key", str(initial))

        response = self.client.put(
            "/api/llm/settings",
            json={
                "mode": "stub",
                "strong": {
                    "base_url": "https://reasoning.test/v1",
                    "model": "same-model",
                    "api_key": "secret-strong-1234",
                },
                "cheap": {
                    "base_url": "https://story.test/v1",
                    "model": "same-model",
                    "api_key": "secret-cheap-5678",
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        raw = response.text
        self.assertNotIn("secret-strong", raw)
        self.assertNotIn("secret-cheap", raw)
        settings = response.json()["settings"]
        self.assertEqual(settings["strong"]["masked_key"], "••••••••1234")
        self.assertEqual(settings["cheap"]["masked_key"], "••••••••5678")

        # A new world keeps the active API route for this browser session.
        self.client.post("/api/reset")
        after_reset = self.client.get("/api/llm/settings").json()
        self.assertEqual(after_reset["strong"]["base_url"], "https://reasoning.test/v1")
        test = self.client.post("/api/llm/test", json={"role": "strong"}).json()
        self.assertTrue(test["ok"])

    def test_signal_console_rejects_insecure_remote_url(self):
        response = self.client.put(
            "/api/llm/settings",
            json={
                "strong": {
                    "base_url": "http://example.com/v1",
                    "model": "model",
                }
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("HTTPS", response.json()["error"])

    def test_agent_connection_pool_and_routes(self):
        initial = self.client.get("/api/llm/settings").json()
        routes = {
            agent["id"]: ("story" if agent["id"] in {"narrator", "npc_dialogue", "field_investigator"} else "reasoning")
            for agent in initial["agent_catalog"]
        }
        routes["case_analyst"] = "analyst_api"
        response = self.client.put(
            "/api/llm/settings",
            json={
                "mode": "stub",
                "connections": {
                    "reasoning": {
                        "name": "Shared runtime",
                        "base_url": "https://runtime.test/v1",
                        "model": "runtime-model",
                    },
                    "story": {
                        "name": "Story runtime",
                        "base_url": "https://story.test/v1",
                        "model": "story-model",
                    },
                    "analyst_api": {
                        "name": "Analyst dedicated",
                        "base_url": "https://analyst.test/v1",
                        "model": "analysis-model",
                        "api_key": "analyst-secret-7788",
                    },
                },
                "agent_routes": routes,
            },
        )
        self.assertEqual(response.status_code, 200)
        settings = response.json()["settings"]
        self.assertEqual(settings["agent_routes"]["case_analyst"], "analyst_api")
        self.assertEqual(settings["connections"]["analyst_api"]["model"], "analysis-model")
        self.assertEqual(settings["connections"]["analyst_api"]["credential_source"], "personal")
        self.assertFalse(settings["credential_policy"]["fallback_to_platform"])
        self.assertNotIn("analyst-secret", response.text)
        self.assertIn("diagnostics", settings)

    def test_platform_credentials_are_read_only_and_personal_settings_are_isolated(self):
        initial = self.client.get("/api/llm/settings").json()
        self.assertEqual(initial["connections"]["reasoning"]["credential_source"], "platform")
        blocked = self.client.put(
            "/api/llm/settings",
            json={
                "mode": "stub",
                "connections": {
                    "reasoning": {
                        "name": "Reasoning API",
                        "base_url": initial["connections"]["reasoning"]["base_url"],
                        "model": initial["connections"]["reasoning"]["model"],
                        "api_key": "attempted-overwrite",
                    },
                    "story": initial["connections"]["story"],
                },
                "agent_routes": initial["agent_routes"],
            },
        )
        self.assertEqual(blocked.status_code, 400)

        routes = dict(initial["agent_routes"])
        routes["narrator"] = "player_api"
        payload_connections = {
            key: {
                "name": value["name"], "base_url": value["base_url"], "model": value["model"]
            }
            for key, value in initial["connections"].items()
        }
        payload_connections["player_api"] = {
            "name": "Player API", "base_url": "https://player.test/v1",
            "model": "player-model", "api_key": "player-secret",
        }
        saved = self.client.put(
            "/api/llm/settings",
            json={"mode": "stub", "connections": payload_connections, "agent_routes": routes},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["settings"]["agent_routes"]["narrator"], "player_api")

        from everstory.api.main import app
        other = TestClient(app)
        self.authorize_writes(other)
        other.post("/api/reset")
        self.assertNotIn("player_api", other.get("/api/llm/settings").json()["connections"])

    def test_player_can_disable_and_restore_a_platform_model_for_own_session(self):
        initial = self.client.get("/api/llm/settings").json()
        self.assertIn("reasoning", initial["platform_catalog"])
        remaining = {
            key: {
                "name": value["name"],
                "base_url": value["base_url"],
                "model": value["model"],
            }
            for key, value in initial["connections"].items()
            if key != "reasoning"
        }
        routes = {
            agent: ("story" if route == "reasoning" else route)
            for agent, route in initial["agent_routes"].items()
        }
        disabled = self.client.put(
            "/api/llm/settings",
            json={"mode": "stub", "connections": remaining, "agent_routes": routes},
        )
        self.assertEqual(disabled.status_code, 200)
        disabled_settings = disabled.json()["settings"]
        self.assertNotIn("reasoning", disabled_settings["connections"])
        self.assertIn("reasoning", disabled_settings["platform_catalog"])

        remaining["reasoning"] = {
            "name": initial["platform_catalog"]["reasoning"]["name"],
            "base_url": initial["platform_catalog"]["reasoning"]["base_url"],
            "model": initial["platform_catalog"]["reasoning"]["model"],
        }
        restored = self.client.put(
            "/api/llm/settings",
            json={"mode": "stub", "connections": remaining, "agent_routes": routes},
        )
        self.assertEqual(restored.status_code, 200)
        restored_connection = restored.json()["settings"]["connections"]["reasoning"]
        self.assertEqual(restored_connection["credential_source"], "platform")
        self.assertEqual(restored_connection["masked_key"], "")

    def test_legacy_partial_override_cannot_reclassify_a_platform_key(self):
        response = self.client.put(
            "/api/llm/settings",
            json={
                "mode": "stub",
                "cheap": {
                    "base_url": "https://player-story.test/v1",
                    "model": "player-story",
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["settings"]
        self.assertEqual(data["connections"]["reasoning"]["credential_source"], "platform")
        self.assertEqual(data["connections"]["story"]["credential_source"], "personal")
        self.assertFalse(data["connections"]["story"]["key_configured"])

    def test_usage_endpoint_and_console_chart_contract(self):
        usage = self.client.get(
            "/api/llm/usage?range=7d&metric=tokens&group_by=source"
        )
        self.assertEqual(usage.status_code, 200)
        data = usage.json()
        self.assertEqual(len(data["series"]), 7)
        self.assertIn("platform_quota", data["summary"])
        self.assertIn("logs", data)
        bad = self.client.get("/api/llm/usage?range=year")
        self.assertEqual(bad.status_code, 400)

        page = self.client.get("/settings").text
        script = self.client.get("/static/settings.js").text
        self.assertIn('id="usage-chart"', page)
        self.assertIn('id="usage-metric"', page)
        self.assertIn("credential_source", script)
        self.assertNotIn("BYOK 不回退平台", page)
        self.assertNotIn("凭据隔离", page)
        self.assertIn('data-i18n="addConnection"', page)
        self.assertIn("data-remove-provider", script)

    def test_team_chat_has_identity_and_agent_challenge(self):
        history = self.client.get("/api/agents/chat").json()
        participants = {member["id"]: member for member in history["participants"]}
        self.assertTrue(participants["player"]["human"])
        self.assertEqual(participants["player"]["role"], "Lead Investigator")
        self.assertIn("case_analyst", participants)
        self.assertIn("skeptic", participants)

        before_turn = self.client.get("/api/world").json()["turn"]
        response = self.client.post(
            "/api/agents/chat",
            json={"text": "I think the lighthouse failure proves sabotage."},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        created = data["new_messages"]
        self.assertEqual([message["sender_id"] for message in created], [
            "player", "case_analyst", "skeptic"
        ])
        self.assertEqual(created[0]["initials"], "YOU")
        self.assertEqual(created[2]["kind"], "challenge")
        self.assertEqual(created[2]["reply_to"], created[1]["id"])
        self.assertIn(created[1]["sender_name"], created[2]["text"])
        self.assertEqual(len(data["tasks"]), 1)
        self.assertEqual(data["tasks"][0]["status"], "proposed")
        self.assertEqual(created[1]["task_id"], data["tasks"][0]["id"])
        self.assertEqual(self.client.get("/api/world").json()["turn"], before_turn)

    def test_player_approves_grounded_scene_inspection(self):
        before = self.client.get("/api/world").json()
        proposal = self.client.post(
            "/api/agents/chat",
            json={"text": "@field inspect the current scene and report confirmed evidence."},
        ).json()
        task = proposal["tasks"][0]
        self.assertEqual(task["agent_id"], "field_investigator")
        self.assertEqual(task["type"], "inspect_scene")
        self.assertEqual(task["status"], "proposed")
        self.assertEqual(proposal["evidence"], [])

        response = self.client.post(f"/api/agents/tasks/{task['id']}/approve")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        approved = next(item for item in result["tasks"] if item["id"] == task["id"])
        self.assertEqual(approved["status"], "completed")
        self.assertGreaterEqual(len(result["evidence"]), 1)
        self.assertTrue(all(
            item["location_id"] == before["player"]["location_id"]
            for item in result["evidence"]
        ))
        self.assertEqual(result["new_messages"][0]["kind"], "task_result")
        self.assertEqual(result["new_messages"][0]["task_id"], task["id"])
        self.assertEqual(self.client.get("/api/world").json()["turn"], before["turn"])

        repeated = self.client.post(f"/api/agents/tasks/{task['id']}/approve")
        self.assertEqual(repeated.status_code, 400)

    def test_approved_agent_travel_executes_world_action(self):
        before = self.client.get("/api/world").json()
        proposal = self.client.post(
            "/api/agents/chat",
            json={"text": "@field travel to Dock with the team."},
        ).json()
        task = proposal["tasks"][0]
        self.assertEqual(task["type"], "travel")
        self.assertEqual(task["action"], {"type": "move", "params": {"to": "dock"}})
        self.assertEqual(self.client.get("/api/world").json()["turn"], before["turn"])

        approved = self.client.post(f"/api/agents/tasks/{task['id']}/approve").json()
        self.assertTrue(approved["action_result"]["ok"])
        self.assertEqual(approved["world"]["player"]["location_id"], "dock")
        self.assertEqual(approved["world"]["turn"], before["turn"] + 1)
        evidence = next(item for item in approved["evidence"] if item["task_id"] == task["id"])
        self.assertEqual(evidence["type"], "scene")

    def test_approved_agent_examine_and_interview_record_evidence(self):
        self.client.post("/api/turn", json={"text": "move to cottage"})
        examine = self.client.post(
            "/api/agents/chat",
            json={"text": "@field examine the lantern."},
        ).json()["tasks"][0]
        self.assertEqual(examine["type"], "examine")
        examined = self.client.post(f"/api/agents/tasks/{examine['id']}/approve").json()
        self.assertIn("cold and dark", examined["action_result"]["message"])
        self.assertTrue(any(item["type"] == "item" for item in examined["evidence"]))

        self.client.post("/api/turn", json={"text": "move to lighthouse_ground"})
        interview = self.client.post(
            "/api/agents/chat",
            json={"text": "@field interview Mara."},
        ).json()["tasks"][-1]
        self.assertEqual(interview["type"], "interview")
        interviewed = self.client.post(f"/api/agents/tasks/{interview['id']}/approve").json()
        self.assertIn("sea has grown restless", interviewed["action_result"]["message"])
        self.assertTrue(any(item["type"] == "testimony" for item in interviewed["evidence"]))

    def test_stale_agent_action_requires_fresh_proposal(self):
        proposal = self.client.post(
            "/api/agents/chat", json={"text": "@field travel to Dock."}
        ).json()["tasks"][0]
        self.client.post("/api/turn", json={"text": "move to lighthouse_ground"})
        before = self.client.get("/api/world").json()["turn"]
        response = self.client.post(f"/api/agents/tasks/{proposal['id']}/approve")
        self.assertEqual(response.status_code, 400)
        self.assertIn("fresh proposal", response.json()["error"])
        self.assertEqual(self.client.get("/api/world").json()["turn"], before)

    def test_director_can_propose_authoritative_accusation(self):
        self.client.post("/api/turn", json={"text": "move to dock"})
        proposal = self.client.post(
            "/api/agents/chat",
            json={"text": "@director accuse Elias Ward using the current case."},
        ).json()
        task = proposal["tasks"][0]
        self.assertEqual(task["agent_id"], "case_director")
        self.assertEqual(task["type"], "accuse")
        self.assertEqual(task["action"]["params"]["target"], "elias")
        approved = self.client.post(f"/api/agents/tasks/{task['id']}/approve")
        self.assertEqual(approved.status_code, 400)
        self.assertIn("case board is not ready", approved.json()["error"])
        self.assertFalse(self.client.get("/api/world").json()["flags"]["case_solved"])

    def test_main_chat_routes_authoritative_evidence_to_team(self):
        self.client.post("/api/turn", json={"text": "move to cottage"})
        before = self.client.get("/api/world").json()
        blocked = self.client.post(
            "/api/turn", json={"text": "examine the annotated tide chart", "locale": "en"}
        ).json()
        self.assertFalse(blocked["events"][0]["ok"])
        self.assertIn("Investigation Room", blocked["events"][0]["message"])
        self.assertEqual(blocked["world"]["turn"], before["turn"])
        self.assertFalse(blocked["world"]["flags"].get("verified_tide_timeline", False))

    def test_complete_multi_agent_sabotage_case_via_approval_pipeline(self):
        def propose_and_approve(text, task_type):
            proposal = self.client.post("/api/agents/chat", json={"text": text}).json()
            task = next(
                item for item in reversed(proposal["tasks"])
                if item["status"] == "proposed" and item["type"] == task_type
            )
            response = self.client.post(f"/api/agents/tasks/{task['id']}/approve")
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()

        propose_and_approve("@field travel to Dock.", "travel")
        propose_and_approve("@field interview Elias Ward.", "interview")
        self.client.post("/api/turn", json={"text": "move to cottage"})
        propose_and_approve("@field interview Dr. Celia Thorne.", "interview")
        propose_and_approve("@field examine the annotated tide chart.", "examine")
        self.client.post("/api/turn", json={"text": "move to lighthouse_ground"})
        propose_and_approve("@field interview Mara.", "interview")
        for command in ("move to lighthouse_tower", "move to lantern_room"):
            self.client.post("/api/turn", json={"text": command})
        propose_and_approve("@field examine the severed fuel line.", "examine")
        for command in (
            "move to lighthouse_tower", "move to lighthouse_ground",
            "move to cottage", "move to dock", "move to boat_shed",
        ):
            self.client.post("/api/turn", json={"text": command})
        propose_and_approve("@field examine the salvage ledger.", "examine")
        self.client.post("/api/turn", json={"text": "move to dock"})
        reviewed = propose_and_approve("@analyst review the confirmed case record.", "review_case")
        self.assertTrue(reviewed["case_readiness"]["ready"])
        solved = propose_and_approve("@director accuse Elias Ward.", "accuse")

        self.assertTrue(solved["world"]["flags"]["case_solved"])
        self.assertEqual(solved["world"]["flags"]["accused"], "elias")
        evidence_types = {item["type"] for item in solved["evidence"]}
        self.assertTrue({"scene", "testimony", "item", "conclusion"} <= evidence_types)
        self.assertIn("Elias Ward breaks", solved["action_result"]["message"])

    def test_team_chat_is_isolated_between_browser_sessions(self):
        other = TestClient(self.client.app)
        try:
            self.client.post("/api/agents/chat", json={"text": "private team note"})
            first = self.client.get("/api/agents/chat").json()["messages"]
            second = other.get("/api/agents/chat").json()["messages"]
            self.assertGreater(len(first), len(second))
            self.assertFalse(any("private team note" in item["text"] for item in second))
            self.assertEqual(other.get("/api/agents/chat").json()["tasks"], [])
        finally:
            other.close()

    def test_static_assets_are_cached_and_compressed(self):
        image = self.client.get("/static/img/scenes/cottage.webp")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["content-type"], "image/webp")
        self.assertIn("max-age=86400", image.headers.get("cache-control", ""))

        css = self.client.get(
            "/static/ui-tweaks.css", headers={"Accept-Encoding": "gzip"}
        )
        self.assertEqual(css.status_code, 200)
        self.assertEqual(css.headers.get("content-encoding"), "gzip")

    def test_turn_rejects_invalid_action(self):
        data = self.client.post("/api/turn", json={"text": "move to cave"}).json()
        self.assertFalse(data["events"][0]["ok"])
        self.assertEqual(
            data["world"]["player"]["location_name"], "Storm Shore"
        )

    def test_turn_applies_valid_action(self):
        data = self.client.post(
            "/api/turn", json={"text": "move to lighthouse_ground"}
        ).json()
        self.assertTrue(data["events"][0]["ok"])
        self.assertEqual(
            data["world"]["player"]["location_name"], "Lighthouse Ground Floor"
        )

    def test_clients_have_isolated_worlds(self):
        other = TestClient(self.client.app)
        try:
            self.client.post("/api/turn", json={"text": "wait"})
            first_world = self.client.get("/api/world").json()
            other_world = other.get("/api/world").json()
            self.assertEqual(first_world["turn"], 1)
            self.assertEqual(other_world["turn"], 0)
            self.assertNotEqual(
                self.client.cookies.get("everstory_runtime"),
                other.cookies.get("everstory_runtime"),
            )
        finally:
            other.close()

    def test_saves_are_isolated_by_client(self):
        import tempfile
        import everstory.persistence as persistence

        other = TestClient(self.client.app)
        original = persistence.SAVES_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                persistence.SAVES_DIR = tmp
                self.client.post("/api/save", json={"name": "private"})
                self.assertEqual(len(self.client.get("/api/saves").json()["saves"]), 1)
                self.assertEqual(other.get("/api/saves").json()["saves"], [])
        finally:
            persistence.SAVES_DIR = original
            other.close()

    def test_same_session_turns_are_serialized(self):
        from concurrent.futures import ThreadPoolExecutor

        other = TestClient(self.client.app)
        other.cookies.set(
            "everstory_runtime", self.client.cookies.get("everstory_runtime")
        )
        other.cookies.set(
            "everstory_auth", self.client.cookies.get("everstory_auth")
        )
        other.cookies.set(
            "everstory_csrf", self.client.cookies.get("everstory_csrf")
        )
        other.headers.update(
            {"X-CSRF-Token": self.client.cookies.get("everstory_csrf")}
        )
        try:
            def wait_turn(client):
                return client.post("/api/turn", json={"text": "wait"}).json()["turn"]

            with ThreadPoolExecutor(max_workers=2) as pool:
                turns = list(pool.map(wait_turn, [self.client, other]))
            self.assertEqual(sorted(turns), [1, 2])
            self.assertEqual(self.client.get("/api/world").json()["turn"], 2)
        finally:
            other.close()

    def test_reset(self):
        self.client.post("/api/turn", json={"text": "wait"})
        self.client.post("/api/reset")
        world = self.client.get("/api/world").json()
        self.assertEqual(world["turn"], 0)
        self.assertEqual(world["player"]["location_name"], "Storm Shore")

    def test_save_and_load(self):
        import tempfile
        from everstory.persistence import SAVES_DIR

        with tempfile.TemporaryDirectory() as tmp:
            original = SAVES_DIR
            import everstory.persistence as persistence

            persistence.SAVES_DIR = tmp
            try:
                self.client.post("/api/turn", json={"text": "wait"})
                saved = self.client.post(
                    "/api/save", json={"name": "apitest"}
                ).json()
                self.assertTrue(saved["ok"])
                self.client.post("/api/reset")
                world = self.client.get("/api/world").json()
                self.assertEqual(world["turn"], 0)

                saves = self.client.get("/api/saves").json()["saves"]
                self.assertGreaterEqual(len(saves), 1)
                loaded = self.client.post(
                    "/api/load", json={"path": saves[0]["path"]}
                ).json()
                self.assertGreater(loaded["turn"], 0)
            finally:
                persistence.SAVES_DIR = original

    def test_save_and_load_restores_main_conversation(self):
        import tempfile
        import everstory.persistence as persistence

        original = persistence.SAVES_DIR
        with tempfile.TemporaryDirectory() as tmp:
            persistence.SAVES_DIR = tmp
            try:
                self.client.post("/api/turn", json={"text": "move to cottage"})
                before = self.client.get("/api/conversation").json()["messages"]
                self.assertEqual([item["role"] for item in before], ["user", "assistant"])
                self.assertEqual(before[1]["speaker_id"], "world_narrator")
                self.client.post("/api/save", json={"name": "conversation"})
                self.client.post("/api/turn", json={"text": "wait"})
                save_path = self.client.get("/api/saves").json()["saves"][0]["path"]
                self.client.post("/api/load", json={"path": save_path})
                restored = self.client.get("/api/conversation").json()["messages"]
                self.assertEqual(restored, before)
            finally:
                persistence.SAVES_DIR = original

    def test_save_and_load_restores_investigation_memory(self):
        import tempfile
        import everstory.persistence as persistence

        original = persistence.SAVES_DIR
        with tempfile.TemporaryDirectory() as tmp:
            persistence.SAVES_DIR = tmp
            try:
                proposal = self.client.post(
                    "/api/agents/chat",
                    json={"text": "@field inspect this scene for confirmed evidence"},
                ).json()
                task_id = proposal["tasks"][0]["id"]
                approved = self.client.post(
                    f"/api/agents/tasks/{task_id}/approve"
                ).json()
                evidence_ids = [item["id"] for item in approved["evidence"]]

                saved = self.client.post(
                    "/api/save", json={"name": "case-memory"}
                ).json()
                self.assertEqual(saved["evidence"], len(evidence_ids))
                self.client.post("/api/reset")
                self.assertEqual(
                    self.client.get("/api/agents/chat").json()["evidence"], []
                )

                loaded = self.client.post(
                    "/api/load", json={"path": saved["path"]}
                )
                self.assertEqual(loaded.status_code, 200)
                restored = self.client.get("/api/agents/chat").json()
                self.assertEqual(
                    [item["id"] for item in restored["evidence"]], evidence_ids
                )
                restored_task = next(
                    item for item in restored["tasks"] if item["id"] == task_id
                )
                self.assertEqual(restored_task["status"], "completed")
                self.assertTrue(any(
                    item.get("task_id") == task_id
                    and item["kind"] == "task_result"
                    for item in restored["messages"]
                ))
            finally:
                persistence.SAVES_DIR = original


if __name__ == "__main__":
    unittest.main()
