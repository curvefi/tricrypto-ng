import boa


def test_sender_balance_decreases(loaded_alice, bob, charlie, tricrypto_swap):
    sender_balance = tricrypto_swap.balanceOf(loaded_alice)
    amount = sender_balance // 4

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, amount)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, amount)

    assert tricrypto_swap.balanceOf(loaded_alice) == sender_balance - amount


def test_receiver_balance_increases(
    loaded_alice, bob, charlie, tricrypto_swap
):
    receiver_balance = tricrypto_swap.balanceOf(charlie)
    amount = tricrypto_swap.balanceOf(loaded_alice) // 4

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, amount)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, amount)

    assert tricrypto_swap.balanceOf(charlie) == receiver_balance + amount


def test_caller_balance_not_affected(
    loaded_alice, bob, charlie, tricrypto_swap
):
    caller_balance = tricrypto_swap.balanceOf(bob)
    amount = tricrypto_swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, amount)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, amount)

    assert tricrypto_swap.balanceOf(bob) == caller_balance


def test_caller_approval_affected(alice, bob, charlie, tricrypto_swap):
    approval_amount = tricrypto_swap.balanceOf(alice)
    transfer_amount = approval_amount // 4

    with boa.env.prank(alice):
        tricrypto_swap.approve(bob, approval_amount)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(alice, charlie, transfer_amount)

    assert (
        tricrypto_swap.allowance(alice, bob)
        == approval_amount - transfer_amount
    )


def test_receiver_approval_not_affected(
    loaded_alice, bob, charlie, tricrypto_swap
):
    approval_amount = tricrypto_swap.balanceOf(loaded_alice)
    transfer_amount = approval_amount // 4

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, approval_amount)
        tricrypto_swap.approve(charlie, approval_amount)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, transfer_amount)

    assert tricrypto_swap.allowance(loaded_alice, charlie) == approval_amount


def test_total_supply_not_affected(loaded_alice, bob, charlie, tricrypto_swap):
    total_supply = tricrypto_swap.totalSupply()
    amount = tricrypto_swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, amount)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, amount)

    assert tricrypto_swap.totalSupply() == total_supply


def test_returns_true(loaded_alice, bob, charlie, tricrypto_swap):
    amount = tricrypto_swap.balanceOf(loaded_alice)
    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, amount)

    with boa.env.prank(bob):
        assert tricrypto_swap.transferFrom(loaded_alice, charlie, amount)


def test_transfer_full_balance(loaded_alice, bob, charlie, tricrypto_swap):
    amount = tricrypto_swap.balanceOf(loaded_alice)
    receiver_balance = tricrypto_swap.balanceOf(charlie)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, amount)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, amount)

    assert tricrypto_swap.balanceOf(loaded_alice) == 0
    assert tricrypto_swap.balanceOf(charlie) == receiver_balance + amount


def test_transfer_zero_tokens(loaded_alice, bob, charlie, tricrypto_swap):
    sender_balance = tricrypto_swap.balanceOf(loaded_alice)
    receiver_balance = tricrypto_swap.balanceOf(charlie)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, sender_balance)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, 0)

    assert tricrypto_swap.balanceOf(loaded_alice) == sender_balance
    assert tricrypto_swap.balanceOf(charlie) == receiver_balance


def test_transfer_zero_tokens_without_approval(
    loaded_alice, bob, charlie, tricrypto_swap
):
    sender_balance = tricrypto_swap.balanceOf(loaded_alice)
    receiver_balance = tricrypto_swap.balanceOf(charlie)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, 0)

    assert tricrypto_swap.balanceOf(loaded_alice) == sender_balance
    assert tricrypto_swap.balanceOf(charlie) == receiver_balance


def test_insufficient_balance(loaded_alice, bob, charlie, tricrypto_swap):
    balance = tricrypto_swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, balance + 1)

    with boa.reverts(), boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, balance + 1)


def test_insufficient_approval(loaded_alice, bob, charlie, tricrypto_swap):
    balance = tricrypto_swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, balance - 1)

    with boa.reverts(), boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, balance)


def test_no_approval(loaded_alice, bob, charlie, tricrypto_swap):
    balance = tricrypto_swap.balanceOf(loaded_alice)

    with boa.reverts(), boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, balance)


def test_revoked_approval(loaded_alice, bob, charlie, tricrypto_swap):
    balance = tricrypto_swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, balance)
        tricrypto_swap.approve(bob, 0)

    with boa.reverts(), boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, balance)


def test_transfer_to_self(loaded_alice, tricrypto_swap):
    sender_balance = tricrypto_swap.balanceOf(loaded_alice)
    amount = sender_balance // 4

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(loaded_alice, sender_balance)
        tricrypto_swap.transferFrom(loaded_alice, loaded_alice, amount)

    assert tricrypto_swap.balanceOf(loaded_alice) == sender_balance
    assert (
        tricrypto_swap.allowance(loaded_alice, loaded_alice)
        == sender_balance - amount
    )


def test_transfer_to_self_no_approval(loaded_alice, tricrypto_swap):
    amount = tricrypto_swap.balanceOf(loaded_alice)

    with boa.reverts(), boa.env.prank(loaded_alice):
        tricrypto_swap.transferFrom(loaded_alice, loaded_alice, amount)


def test_transfer_event_fires(loaded_alice, bob, charlie, tricrypto_swap):
    amount = tricrypto_swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.approve(bob, amount)

    with boa.env.prank(bob):
        tricrypto_swap.transferFrom(loaded_alice, charlie, amount)

    logs = tricrypto_swap.get_logs()

    assert len(logs) == 1
    assert logs[0].event_type.name == "Transfer"
    assert logs[0].args[0] == amount
    assert logs[0].topics[0] == loaded_alice
    assert logs[0].topics[1] == charlie
