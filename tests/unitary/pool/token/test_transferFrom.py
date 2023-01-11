import boa


def test_sender_balance_decreases(loaded_alice, bob, charlie, swap):
    sender_balance = swap.balanceOf(loaded_alice)
    amount = sender_balance // 4

    with boa.env.prank(loaded_alice):
        swap.approve(bob, amount)

    with boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, amount)

    assert swap.balanceOf(loaded_alice) == sender_balance - amount


def test_receiver_balance_increases(
    loaded_alice, bob, charlie, swap
):
    receiver_balance = swap.balanceOf(charlie)
    amount = swap.balanceOf(loaded_alice) // 4

    with boa.env.prank(loaded_alice):
        swap.approve(bob, amount)

    with boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, amount)

    assert swap.balanceOf(charlie) == receiver_balance + amount


def test_caller_balance_not_affected(
    loaded_alice, bob, charlie, swap
):
    caller_balance = swap.balanceOf(bob)
    amount = swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        swap.approve(bob, amount)

    with boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, amount)

    assert swap.balanceOf(bob) == caller_balance


def test_caller_approval_affected(alice, bob, charlie, swap):
    approval_amount = swap.balanceOf(alice)
    transfer_amount = approval_amount // 4

    with boa.env.prank(alice):
        swap.approve(bob, approval_amount)

    with boa.env.prank(bob):
        swap.transferFrom(alice, charlie, transfer_amount)

    assert (
        swap.allowance(alice, bob)
        == approval_amount - transfer_amount
    )


def test_receiver_approval_not_affected(
    loaded_alice, bob, charlie, swap
):
    approval_amount = swap.balanceOf(loaded_alice)
    transfer_amount = approval_amount // 4

    with boa.env.prank(loaded_alice):
        swap.approve(bob, approval_amount)
        swap.approve(charlie, approval_amount)

    with boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, transfer_amount)

    assert swap.allowance(loaded_alice, charlie) == approval_amount


def test_total_supply_not_affected(loaded_alice, bob, charlie, swap):
    total_supply = swap.totalSupply()
    amount = swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        swap.approve(bob, amount)

    with boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, amount)

    assert swap.totalSupply() == total_supply


def test_returns_true(loaded_alice, bob, charlie, swap):
    amount = swap.balanceOf(loaded_alice)
    with boa.env.prank(loaded_alice):
        swap.approve(bob, amount)

    with boa.env.prank(bob):
        assert swap.transferFrom(loaded_alice, charlie, amount)


def test_transfer_full_balance(loaded_alice, bob, charlie, swap):
    amount = swap.balanceOf(loaded_alice)
    receiver_balance = swap.balanceOf(charlie)

    with boa.env.prank(loaded_alice):
        swap.approve(bob, amount)

    with boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, amount)

    assert swap.balanceOf(loaded_alice) == 0
    assert swap.balanceOf(charlie) == receiver_balance + amount


def test_transfer_zero_tokens(loaded_alice, bob, charlie, swap):
    sender_balance = swap.balanceOf(loaded_alice)
    receiver_balance = swap.balanceOf(charlie)

    with boa.env.prank(loaded_alice):
        swap.approve(bob, sender_balance)

    with boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, 0)

    assert swap.balanceOf(loaded_alice) == sender_balance
    assert swap.balanceOf(charlie) == receiver_balance


def test_transfer_zero_tokens_without_approval(
    loaded_alice, bob, charlie, swap
):
    sender_balance = swap.balanceOf(loaded_alice)
    receiver_balance = swap.balanceOf(charlie)

    with boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, 0)

    assert swap.balanceOf(loaded_alice) == sender_balance
    assert swap.balanceOf(charlie) == receiver_balance


def test_insufficient_balance(loaded_alice, bob, charlie, swap):
    balance = swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        swap.approve(bob, balance + 1)

    with boa.reverts(), boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, balance + 1)


def test_insufficient_approval(loaded_alice, bob, charlie, swap):
    balance = swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        swap.approve(bob, balance - 1)

    with boa.reverts(), boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, balance)


def test_no_approval(loaded_alice, bob, charlie, swap):
    balance = swap.balanceOf(loaded_alice)

    with boa.reverts(), boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, balance)


def test_revoked_approval(loaded_alice, bob, charlie, swap):
    balance = swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        swap.approve(bob, balance)
        swap.approve(bob, 0)

    with boa.reverts(), boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, balance)


def test_transfer_to_self(loaded_alice, swap):
    sender_balance = swap.balanceOf(loaded_alice)
    amount = sender_balance // 4

    with boa.env.prank(loaded_alice):
        swap.approve(loaded_alice, sender_balance)
        swap.transferFrom(loaded_alice, loaded_alice, amount)

    assert swap.balanceOf(loaded_alice) == sender_balance
    assert (
        swap.allowance(loaded_alice, loaded_alice)
        == sender_balance - amount
    )


def test_transfer_to_self_no_approval(loaded_alice, swap):
    amount = swap.balanceOf(loaded_alice)

    with boa.reverts(), boa.env.prank(loaded_alice):
        swap.transferFrom(loaded_alice, loaded_alice, amount)


def test_transfer_event_fires(loaded_alice, bob, charlie, swap):
    amount = swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        swap.approve(bob, amount)

    with boa.env.prank(bob):
        swap.transferFrom(loaded_alice, charlie, amount)

    logs = swap.get_logs()

    assert len(logs) == 2
    assert logs[0].event_type.name == "Approval"
    assert logs[0].args[0] == 0  # since everything got transferred
    assert logs[0].topics[0].lower() == loaded_alice.lower()
    assert logs[0].topics[1].lower() == bob.lower()

    assert logs[1].event_type.name == "Transfer"
    assert logs[1].args[0] == amount
    assert logs[1].topics[0].lower() == loaded_alice.lower()
    assert logs[1].topics[1].lower() == charlie.lower()
