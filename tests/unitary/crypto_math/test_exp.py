import math

import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings
from vyper.utils import SizeLimits

source_code = """
@external
@view
def _exp(_power: int256) -> uint256:
    if _power <= -42139678854452767551:
        return 0

    if _power >= 135305999368893231589:
        raise "exp overflow"

    x: int256 = unsafe_div(unsafe_mul(_power, 2**96), 10**18)
    k: int256 = unsafe_div(
        unsafe_add(
            unsafe_div(unsafe_mul(x, 2**96), 54916777467707473351141471128),
            2**95
        ),
        2**96
    )
    x = unsafe_sub(x, unsafe_mul(k, 54916777467707473351141471128))

    y: int256 = unsafe_add(x, 1346386616545796478920950773328)
    y = unsafe_add(unsafe_div(unsafe_mul(y, x), 2**96), 57155421227552351082224309758442)
    p: int256 = unsafe_sub(unsafe_add(y, x), 94201549194550492254356042504812)
    p = unsafe_add(unsafe_div(unsafe_mul(p, y), 2**96), 28719021644029726153956944680412240)
    p = unsafe_add(unsafe_mul(p, x), (4385272521454847904659076985693276 * 2**96))

    q: int256 = x - 2855989394907223263936484059900
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 50020603652535783019961831881945)
    q = unsafe_sub(unsafe_div(unsafe_mul(q, x), 2**96), 533845033583426703283633433725380)
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 3604857256930695427073651918091429)
    q = unsafe_sub(unsafe_div(unsafe_mul(q, x), 2**96), 14423608567350463180887372962807573)
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 26449188498355588339934803723976023)

    return shift(
        unsafe_mul(convert(unsafe_div(p, q), uint256), 3822833074963236453042738258902158003155416615667),
        unsafe_sub(k, 195))
"""  # noqa: E501


@pytest.fixture(scope="module")
def exp_solmate():
    return boa.loads(source_code)


@given(
    strategy(
        "int256",
        min_value=SizeLimits.MIN_INT256,
        max_value=SizeLimits.MAX_INT256,
    )
)
@settings(max_examples=10000, deadline=None)
def test_exp(exp_solmate, x):

    if x >= 135305999368893231589:
        with boa.reverts("exp overflow"):
            exp_solmate._exp(x)

    elif x <= -42139678854452767551:
        assert exp_solmate._exp(x) == 0

    else:

        exp_ideal = int(math.exp(x / 10**18) * 10**18)
        exp_implementation = exp_solmate._exp(x)

        # TODO: dont use approx:
        assert exp_ideal == pytest.approx(exp_implementation)
