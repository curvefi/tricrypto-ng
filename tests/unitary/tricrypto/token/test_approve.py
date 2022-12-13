import boa
import pytest

from tests.utils.tokens import mint_for_testing


@pytest.mark.parametrize("idx", range(5))
def test_initial_approval_is_zero(
    tricrypto_swap, alice, users, idx, skip_unoptimized
):
    assert tricrypto_swap.allowance(alice, users[idx]) == 0


def test_approve(tricrypto_swap, alice, bob, skip_unoptimized):

    with boa.env.prank(alice):
        tricrypto_swap.approve(bob, 10**19)

    assert tricrypto_swap.allowance(alice, bob) == 10**19


def test_modify_approve_zero_nonzero(
    tricrypto_swap, alice, bob, skip_unoptimized
):

    with boa.env.prank(alice):
        tricrypto_swap.approve(bob, 10**19)
        tricrypto_swap.approve(bob, 0)
        tricrypto_swap.approve(bob, 12345678)

    assert tricrypto_swap.allowance(alice, bob) == 12345678


def test_revoke_approve(tricrypto_swap, alice, bob, skip_unoptimized):

    with boa.env.prank(alice):
        tricrypto_swap.approve(bob, 10**19)
        tricrypto_swap.approve(bob, 0)

    assert tricrypto_swap.allowance(alice, bob) == 0


def test_approve_self(tricrypto_swap, alice, skip_unoptimized):

    with boa.env.prank(alice):
        tricrypto_swap.approve(alice, 10**19)

    assert tricrypto_swap.allowance(alice, alice) == 10**19


def test_only_affects_target(tricrypto_swap, alice, bob, skip_unoptimized):
    with boa.env.prank(alice):
        tricrypto_swap.approve(bob, 10**19)

    assert tricrypto_swap.allowance(bob, alice) == 0


def test_returns_true(tricrypto_swap, alice, bob, skip_unoptimized):
    with boa.env.prank(alice):
        assert tricrypto_swap.approve(bob, 10**19)


def test_approval_event_fires(tricrypto_swap, alice, bob):

    with boa.env.prank(alice):
        tricrypto_swap.approve(bob, 10**19)

    logs = tricrypto_swap.get_logs()

    assert len(logs) == 1
    assert logs[0].event_type.name == "Approval"
    assert logs[0].topics[0] == alice
    assert logs[0].topics[1] == bob
    assert logs[0].args[0] == 10**19


def test_infinite_approval(tricrypto_swap, alice, bob, skip_unoptimized):
    with boa.env.prank(alice):
        tricrypto_swap.approve(bob, 2**256 - 1)

    mint_for_testing(tricrypto_swap, alice, 10**18)
    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(alice, bob, 10**18)

    assert tricrypto_swap.allowance(alice, bob) == 2**256 - 1
