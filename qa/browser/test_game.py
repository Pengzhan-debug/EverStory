import re
from urllib.parse import urlsplit

import allure
import pytest
from playwright.sync_api import expect

from qa.browser.page_objects import GamePage

pytestmark = [allure.feature("Browser journeys / Playwright")]


@pytest.fixture
def game(page, base_url):
    return GamePage(page, base_url).open()


def test_streamed_move_updates_world_and_hud(game):
    result = game.send("move to dock")
    assert result["turn"] == 1
    game.expect_location("dock")
    expect(game.page.locator("#loc-chip")).to_contain_text("Dock")
    expect(game.page.locator("#messages .msg.assistant").last).to_be_visible()


def test_rejected_action_keeps_state_and_input_usable(game):
    before = game.world()["state_hash"]
    rejected = game.send("move to cave")
    assert rejected["state_hash"] == before
    expect(game.input).to_be_enabled()
    # The engine counts attempts, including rejected actions, as turns.
    assert game.send("move to dock")["turn"] == rejected["turn"] + 1


def test_team_proposal_requires_click_to_advance(game):
    page = game.page
    before = game.world()["state_hash"]
    page.locator("#team-btn").click()
    expect(page.locator("#team-panel")).to_have_attribute("aria-hidden", "false")
    page.locator("#team-input").fill("@field travel to Dock.")
    with page.expect_response(
        lambda response: response.url.endswith("/api/agents/chat") and response.request.method == "POST"
    ) as proposed:
        page.locator("#team-form button[type=submit]").click()
    assert proposed.value.status == 200
    assert game.world()["state_hash"] == before
    approve = page.locator("#team-messages [data-approve-task]").first
    expect(approve).to_be_visible()
    with page.expect_response(re.compile(r"/api/agents/tasks/.+/approve$")) as approved:
        approve.click()
    assert approved.value.status == 200
    expect(page.locator("#team-status")).to_contain_text("Approved result returned")
    assert game.world()["turn"] == 1
    game.expect_location("dock")


def test_save_change_and_restore_from_toolbar(game):
    page = game.page
    game.send("move to dock")
    saved = game.world()["state_hash"]
    with page.expect_response("**/api/save") as response:
        page.locator("#save-btn").click()
    assert response.value.status == 200
    assert game.send("wait")["turn"] == 2
    with page.expect_response("**/api/load") as response:
        page.locator("#load-btn").click()
    assert response.value.status == 200
    page.wait_for_function("hash => window.EverStory?.world?.state_hash === hash", arg=saved)
    assert game.world()["state_hash"] == saved


def test_reload_restores_state_and_conversation(game):
    game.send("move to dock")
    saved = game.world()["state_hash"]
    game.page.reload()
    game.expect_location("dock")
    assert game.world()["state_hash"] == saved
    # The UI translates raw commands into display labels. Assert the stored command too.
    expect(game.page.locator("#messages .msg.user").last).to_have_attribute("data-command", "move to dock")
    expect(game.page.locator("#messages .msg.user").last).to_contain_text("Travel to Dock")


def test_language_switch_persists_without_changing_world(game):
    before = game.world()["state_hash"]
    game.page.locator("#game-language").select_option("zh-CN")
    expect(game.page.locator("#game-language")).to_have_value("zh-CN")
    game.page.reload()
    expect(game.page.locator("#game-language")).to_have_value("zh-CN")
    assert game.world()["state_hash"] == before


def test_browser_contexts_have_isolated_worlds(game, new_context, base_url):
    game.send("move to dock")
    other = new_context()
    other.route("**/*", lambda route: route.continue_()
                if urlsplit(route.request.url).hostname in {"127.0.0.1", "localhost"}
                else route.abort())
    other.add_init_script("sessionStorage.setItem('everstory-intro-seen','1');")
    second = GamePage(other.new_page(), base_url).open()
    assert second.world()["turn"] == 0
    assert second.send("wait")["turn"] == 1
    assert game.world()["player"]["location_id"] == "dock"
    assert second.world()["player"]["location_id"] != "dock"


def test_network_failure_releases_input_and_allows_retry(game):
    page = game.page
    before = game.world()["state_hash"]
    page.route("**/api/turn/stream", lambda route: route.abort("connectionfailed"), times=1)
    game.input.fill("move to dock")
    page.locator("#input-form button[type=submit]").click()
    expect(page.locator("#messages .msg.assistant").last).to_contain_text("⚠")
    expect(game.input).to_be_enabled()
    assert game.world()["state_hash"] == before
    assert game.send("move to dock")["turn"] == 1


def test_settings_popup_preserves_game_state(game):
    game.send("move to dock")
    before = game.world()["state_hash"]
    with game.page.expect_popup() as popup:
        game.page.locator("#settings-btn").click()
    popup.value.wait_for_load_state("domcontentloaded")
    assert "/settings" in popup.value.url
    popup.value.close()
    assert game.world()["state_hash"] == before
    expect(game.input).to_be_enabled()


def test_narrow_viewport_can_submit_action(game):
    game.page.set_viewport_size({"width": 390, "height": 844})
    assert game.send("move to dock")["turn"] == 1
    expect(game.input).to_be_visible()
