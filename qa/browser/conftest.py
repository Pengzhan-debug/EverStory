from urllib.parse import urlsplit

import allure
import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1365, "height": 900},
            "locale": "en-US", "reduced_motion": "reduce"}


@pytest.fixture(autouse=True)
def local_resources_only(context):
    # The product references Google Fonts; these tests must not need the internet.
    context.route("**/*", lambda route: route.continue_()
                  if urlsplit(route.request.url).hostname in {"127.0.0.1", "localhost"}
                  else route.abort())
    context.add_init_script("if (!localStorage.getItem('everstory_locale')) localStorage.setItem('everstory_locale','en');")


@pytest.fixture(autouse=True)
def browser_evidence(page):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield
    if not page.is_closed():
        allure.attach(page.screenshot(full_page=True), "Final page", allure.attachment_type.PNG)
    if errors:
        allure.attach("\n".join(errors), "Uncaught browser errors", allure.attachment_type.TEXT)
    assert not errors, errors
