import boa
from hexbytes import HexBytes

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


# tests inspired by:
# https://github.com/yearn/yearn-vaults/blob/master/tests/functional/vault/test_permit.py  # noqa: E501
# https://github.com/curvefi/curve-stablecoin/blob/5b6708138d82419917328e8042f3857eac034796/tests/stablecoin/test_approve.py  # noqa: E501


def test_permit_success(eth_acc, bob, swap, sign_permit):

    value = 2**256 - 1
    deadline = boa.env.vm.state.timestamp + 600

    sig = sign_permit(
        swap=swap,
        owner=eth_acc,
        spender=bob,
        value=value,
        deadline=deadline,
    )

    assert swap.allowance(eth_acc.address, bob) == 0
    with boa.env.prank(bob):
        assert swap.permit(
            eth_acc.address,
            bob,
            value,
            deadline,
            sig.v,
            HexBytes(sig.r),
            HexBytes(sig.s),
        )

    logs = swap.get_logs()

    assert swap.allowance(eth_acc.address, bob) == value
    assert len(logs) == 1
    assert swap.nonces(eth_acc.address) == 1
    assert logs[0].event_type.name == "Approval"
    assert logs[0].topics[0].lower() == eth_acc.address.lower()
    assert logs[0].topics[1].lower() == bob.lower()
    assert logs[0].args[0] == value


def test_permit_reverts_owner_is_invalid(bob, swap):
    with boa.reverts(dev="invalid owner"), boa.env.prank(bob):
        swap.permit(
            ZERO_ADDRESS,
            bob,
            2**256 - 1,
            boa.env.vm.state.timestamp + 600,
            27,
            b"\x00" * 32,
            b"\x00" * 32,
        )


def test_permit_reverts_deadline_is_invalid(bob, swap):
    with boa.reverts(dev="permit expired"), boa.env.prank(bob):
        swap.permit(
            bob,
            bob,
            2**256 - 1,
            boa.env.vm.state.timestamp - 600,
            27,
            b"\x00" * 32,
            b"\x00" * 32,
        )


def test_permit_reverts_signature_is_invalid(bob, swap):
    with boa.reverts(dev="invalid signature"), boa.env.prank(bob):
        swap.permit(
            bob,
            bob,
            2**256 - 1,
            boa.env.vm.state.timestamp + 600,
            27,
            b"\x00" * 32,
            b"\x00" * 32,
        )


def test_domain_separator_updates_when_chain_id_updates(swap):

    domain_separator = swap.DOMAIN_SEPARATOR()
    with boa.env.anchor():
        boa.env.vm.patch.chain_id = 42
        assert domain_separator != swap.DOMAIN_SEPARATOR()
