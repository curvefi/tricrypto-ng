import random

import boa
import click
from compile_contracts import deploy
from eth_utils import to_checksum_address
from rich.console import Console
from rich.progress import Progress

console = Console()


def mint_for_testing(token_contract, addr, amount):

    addr = to_checksum_address(addr)

    if token_contract.symbol() == "WETH":
        boa.env.set_balance(addr, boa.env.get_balance(addr) + amount)
        with boa.env.prank(addr):
            token_contract.deposit(value=amount)
    else:
        token_contract.eval(f"self.totalSupply += {amount}")
        token_contract.eval(f"self.balanceOf[{addr}] += {amount}")
        token_contract.eval(f"log Transfer(empty(address), {addr}, {amount})")


def cubic_root(x):
    # x is taken at base 1e36
    # result is at base 1e18

    D = x / 10**18
    for i in range(255):
        diff = 0
        D_prev = D
        D = (
            D
            * (2 * 10**18 + x / D * 10**18 / D * 10**18 / D)
            / (3 * 10**18)
        )
        if D > D_prev:
            diff = D - D_prev
        else:
            diff = D_prev - D
        if diff <= 1 or diff * 10**18 < D:
            return D
    raise "Did not converge"


def opinionated_data_sampler():
    strats = [i for i in range(22)]
    max = 10 ** random.choice(strats)
    return random.randint(1, max)


def _lp_price(swap):

    vp = swap.virtual_price()
    p1 = swap.price_oracle(0)
    p2 = swap.price_oracle(1)

    return 3 * vp * cubic_root(p1 * p2) // 1e36


def _deposit(addr, coins, amounts, swap, token):

    addr_token_bal = token.balanceOf(addr)

    for coin, q in zip(coins, amounts):
        mint_for_testing(coin, addr, q)

    with boa.env.prank(addr):
        swap.add_liquidity(amounts, 0)

    tokens_minted = token.balanceOf(addr) - addr_token_bal
    return tokens_minted


def _get_deposit_amounts(initial_prices, coins):

    precisions = [10 ** coin.decimals() for coin in coins]

    deposit_dollar_amount = random.randint(a=1, b=10**7)
    deposit_amounts = [
        deposit_dollar_amount * precision * 10**18 // price
        for price, precision in zip(initial_prices, precisions)
    ]
    return deposit_amounts


def deploy_and_deposit(
    alice, bob, charlie, coins, params, initial_prices, swap
):

    params["ma_time"] = 866  # 600 / ln(2)
    swap, token, _, _, coins = deploy(
        coins=coins, swap_contract=swap, optimized=True, params=params
    )
    deposit_amounts = _get_deposit_amounts(initial_prices, coins)

    for coin in coins:
        for user in [alice, bob, charlie]:
            with boa.env.prank(user):
                coin.approve(swap, 2**256 - 1)

    for user in [alice, bob]:
        _deposit(user, coins, deposit_amounts, swap, token)

    return swap, token


def set_balanced_state(
    alice, bob, charlie, coins, params, initial_prices, swap
):

    swap, token = deploy_and_deposit(
        alice, bob, charlie, coins, params, initial_prices, swap
    )

    # bob withdraws proportionally:
    withdraw_fraction = random.uniform(0, 0.1)
    token_balance = token.balanceOf(bob)
    tokens_to_withdraw = int(token_balance * withdraw_fraction)

    with boa.env.prank(bob):
        swap.remove_liquidity(tokens_to_withdraw, [0, 0, 0])

    return swap, token


def set_unbalanced_state(
    alice, bob, charlie, coins, params, initial_prices, swap
):

    swap, token = deploy_and_deposit(
        alice, bob, charlie, coins, params, initial_prices, swap
    )

    # bob withdraws in one coin:
    coin_to_withdraw = random.randint(0, 2)

    with boa.env.prank(bob):
        swap.remove_liquidity_one_coin(10**18, coin_to_withdraw, 0)

    return swap, token


def _write(filename, generated_data):

    import os

    if not os.path.exists("data"):
        console.log("Creating data directory at ./data")
        os.mkdir("data")

    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write("amount_in,amount_out,trade_price,expected_price\n")

    with open(filename, "a") as f:
        for data in generated_data:
            f.write(data)


def deposit_usd(
    user,
    coins,
    swap,
    token,
    amount_in,
):

    expected_price = swap.last_prices(1) / 10**18

    try:

        deposit_amounts = [amount_in, 0, 0]
        tokens_minted = _deposit(user, coins, deposit_amounts, swap, token)

        trade_price = swap.last_prices(1) / 10**18

    except:  # noqa: E722

        trade_price = _lp_price(swap)
        tokens_minted = 0

    return {
        "amount_in": amount_in,
        "amount_out": tokens_minted,
        "trade_price": trade_price,
        "expected_price": expected_price,
    }


