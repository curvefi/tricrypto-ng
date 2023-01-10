import boa
import pytest


@pytest.fixture(scope="module")
def weth(deployer):
    with boa.env.prank(deployer):
        return boa.load("contracts/mocks/WETH.vy")


@pytest.fixture(scope="module")
def usdt(deployer):
    with boa.env.prank(deployer):
        return boa.load("contracts/mocks/ERC20Mock.vy", "USD", "USD", 18)


@pytest.fixture(scope="module")
def wbtc(deployer):
    with boa.env.prank(deployer):
        return boa.load("contracts/mocks/ERC20Mock.vy", "USD", "USD", 18)


@pytest.fixture(scope="module")
def coins(usdt, wbtc, weth):
    yield [usdt, wbtc, weth]


@pytest.fixture(scope="module")
def pool_coins(coins):
    yield coins
