import boa
import pytest


@pytest.fixture(scope="module")
def math_contract(deployer):
    with boa.env.prank(deployer):
        return boa.load("contracts/CurveCryptoMathOptimized3.vy")


@pytest.fixture(scope="module")
def gauge_interface():
    return boa.load_partial("contracts/LiquidityGauge.vy")


@pytest.fixture(scope="module")
def gauge_implementation(deployer, gauge_interface):
    with boa.env.prank(deployer):
        return gauge_interface.deploy_as_blueprint()


@pytest.fixture(scope="module")
def views_contract(deployer, tricrypto_math, tricrypto_swap):
    with boa.env.prank(deployer):
        return boa.load(
            "contracts/CurveCryptoViews3Optimized.vy",
            tricrypto_math,
            tricrypto_swap,
        )


@pytest.fixture(scope="module")
def pool_interface():
    return boa.load_partial("contracts/CurveTricryptoOptimized.vy")


@pytest.fixture(scope="module")
def pool_implementation(deployer, pool_interface):
    with boa.env.prank(deployer):
        return pool_interface.deploy_as_blueprint()


@pytest.fixture(scope="module")
def tricrypto_factory(
    deployer,
    fee_receiver,
    pool_implementation,
    gauge_implementation,
    views_contract,
    math_contract,
    weth,
):
    with boa.env.prank(deployer):
        factory = boa.load(
            "contracts/CurveTricryptoFactory.vy", fee_receiver, weth
        )
        factory.set_pool_implementation(pool_implementation)
        factory.set_gauge_implementation(gauge_implementation)
        factory.set_views_implementation(views_contract)
        factory.set_math_implementation(math_contract)

    return factory