def withdraw_usd(
    user,
    coins,
    swap,
    amount_in,  # lp tokens
):

    expected_price = swap.last_prices(1) / 10**18

    try:

        bal_before = coins[0].balanceOf(user)

        with boa.env.prank(user):
            swap.remove_liquidity_one_coin(amount_in, 0, 0)

        received = coins[0].balanceOf(user) - bal_before
        trade_price = swap.last_prices(1) / 10**18

    except:  # noqa: E722

        trade_price = -1
        received = 0

    return {
        "amount_in": amount_in,
        "amount_out": received,  # usd tokens
        "trade_price": trade_price,
        "expected_price": expected_price,
    }


def exchange_usd_eth(
    user,
    coins,
    swap,
    amount_in,
):

    expected_price = swap.last_prices(1) / 10**18

    try:

        mint_for_testing(coins[0], user, amount_in)
        i = random.randint(0, 2)
        j = random.choice([k for k in range(3) if k != i])
        with boa.env.prank(user):
            received = swap.exchange(i, j, amount_in, 0)

        trade_price = swap.last_prices(1) / 10**18

    except:  # noqa: E722

        trade_price = -1
        received = 0

    return {
        "amount_in": amount_in,
        "amount_out": received,
        "trade_price": trade_price,
        "expected_price": expected_price,
    }


@click.command()
@click.option("--num_samples", default=10)
@click.option("--filedir", required=True)
@click.option("--swap", required=True)
def main(num_samples, filedir, swap):
    def _data_to_str(data):
        return (
            f"{data['amount_in']},{data['amount_out']},"
            f"{data['trade_price']},{data['expected_price']}\n"
        )

    def _save_data(filename, deposits_data, withdraw_data, exchange_data):

        _write(f"data/{filedir}/{filename}_deposit_trades.csv", deposits_data)
        _write(f"data/{filedir}/{filename}_withdraw_trades.csv", withdraw_data)
        _write(f"data/{filedir}/{filename}_exchange_trades.csv", exchange_data)

    console.log("Generating addresses ...")

    alice = boa.env.generate_address()
    bob = boa.env.generate_address()
    charlie = boa.env.generate_address()

    INITIAL_PRICES = [10**18, 47500 * 10**18, 1500 * 10**18]
    PARAMS = {
        "A": 135 * 3**3 * 10000,
        "gamma": int(7e-5 * 1e18),
        "mid_fee": int(4e-4 * 1e10),
        "out_fee": int(4e-3 * 1e10),
        "allowed_extra_profit": 2 * 10**12,
        "fee_gamma": int(0.01 * 1e18),
        "adjustment_step": int(0.0015 * 1e18),
        "admin_fee": 5 * 10**9,
        "ma_time": 600,
        "initial_prices": INITIAL_PRICES[1:],
    }

    console.log("Deploying coins ...")

    with boa.env.prank(boa.env.generate_address()):
        usd = boa.load("contracts/mocks/ERC20Mock.vy", "USD", "USD", 18)
        btc = boa.load("contracts/mocks/ERC20Mock.vy", "BTC", "BTC", 18)
        eth = boa.load("contracts/mocks/WETH.vy")  # 18 decimals
    coins = [usd, btc, eth]
    for coin in coins:
        console.log(f"Deployed {coin.name()} with {coin.decimals()} decimals.")

    console.log(f"Deploying {swap} and setting state ...")

    with Progress(console=console) as progress:

        states = {
            "balanced_state": set_balanced_state(
                alice, bob, charlie, coins, PARAMS, INITIAL_PRICES, swap
            ),
            "unbalanced_state": set_unbalanced_state(
                alice, bob, charlie, coins, PARAMS, INITIAL_PRICES, swap
            ),
        }

        task = progress.add_task("Generating data ...", total=2 * num_samples)

        for filename, state in states.items():

            swap, token = state

            deposits_data = []
            withdraw_data = []
            exchange_data = []
            for n_sample in range(num_samples):

                # -------------- generate data -----------------

                dust_amount = opinionated_data_sampler()

                with boa.env.anchor():
                    data = deposit_usd(
                        charlie, coins, swap, token, dust_amount
                    )
                    deposits_data.append(_data_to_str(data))

                with boa.env.anchor():
                    data = withdraw_usd(alice, coins, swap, dust_amount)
                    withdraw_data.append(_data_to_str(data))

                with boa.env.anchor():
                    data = exchange_usd_eth(charlie, coins, swap, dust_amount)
                    exchange_data.append(_data_to_str(data))

                progress.update(task, advance=1)

            _save_data(filename, deposits_data, withdraw_data, exchange_data)

    console.log("Saved data. Exiting.")


if __name__ == "__main__":
    main()
