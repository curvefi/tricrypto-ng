import boa

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


# tests inspired by:
# https://github.com/yearn/yearn-vaults/blob/master/tests/functional/vault/test_permit.py  # noqa: E501
# https://github.com/curvefi/curve-stablecoin/blob/5b6708138d82419917328e8042f3857eac034796/tests/stablecoin/test_approve.py  # noqa: E501


def test_permit_success(
    eth_acc, bob, tricrypto_swap, sign_permit, skip_unoptimized
):

    sig = sign_permit(
        swap=tricrypto_swap,
        owner=eth_acc,
        spender=bob,
        value=2**256 - 1,
        deadline=2**256 - 1,
        nonce=tricrypto_swap.nonces(eth_acc),
        salt=tricrypto_swap.salt(),
    )

    assert tricrypto_swap.allowance(eth_acc.address, bob) == 0
    with boa.env.prank(bob):

        assert tricrypto_swap.permit(
            eth_acc.address,
            bob,
            2**256 - 1,
            2**256 - 1,
            sig.v,
            (sig.r).to_bytes(32, "big"),
            (sig.s).to_bytes(32, "big"),
        )

    logs = tricrypto_swap.get_logs()

    assert tricrypto_swap.allowance(eth_acc.address, bob) == 2**256 - 1
    assert len(logs) == 1
    assert tricrypto_swap.nonces(eth_acc.address) == 1
    assert logs[0].event_type.name == "Approval"
    assert logs[0].topics[0] == eth_acc.address
    assert logs[0].topics[1] == bob
    assert logs[0].args[0] == 2**256 - 1


def test_permit_reverts_owner_is_invalid(
    bob, tricrypto_swap, skip_unoptimized
):
    with boa.reverts("dev: invalid owner"), boa.env.prank(bob):
        tricrypto_swap.permit(
            ZERO_ADDRESS,
            bob,
            2**256 - 1,
            boa.env.vm.state.timestamp + 600,
            27,
            b"\x00" * 32,
            b"\x00" * 32,
        )


def test_permit_reverts_deadline_is_invalid(
    bob, tricrypto_swap, skip_unoptimized
):
    with boa.reverts("dev: permit expired"), boa.env.prank(bob):
        tricrypto_swap.permit(
            bob,
            bob,
            2**256 - 1,
            boa.env.vm.state.timestamp - 600,
            27,
            b"\x00" * 32,
            b"\x00" * 32,
        )


def test_permit_reverts_signature_is_invalid(
    bob, tricrypto_swap, skip_unoptimized
):
    with boa.reverts("dev: invalid signature"), boa.env.prank(bob):
        tricrypto_swap.permit(
            bob,
            bob,
            2**256 - 1,
            boa.env.vm.state.timestamp + 600,
            27,
            b"\x00" * 32,
            b"\x00" * 32,
        )


def test_domain_separator_updates_when_chain_id_updates(tricrypto_swap):

    domain_separator = tricrypto_swap.DOMAIN_SEPARATOR()
    with boa.env.anchor():
        boa.env.vm.patch.chain_id = 42
        assert domain_separator != tricrypto_swap.DOMAIN_SEPARATOR()
