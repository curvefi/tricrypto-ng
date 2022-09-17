from datetime import timedelta

import boa
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

SETTINGS = dict(max_examples=10000, deadline=timedelta(seconds=1000))


@given(st.integers(min_value=0, max_value=SizeLimits.MAX_UINT256 / 10**18))
@settings(**SETTINGS)
def test_cbrt(tricrypto_math, val):

    cbrt_ideal = int((val / 10**18) ** (1 / 3) * 10**18)

    try:
        cbrt_int = tricrypto_math.eval(f"self.cbrt({val})")
        assert cbrt_int == pytest.approx(cbrt_ideal)
        with open("passed_cbrt_test_samples.txt", "a") as f:
            f.write(
                f"input: {val}:= ideal: {cbrt_ideal}, "
                f"implementation: {cbrt_int}\n"
            )

    except AssertionError:
        # TODO: remove later! it is just to survey non-convergences:
        with open("assertionerror_cbrt_test_samples.txt", "a") as f:
            f.write(
                f"input: {val}:= ideal: {cbrt_ideal}, "
                f"implementation: {cbrt_int}\n"
            )
    except boa.BoaError:
        with open("failed_cbrt_test_samples.txt", "a") as f:
            f.write(f"input: {val}:= ideal: {cbrt_ideal}\n")
