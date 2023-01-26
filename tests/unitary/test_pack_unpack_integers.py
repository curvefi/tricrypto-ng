from boa.test import strategy
from hypothesis import given, settings


@given(val=strategy("uint256[3]", max_value=10**18))
@settings(max_examples=10000, deadline=None)
def test_pack_unpack_three_integers(swap, tricrypto_factory, val):

    for contract in [swap, tricrypto_factory]:
        packed = contract.internal._pack(val)
        unpacked = swap.internal._unpack(packed)  # swap unpacks
        for i in range(3):
            assert unpacked[i] == val[i]
