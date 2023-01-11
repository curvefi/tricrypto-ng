import boa


def test_sender_balance_decreases(loaded_alice, bob, tricrypto_swap):
    sender_balance = tricrypto_swap.balanceOf(loaded_alice)
    amount = sender_balance // 4

    with boa.env.prank(loaded_alice):
        tricrypto_swap.transfer(bob, amount)

    assert tricrypto_swap.balanceOf(loaded_alice) == sender_balance - amount


def test_receiver_balance_increases(loaded_alice, bob, tricrypto_swap):
    receiver_balance = tricrypto_swap.balanceOf(bob)
    amount = tricrypto_swap.balanceOf(loaded_alice) // 4

    with boa.env.prank(loaded_alice):
        tricrypto_swap.transfer(bob, amount)

    assert tricrypto_swap.balanceOf(bob) == receiver_balance + amount


def test_total_supply_not_affected(loaded_alice, bob, tricrypto_swap):
    total_supply = tricrypto_swap.totalSupply()
    amount = tricrypto_swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.transfer(bob, amount)

    assert tricrypto_swap.totalSupply() == total_supply


def test_returns_true(loaded_alice, bob, tricrypto_swap):
    amount = tricrypto_swap.balanceOf(loaded_alice)

    with boa.env.prank(loaded_alice):
        assert tricrypto_swap.transfer(bob, amount)


def test_transfer_full_balance(loaded_alice, bob, tricrypto_swap):
    amount = tricrypto_swap.balanceOf(loaded_alice)
    receiver_balance = tricrypto_swap.balanceOf(bob)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.transfer(bob, amount)

    assert tricrypto_swap.balanceOf(loaded_alice) == 0
    assert tricrypto_swap.balanceOf(bob) == receiver_balance + amount


def test_transfer_zero_tokens(loaded_alice, bob, tricrypto_swap):
    sender_balance = tricrypto_swap.balanceOf(loaded_alice)
    receiver_balance = tricrypto_swap.balanceOf(bob)

    with boa.env.prank(loaded_alice):
        tricrypto_swap.transfer(bob, 0)

    assert tricrypto_swap.balanceOf(loaded_alice) == sender_balance
    assert tricrypto_swap.balanceOf(bob) == receiver_balance


def test_transfer_to_self(loaded_alice, tricrypto_swap):
    sender_balance = tricrypto_swap.balanceOf(loaded_alice)
    amount = sender_balance // 4

    with boa.env.prank(loaded_alice):
        tricrypto_swap.transfer(loaded_alice, amount)

    assert tricrypto_swap.balanceOf(loaded_alice) == sender_balance


def test_insufficient_balance(loaded_alice, bob, tricrypto_swap):
    balance = tricrypto_swap.balanceOf(loaded_alice)

    with boa.reverts(), boa.env.prank(loaded_alice):
        tricrypto_swap.transfer(bob, balance + 1)


def test_transfer_event_fires(loaded_alice, bob, tricrypto_swap):
    amount = tricrypto_swap.balanceOf(loaded_alice)
    with boa.env.prank(loaded_alice):
        tricrypto_swap.transfer(bob, amount)

    logs = tricrypto_swap.get_logs()

    assert len(logs) == 1
    assert logs[0].event_type.name == "Transfer"
    assert logs[0].args[0] == amount
    assert logs[0].topics[0].lower() == loaded_alice.lower()
    assert logs[0].topics[1].lower() == bob.lower()
