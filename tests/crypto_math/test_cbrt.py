from datetime import timedelta

import boa
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

CBRT_SETTINGS = dict(max_examples=10000, deadline=timedelta(seconds=1000))
MAX_VAL = SizeLimits.MAX_UINT256


def _cbrt_wad_ideal(val: int) -> int:
    return int((val / 10**18) ** (1 / 3) * 10**18)


def _fails_overflow_tests(val, initial_val, tricrypto_math) -> bool:

    # we multiply 10 ** 18 to the input, and then 10 ** 18 in the first
    # iteration, so check if it goes over max val. if it does,
    # we call should revert:
    if val * 10**36 > MAX_VAL:
        with boa.reverts():
            tricrypto_math.eval(f"self.cbrt({val})")

        return True

    # since there are no initial values, the var `a` is set to
    # input val, and this is squared. This would then go over
    # MAX_UINT256 for very large numbers, so check that it reverts
    # for those cases:
    elif initial_val**2 > MAX_VAL:
        with boa.reverts():
            tricrypto_math.eval(f"self.cbrt({val})")

        return True

    else:

        return False


@given(st.integers(min_value=0, max_value=MAX_VAL))
@settings(**CBRT_SETTINGS)
def test_cbrt_without_initial_values(tricrypto_math, val):

    if not _fails_overflow_tests(val, val, tricrypto_math):

        cbrt_ideal = _cbrt_wad_ideal(val)
        cbrt_int = tricrypto_math.eval(f"self.cbrt({val})")
        assert cbrt_int == pytest.approx(cbrt_ideal)


@given(
    val=st.integers(min_value=0, max_value=MAX_VAL),
    initial_val_frac=st.floats(min_value=0.01, max_value=10),
)
@settings(**CBRT_SETTINGS)
def test_cbrt_with_initial_values(tricrypto_math, val, initial_val_frac):

    cbrt_ideal = _cbrt_wad_ideal(val)
    initial_value = int(initial_val_frac * cbrt_ideal)

    if not _fails_overflow_tests(val, initial_value, tricrypto_math):

        cbrt_int = tricrypto_math.eval(f"self.cbrt({val}, {initial_value})")
        assert cbrt_int == pytest.approx(cbrt_ideal)


@given(st.integers(min_value=0, max_value=MAX_VAL))
@settings(**CBRT_SETTINGS)
def test_cbrt_optimized(tricrypto_math, val):

    cbrt_ideal = _cbrt_wad_ideal(val)
    cbrt_optimized = tricrypto_math.eval(f"self.cbrt_optimized({val})")
    cbrt_int = tricrypto_math.eval(f"self.cbrt({val})")

    assert cbrt_int == cbrt_optimized
    assert cbrt_int == pytest.approx(cbrt_ideal)
