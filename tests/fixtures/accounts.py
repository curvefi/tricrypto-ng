import pytest


def _format_addr(t):
    if isinstance(t, str):
        t = t.encode("utf-8")
    return t.rjust(20, b"\x00")


@pytest.fixture(scope="module")
def deployer():
    yield _format_addr("deployer")


@pytest.fixture(scope="module")
def owner():
    yield _format_addr("fiddy")


@pytest.fixture(scope="module")
def fee_receiver():
    yield _format_addr("ecb")


@pytest.fixture(scope="module")
def user():
    yield _format_addr("user")
