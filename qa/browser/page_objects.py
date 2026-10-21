from playwright.sync_api import expect


class GamePage:
    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url
        self.input = page.locator("#input")

    def open(self):
        self.page.goto(self.base_url)
        # The intro automatically dismisses after 3.6s; reduced-motion CSS may
        # make ENTER unclickable while it is already fading out.
        expect(self.page.locator("#intro-layer")).to_have_count(0, timeout=15000)
        expect(self.input).to_be_enabled()
        self.page.wait_for_function("window.EverStory?.world?.state_hash")
        return self

    def world(self):
        response = self.page.request.get(self.base_url + "/api/world")
        assert response.ok
        return response.json()

    def send(self, text):
        self.input.fill(text)
        with self.page.expect_response("**/api/turn/stream") as response:
            self.page.locator("#input-form button[type=submit]").click()
        assert response.value.status == 200
        expect(self.input).to_be_enabled()
        return self.world()

    def expect_location(self, location):
        self.page.wait_for_function("location => window.EverStory?.world?.player?.location_id === location", arg=location)
        assert self.world()["player"]["location_id"] == location
