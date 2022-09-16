from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

SETTINGS = dict(max_examples=2000, deadline=timedelta(seconds=1000))


@given(st.integers(min_value=0, max_value=2**256 - 1))
@settings(**SETTINGS)
def test_cbrt(tricrypto_math, val):

    cbrt_int = tricrypto_math.eval(f"self.cbrt({val})")
    cbrt_ideal = int((val / 10**18) ** (1 / 3) * 10**18)
    assert cbrt_int == pytest.approx(cbrt_ideal)
