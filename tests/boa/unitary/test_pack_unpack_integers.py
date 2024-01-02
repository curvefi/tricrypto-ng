from boa.test import strategy
from hypothesis import given, settings


@given(val=strategy("uint256[3]", max_value=10**18))
@settings(max_examples=10000, deadline=None)
def test_pack_unpack_three_integers(swap, val):
    packed = swap.internal._pack_3(val)
    unpacked = swap.internal._unpack_3(packed)  # swap unpacks
    for i in range(3):
        assert unpacked[i] == val[i]


@given(val=strategy("uint256[3]", max_value=10**18))
@settings(max_examples=10000, deadline=None)
def test_pack_unpack_three_integers_factory(swap, tricrypto_factory, val):
    packed = tricrypto_factory.internal._pack(val)
    unpacked = swap.internal._unpack_3(packed)  # swap unpacks
    for i in range(3):
        assert unpacked[i] == val[i]


@given(val=strategy("uint256[2]", max_value=2**128 - 1))
@settings(max_examples=10000, deadline=None)
def test_pack_unpack_2_integers(swap, val):

    packed = swap.internal._pack_2(val[0], val[1])
    unpacked = swap.internal._unpack_2(packed)  # swap unpacks

    assert unpacked[0] == val[0]
    assert unpacked[1] == val[1]
