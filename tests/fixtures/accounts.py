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
    acc = boa.env.generate_address()
    boa.env.set_balance(acc, 10**25)
    return acc


@pytest.fixture(scope="module")
def users():
    accs = [boa.env.generate_address() for i in range(10)]
    for acc in accs:
        boa.env.set_balance(acc, 10**25)
    return acc
