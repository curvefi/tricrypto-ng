import boa
import pytest


@pytest.fixture(scope="module")
def weth(deployer):
    with boa.env.prank(deployer):
        yield boa.load("contracts/mocks/WETH.vy")


@pytest.fixture(scope="module")
def usdt(deployer):
    with boa.env.prank(deployer):
        yield boa.load("contracts/mocks/ERC20Mock.vy", "USDT", "USDT", 6)


@pytest.fixture(scope="module")
def wbtc(deployer):
    with boa.env.prank(deployer):
        yield boa.load("contracts/mocks/ERC20Mock.vy", "WBTC", "WBTC", 8)


@pytest.fixture(scope="module")
def coins(usdt, wbtc, weth):
    yield [usdt, wbtc, weth]
