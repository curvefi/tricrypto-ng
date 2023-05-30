import boa


def test_sender_balance_decreases(loaded_alice, bob, swap):
    sender_balance = swap.balanceOf(loaded_alice)
    amount = sender_balance // 4

    with boa.env.prank(loaded_alice):
        swap.transfer(bob, amount)

    assert swap.balanceOf(loaded_alice) == sender_balance - amount


def test_receiver_balance_increases(loaded_alice, bob, swap):
    receiver_balance = swap.balanceOf(bob)
    amount = swap.balanceOf(loaded_alice) // 4

    with boa.env.prank(loaded_alice):
        swap.transfer(bob, amount)

    assert swap.balanceOf(bob) == receiver_balance + amount


def test_total_supply_not_affected(loaded_alice, bob, swap):
    total_supply = swap.totalSupply()
    amount = swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        swap.transfer(bob, amount)

    assert swap.totalSupply() == total_supply


def test_returns_true(loaded_alice, bob, swap):
    amount = swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        assert swap.transfer(bob, amount)


def test_transfer_full_balance(loaded_alice, bob, swap):
    amount = swap.balanceOf(loaded_alice)
    receiver_balance = swap.balanceOf(bob)

    with boa.env.prank(loaded_alice):
        swap.transfer(bob, amount)

    assert swap.balanceOf(loaded_alice) == 0
    assert swap.balanceOf(bob) == receiver_balance + amount


def test_transfer_zero_tokens(loaded_alice, bob, swap):
    sender_balance = swap.balanceOf(loaded_alice)
    receiver_balance = swap.balanceOf(bob)

    with boa.env.prank(loaded_alice):
        swap.transfer(bob, 0)

    assert swap.balanceOf(loaded_alice) == sender_balance
    assert swap.balanceOf(bob) == receiver_balance


def test_transfer_to_self(loaded_alice, swap):
    sender_balance = swap.balanceOf(loaded_alice)
    amount = sender_balance // 4

    with boa.env.prank(loaded_alice):
        swap.transfer(loaded_alice, amount)

    assert swap.balanceOf(loaded_alice) == sender_balance


def test_insufficient_balance(loaded_alice, bob, swap):
    balance = swap.balanceOf(loaded_alice)

    with boa.reverts(), boa.env.prank(loaded_alice):
        swap.transfer(bob, balance + 1)


def test_transfer_event_fires(loaded_alice, bob, swap):
    amount = swap.balanceOf(loaded_alice)
    with boa.env.prank(loaded_alice):
        swap.transfer(bob, amount)

    logs = swap.get_logs()

    assert len(logs) == 1
    assert logs[0].event_type.name == "Transfer"
    assert logs[0].args[0] == amount
    assert logs[0].topics[0].lower() == loaded_alice.lower()
    assert logs[0].topics[1].lower() == bob.lower()
