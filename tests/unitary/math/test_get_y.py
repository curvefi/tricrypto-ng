# flake8: noqa
import time
from datetime import timedelta
from decimal import Decimal

import pytest
from hypothesis import given, note, settings
from hypothesis import strategies as st

from tests.utils.simulation_ma_4 import inv_target_decimal as inv_target

N_COINS = 3
MAX_SAMPLES = 10000  # Increase for fuzzing

A_MUL = 10000 * 3**3
MIN_A = int(0.01 * A_MUL)
MAX_A = 1000 * A_MUL

# gamma from 1e-8 up to 0.05
MIN_GAMMA = 10**10
MAX_GAMMA = 5 * 10**16

pytest.current_case_id = 0
pytest.negative_sqrt_arg = 0
pytest.gas_original = 0
pytest.gas_new = 0
pytest.t_start = time.time()


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
)
@settings(max_examples=MAX_SAMPLES, deadline=timedelta(seconds=1000))
def test_get_y(math_unoptimized, math_optimized, A, D, xD, yD, zD, gamma, j):
    pytest.current_case_id += 1
    X = [D * xD // 10**18, D * yD // 10**18, D * zD // 10**18]

    A_dec = Decimal(A) / 10000 / 27

    def calculate_F_by_y0(y0):
        new_X = X[:]
        new_X[j] = y0
        return inv_target(A_dec, gamma, new_X, D)

    try:
        result_original = math_unoptimized.newton_y(A, gamma, X, D, j)
        pytest.gas_original += math_unoptimized._computation.get_gas_used()
    except:
        (result_get_y, K0) = math_optimized.get_y(A, gamma, X, D, j)
        return

    (result_get_y, K0) = math_optimized.get_y(A, gamma, X, D, j)

    pytest.gas_new += math_optimized._computation.get_gas_used()
    note(
        "{"
        f"'ANN': {A}, 'D': {D}, 'xD': {xD}, 'yD': {yD}, 'zD': {zD}, 'GAMMA': {gamma}, 'index': {j}"
        "}\n"
    )

    if K0 == 0:
        pytest.negative_sqrt_arg += 1

    if pytest.current_case_id % 100 == 0:
        print(
            f"--- {pytest.current_case_id}\nPositive dy frac: {100*pytest.negative_sqrt_arg/pytest.current_case_id:.1f}%\t{time.time() - pytest.t_start:.1f} seconds.\n"
            f"Gas advantage per call: {pytest.gas_original//pytest.current_case_id} {pytest.gas_new//pytest.current_case_id}\n"
        )

    assert abs(result_original - result_get_y) <= max(
        10**4, result_original / 1e8
    ) or abs(calculate_F_by_y0(result_get_y)) <= abs(
        calculate_F_by_y0(result_original)
    )
