import boa
from eth_account.account import Account


# tests inspired by yearn-vaults:
# https://github.com/yearn/yearn-vaults/blob/master/tests/functional/vault/test_permit.py  # noqa: E501
def test_permit(eth_acc, bob, tricrypto_swap, sign_permit, skip_unoptimized):

    sig = sign_permit(
        tricrypto_swap, eth_acc, bob, 2**256 - 1, 2**256 - 1, 0
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


def test_permit_contract(
    eth_acc, bob, tricrypto_swap, sign_permit, skip_unoptimized
):

    src = """
@view
@external
def isValidSignature(_hash: bytes32, _sig: Bytes[65]) -> bytes32:
    return 0x1626ba7e00000000000000000000000000000000000000000000000000000000
"""

    mock_contract = boa.loads(src)
    sig = sign_permit(
        tricrypto_swap, eth_acc, bob, 2**256 - 1, 2**256 - 1, 0
    )

    with boa.env.prank(bob):
        tricrypto_swap.permit(
            mock_contract,
            bob,
            2**256 - 1,
            2**256 - 1,
            sig.v,
            (sig.r).to_bytes(32, "big"),
            (sig.s).to_bytes(32, "big"),
        )

    # make sure this is hit when owner is a contract
    last_computation = tricrypto_swap._computation.children[-1]
    subcall_obj = boa.env.lookup_contract(last_computation.msg.code_address)
    assert hasattr(subcall_obj, "isValidSignature")


def test_permit_wrong_signature(bob, tricrypto_swap, sign_permit):
    owner = Account.create()
    deadline = boa.env.vm.state.timestamp + 3600
    sig = sign_permit(tricrypto_swap, owner, bob, 0, deadline, 0)
    with boa.env.prank(bob), boa.reverts("dev: invalid signature"):
        tricrypto_swap.permit(
            owner.address,
            bob,
            10**19,
            deadline,
            sig.v,
            (sig.r).to_bytes(32, "big"),
            (sig.s).to_bytes(32, "big"),
        )


def test_permit_expired(bob, tricrypto_swap, sign_permit):
    owner = Account.create()
    deadline = boa.env.vm.state.timestamp - 600
    amount = 10**19
    sig = sign_permit(tricrypto_swap, owner, bob, amount, deadline, 0)

    with boa.env.prank(bob), boa.reverts("dev: permit expired"):
        tricrypto_swap.permit(
            owner.address,
            bob,
            amount,
            deadline,
            sig.v,
            (sig.r).to_bytes(32, "big"),
            (sig.s).to_bytes(32, "big"),
        )


def test_permit_bad_owner(bob, tricrypto_swap, sign_permit):
    owner = Account.create()
    deadline = boa.env.vm.state.timestamp + 3600
    amount = 10**19
    sig = sign_permit(tricrypto_swap, owner, bob, amount, deadline, 0)

    with boa.env.prank(bob), boa.reverts("dev: invalid owner"):
        tricrypto_swap.permit(
            "0x0000000000000000000000000000000000000000",
            bob,
            amount,
            deadline,
            sig.v,
            (sig.r).to_bytes(32, "big"),
            (sig.s).to_bytes(32, "big"),
        )
