import boa
import pytest
from boa.test import given, strategy
from hypothesis import example, settings
from vyper.utils import SizeLimits

SETTINGS = dict(max_examples=20000, deadline=None)
MAX_VAL = SizeLimits.MAX_UINT256


@pytest.fixture(scope="module")
def vyper_sort3():

    sort_implementation = """
@external
@view
def sort_descending(unsorted: uint256[3]) -> uint256[3]:
    sorted: uint256[3] = unsorted
    temp_var: uint256 = sorted[0]
    if sorted[0] < sorted[1]:
        sorted[0] = sorted[1]
        sorted[1] = temp_var
    if sorted[0] < sorted[2]:
        temp_var = sorted[0]
        sorted[0] = sorted[2]
        sorted[2] = temp_var
    if sorted[1] < sorted[2]:
        temp_var = sorted[1]
        sorted[1] = sorted[2]
        sorted[2] = temp_var

    return sorted
"""

    return boa.loads(sort_implementation)


@given(val=strategy("uint256[3]", min_value=0, max_value=MAX_VAL))
@settings(**SETTINGS)
@example([1, 1, 1])
def test_sort3_descending(vyper_sort3, val):

    sort_vyper = list(vyper_sort3.sort_descending(val))
    sort_python = sorted(val, reverse=True)

    assert sort_vyper == sort_python
