from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

CBRT_SETTINGS = dict(max_examples=10000, deadline=timedelta(seconds=1000))


def _cbrt_wad_ideal(val: int) -> int:
    return int((val / 10**18) ** (1 / 3) * 10**18)


@given(
    st.integers(min_value=0, max_value=SizeLimits.MAX_UINT256 / 2 / 10**18)
)
@settings(**CBRT_SETTINGS)
def test_cbrt_without_initial_values(tricrypto_math, val):

    cbrt_ideal = _cbrt_wad_ideal(val)
    cbrt_int = tricrypto_math.eval(f"self.cbrt({val})")
    assert cbrt_int == pytest.approx(cbrt_ideal)


@given(
    val=st.integers(
        min_value=0, max_value=SizeLimits.MAX_UINT256 / 2 / 10**18
    ),
    initial_val_frac=st.floats(min_value=0.01, max_value=10),
)
@settings(**CBRT_SETTINGS)
def test_cbrt_with_initial_values(tricrypto_math, val, initial_val_frac):

    cbrt_ideal = _cbrt_wad_ideal(val)
    initial_value = int(initial_val_frac * cbrt_ideal)

    cbrt_int = tricrypto_math.eval(f"self.cbrt({val}, {initial_value})")
    assert cbrt_int == pytest.approx(cbrt_ideal)
