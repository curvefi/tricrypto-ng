# flake8: noqa
import sys
import time
from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import tests.utils.simulation_int_many as sim
from tests.utils.checks import check_limits

sys.stdout = sys.stderr

N_COINS = 3
MAX_SAMPLES = 1000  # Increase for fuzzing

A_MUL = 10000 * 3**3
MIN_A = int(0.01 * A_MUL)
MAX_A = 1000 * A_MUL

# gamma from 1e-8 up to 0.05
MIN_GAMMA = 10**10
MAX_GAMMA = 5 * 10**16

pytest.progress = 0
pytest.positive_dy = 0
pytest.t_start = time.time()
pytest.gas_original = 0
pytest.gas_new = 0


@given(
    A=st.integers(min_value=MIN_A, max_value=MAX_A),
    D=st.integers(
        min_value=10**18, max_value=10**14 * 10**18
    ),  # 1 USD to 100T USD
    xD=st.integers(
        min_value=int(1.001e16), max_value=int(0.999e20)
    ),  # <- ratio 1e18 * x/D, typically 1e18 * 1
    yD=st.integers(
        min_value=int(1.001e16), max_value=int(0.999e20)
    ),  # <- ratio 1e18 * y/D, typically 1e18 * 1
    zD=st.integers(
        min_value=int(1.001e16), max_value=int(0.999e20)
    ),  # <- ratio 1e18 * z/D, typically 1e18 * 1
    gamma=st.integers(min_value=MIN_GAMMA, max_value=MAX_GAMMA),
    j=st.integers(min_value=0, max_value=2),
    btcScalePrice=st.integers(min_value=10**2, max_value=10**7),
    ethScalePrice=st.integers(min_value=10, max_value=10**5),
    mid_fee=st.sampled_from(
        [
            int(0.7e-3 * 10**10),
            int(1e-3 * 10**10),
            int(1.2e-3 * 10**10),
            int(4e-3 * 10**10),
        ]
    ),
    out_fee=st.sampled_from([int(4.0e-3 * 10**10), int(10.0e-3 * 10**10)]),
    fee_gamma=st.sampled_from([int(1e-2 * 1e18), int(2e-6 * 1e18)]),
)
@settings(max_examples=MAX_SAMPLES, deadline=timedelta(seconds=1000))
def test_newton_D(
    math_optimized,
    coins,
    A,
    D,
    xD,
    yD,
    zD,
    gamma,
    j,
    btcScalePrice,
    ethScalePrice,
    mid_fee,
    out_fee,
    fee_gamma,
):
    _test_newton_D(
        math_optimized,
        coins,
        A,
        D,
        xD,
        yD,
        zD,
        gamma,
        j,
        btcScalePrice,
        ethScalePrice,
        mid_fee,
        out_fee,
        fee_gamma,
    )


def _test_newton_D(
    tricrypto_math,
    coins,
    A,
    D,
    xD,
    yD,
    zD,
    gamma,
    j,
    btcScalePrice,
    ethScalePrice,
    mid_fee,
    out_fee,
    fee_gamma,
):
    pytest.progress += 1
    if pytest.progress % 100 == 0 and pytest.positive_dy != 0:
        print(
            f"{pytest.progress} | {pytest.positive_dy} cases processed in {time.time()-pytest.t_start:.1f} seconds."
            f"Gas advantage per call: {pytest.gas_original//pytest.positive_dy} {pytest.gas_new//pytest.positive_dy}\n"
        )
    X = [D * xD // 10**18, D * yD // 10**18, D * zD // 10**18]

    try:
        (result_get_y, K0) = tricrypto_math.get_y(A, gamma, X, D, j)
    except:
        decimals = [c.decimals() for c in coins]
        prices = [10**18, btcScalePrice, ethScalePrice]
        if check_limits(D, prices, X, decimals, X):
            raise
        else:
            return  # expected behavior

    # dy should be positive
    if result_get_y < X[j]:

        price_scale = (btcScalePrice, ethScalePrice)
        y = X[j]
        dy = X[j] - result_get_y
        dy -= 1

        if j > 0:
            dy = dy * 10**18 // price_scale[j - 1]

        fee = sim.get_fee(X, fee_gamma, mid_fee, out_fee)
        dy -= fee * dy // 10**10
        y -= dy

        if dy / X[j] <= 0.95:
            pytest.positive_dy += 1
            X[j] = y

            try:
                result_sim = tricrypto_math.newton_D(A, gamma, X)
            except:
                decimals = [c.decimals() for c in coins]
                prices = [10**18, btcScalePrice, ethScalePrice]
                if check_limits(D, prices, X, decimals, X):
                    raise
                else:
                    return  # expected behavior

            pytest.gas_original += tricrypto_math._computation.get_gas_used()

            try:
                result_contract = tricrypto_math.newton_D(A, gamma, X, K0)
            except:
                decimals = [c.decimals() for c in coins]
                prices = [10**18, btcScalePrice, ethScalePrice]
                if check_limits(D, prices, X, decimals, X):
                    raise
                else:
                    return  # expected behavior

            pytest.gas_new += tricrypto_math._computation.get_gas_used()
            assert abs(result_sim - result_contract) <= max(
                10000, result_sim / 1e12
            )
