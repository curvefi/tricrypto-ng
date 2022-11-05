import boa
import pytest


@pytest.fixture(scope="module")
def deployer():
    return boa.env.generate_address()


@pytest.fixture(scope="module")
def owner():
    return boa.env.generate_address()


@pytest.fixture(scope="module")
def fee_receiver():
    return boa.env.generate_address()


@pytest.fixture(scope="module")
def user():
    return boa.env.generate_address()
