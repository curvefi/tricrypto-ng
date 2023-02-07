import boa

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


def compile_swap_source_code(
    coins, tricrypto_math, tricrypto_lp_token, tricrypto_views, optimized, path
):

    with open(path, "r") as f:

        source = f.read()
        source = source.replace(
            "0x0000000000000000000000000000000000000000",
            tricrypto_math.address,
        )

        if not optimized:
            source = source.replace(
                "0x0000000000000000000000000000000000000001",
                tricrypto_lp_token.address,
            )

            source = source.replace(
                "0x0000000000000000000000000000000000000002",
                tricrypto_views.address,
            )

        source = source.replace(
            "0x0000000000000000000000000000000000000010", coins[0].address
        )
        source = source.replace(
            "0x0000000000000000000000000000000000000011", coins[1].address
        )
        source = source.replace(
            "0x0000000000000000000000000000000000000012", coins[2].address
        )

        source = source.replace(
            "1,  # 0", str(10 ** (18 - coins[0].decimals())) + ","
        )
        source = source.replace(
            "1,  # 1", str(10 ** (18 - coins[1].decimals())) + ","
        )
        source = source.replace(
            "1,  # 2", str(10 ** (18 - coins[2].decimals())) + ","
        )
        return source


def deploy(
    coins,
    swap_contract="contracts/CurveTricryptoOptimizedWETH.vy",
    optimized: bool = True,
    params: dict = PARAMS,
):

    deployer = boa.env.generate_address()

    with boa.env.prank(deployer):

        token = None
        if not optimized:
            token = boa.load(
                "contracts/old/CurveTokenV4.vy",
                "Curve USD-BTC-ETH",
                "crvUSDBTCETH",
            )

        math_contract = "contracts/old/CurveCryptoMath3.vy"
        if optimized:
            math_contract = "contracts/CurveCryptoMathOptimized3.vy"
        math = boa.load(math_contract)

        views = None
        if not optimized:
            views = boa.load("contracts/old/CurveCryptoViews3.vy", math)

        # tricrypto
        source = compile_swap_source_code(
            coins, math, token, views, optimized, swap_contract
        )
        swap = boa.loads(
            source,
            boa.env.generate_address(),
            boa.env.generate_address(),
            params["A"],
            params["gamma"],
            params["mid_fee"],
            params["out_fee"],
            params["allowed_extra_profit"],
            params["fee_gamma"],
            params["adjustment_step"],
            params["admin_fee"],
            params["ma_time"],
            params["initial_prices"],
        )
        if not optimized:
            token.set_minter(swap.address)

    # optimized tricrypto is an erc20 implementation:
    if optimized:
        token = swap
        views = boa.load("contracts/CurveCryptoViews3Optimized.vy", math, swap)

    return swap, token, math, views, coins


def main():

    with boa.env.prank(boa.env.generate_address()):
        eth = boa.load("contracts/mocks/WETH.vy")
        usd = boa.load("contracts/mocks/ERC20Mock.vy", "USD", "USD", 18)
        btc = boa.load("contracts/mocks/ERC20Mock.vy", "BTC", "BTC", 18)
    coins = [usd, btc, eth]

    params = PARAMS
    swap, token, math, views, _ = deploy(
        coins=coins,
        swap_contract="contracts/old/CurveCryptoSwap.vy",
        optimized=False,
        params=params,
    )

    # print bytecode size
    print("OG Tricrypto Contract sizes:")
    print(f"Swap: {len(swap.bytecode)}")
    print(f"Token: {len(token.bytecode)}")
    print(f"Math: {len(math.bytecode)}")
    print(f"Views: {len(views.bytecode)} (not included in calcs)")
    total_size_og = sum(len(i.bytecode) for i in [swap, token, math])
    print(f"Total: {total_size_og}")

    params["ma_time"] = 866  # 600 / ln(2)
    swap, token, math, views, _ = deploy(
        coins=coins,
        swap_contract="contracts/CurveTricryptoOptimizedWETH.vy",
        optimized=True,
        params=params,
    )

    # print bytecode size
    print("Optimized Contract sizes:")
    print(f"Swap: {len(swap.bytecode)}")
    print(f"Math: {len(math.bytecode)}")
    print(f"Views: {len(views.bytecode)} (not included in calcs)")
    total_size = len(swap.bytecode) + len(math.bytecode)
    print(f"Total: {total_size}")
    print(f"Optimized Swap is larger by: {total_size - total_size_og}")


if __name__ == "__main__":
    main()
