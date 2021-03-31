# Fixtures in here are available for all tests in any file.
import pytest


@pytest.fixture
def when():
    from mockito import when, unstub
    yield when   # invokes the test that this fixture was passed to
    unstub()     # once test is complete, remove mocks/stubs setup above
