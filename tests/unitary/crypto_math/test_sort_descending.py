from datetime import timedelta

from hypothesis import example, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

SETTINGS = dict(
    max_examples=1000,
    deadline=timedelta(seconds=1000),
)
MAX_VAL = SizeLimits.MAX_UINT256


@given(
    val=st.lists(
        st.integers(min_value=0, max_value=MAX_VAL), min_size=3, max_size=3
    )
)
@settings(**SETTINGS)
@example([1, 1, 1])
def test_sort3_descending(math_optimized, val):

    sort_vyper = list(math_optimized.internal._sort(val))
    assert sort_vyper == sorted(val, reverse=True)


@given(
    val=st.lists(
        st.integers(min_value=0, max_value=MAX_VAL), min_size=3, max_size=3
    )
)
@settings(**SETTINGS)
@example([1, 1, 1])
def test_compare_sort_descending(math_optimized, math_unoptimized, val):

    sort_optimized = list(math_optimized.internal._sort(val))
    sort_unoptimized = list(math_unoptimized.internal.sort(val))
    assert sort_optimized == sort_unoptimized
