from boa.test import strategy
from hypothesis import given, settings

from tests.utils import simulation_int_many as sim

MAX_SAMPLES = 10000


def test_reduction_coefficient(tricrypto_math):
    assert (
        tricrypto_math.reduction_coefficient([10**18, 10**18, 10**18], 0)
        == 10**18
    )
    assert (
        tricrypto_math.reduction_coefficient(
            [10**18, 10**18, 10**18], 10**15
        )
        == 10**18
    )
    result = tricrypto_math.reduction_coefficient(
        [10**18, 10**18, 10**17], 10**15
    )
    assert result > 0
    assert result < 10**18
    result = tricrypto_math.reduction_coefficient(
        [10**18, 10**18, int(0.999e18)], 10**15
    )
    assert result > 0
    assert result < 10**18
    assert result > 9 * 10**17


@given(
    x0=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    x1=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    x2=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    gamma=strategy("uint256", min_value=1, max_value=2**100),
)
@settings(max_examples=MAX_SAMPLES, deadline=None)
def test_reduction_coefficient_property(tricrypto_math, x0, x1, x2, gamma):
    coeff = tricrypto_math.reduction_coefficient([x0, x1, x2], gamma)
    assert coeff <= 10**18


@given(
    x0=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    x1=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    x2=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    gamma=strategy("uint256", min_value=0, max_value=10**17),
)
@settings(max_examples=MAX_SAMPLES, deadline=None)
def test_reduction_coefficient_sim(tricrypto_math, x0, x1, x2, gamma):
    result_contract = tricrypto_math.reduction_coefficient([x0, x1, x2], gamma)
    result_sim = sim.reduction_coefficient([x0, x1, x2], gamma)
    assert result_contract == result_sim
