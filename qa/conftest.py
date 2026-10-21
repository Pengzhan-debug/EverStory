import pytest

from qa.runtime import local_server


@pytest.fixture(scope="session")
def base_url():
    with local_server() as url:
        yield url
