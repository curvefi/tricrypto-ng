import boa
import pytest


@pytest.fixture(scope="module")
def math_optimized(deployer):
    with boa.env.prank(deployer):
        return boa.load("contracts/main/CurveCryptoMathOptimized3.vy")


@pytest.fixture(scope="module")
def math_unoptimized(deployer):
    with boa.env.prank(deployer):
        return boa.load("contracts/old/CurveCryptoMath3.vy")
