import boa
import pytest


@pytest.fixture(scope="module")
def tricrypto_math(deployer):
    with boa.env.prank(deployer):
        return boa.load("contracts/CurveCryptoMathOptimized3.vy")
