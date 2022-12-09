from boa.test import strategy
from hypothesis import given, settings

from tests.utils import simulation_int_many as sim

MAX_SAMPLES = 10000


def test_reduction_coefficient(math_optimized):
    assert (
        math_optimized.reduction_coefficient([10**18, 10**18, 10**18], 0)
        == 10**18
    )
    assert (
        math_optimized.reduction_coefficient(
            [10**18, 10**18, 10**18], 10**15
        )
        == 10**18
    )
    result = math_optimized.reduction_coefficient(
        [10**18, 10**18, 10**17], 10**15
    )
    assert result > 0
    assert result < 10**18
    result = math_optimized.reduction_coefficient(
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
def test_reduction_coefficient_property(math_optimized, x0, x1, x2, gamma):
    coeff = math_optimized.reduction_coefficient([x0, x1, x2], gamma)
    assert coeff <= 10**18


@given(
    x0=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    x1=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    x2=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    gamma=strategy("uint256", min_value=0, max_value=10**17),
)
@settings(max_examples=MAX_SAMPLES, deadline=None)
def test_reduction_coefficient_sim(math_optimized, x0, x1, x2, gamma):
    result_contract = math_optimized.reduction_coefficient([x0, x1, x2], gamma)
    result_sim = sim.reduction_coefficient([x0, x1, x2], gamma)
    assert result_contract == result_sim


@given(
    x0=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    x1=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    x2=strategy("uint256", min_value=10**9, max_value=10**9 * 10**18),
    gamma=strategy("uint256", min_value=0, max_value=10**17),
)
@settings(max_examples=MAX_SAMPLES, deadline=None)
def test_compare_reduction_coefficient(
    math_optimized, math_unoptimized, x0, x1, x2, gamma
):
    result_optimized = math_optimized.reduction_coefficient(
        [x0, x1, x2], gamma
    )
    result_unoptimized = math_unoptimized.reduction_coefficient(
        [x0, x1, x2], gamma
    )
    assert result_optimized == result_unoptimized
