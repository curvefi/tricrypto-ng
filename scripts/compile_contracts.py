import boa

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
}
INITIAL_PRICES = [47500 * 10**18, 1500 * 10**18]


def compile_swap_source_code(
    coins, tricrypto_math, tricrypto_lp_token, tricrypto_views, optimized
):

    path = "contracts/old/CurveCryptoSwap.vy"
    if optimized:
        path = "contracts/CurveTricryptoOptimized.vy"

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
            "1,#0", str(10 ** (18 - coins[0].decimals())) + ","
        )
        source = source.replace(
            "1,#1", str(10 ** (18 - coins[1].decimals())) + ","
        )
        source = source.replace(
            "1,#2", str(10 ** (18 - coins[2].decimals())) + ","
        )
        return source


def deploy(optimized: bool = True, params: dict = PARAMS):

    deployer = boa.env.generate_address()

    with boa.env.prank(deployer):
        eth = boa.load("contracts/mocks/WETH.vy")
        usd = boa.load("contracts/mocks/ERC20Mock.vy", "USD", "USD", 18)
        btc = boa.load("contracts/mocks/ERC20Mock.vy", "BTC", "BTC", 18)
        coins = [usd, btc, eth]

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
        if not optimized:
            views = boa.load("contracts/old/CurveCryptoViews3.vy", math)

        # tricrypto
        source = compile_swap_source_code(coins, math, token, views, optimized)
        swap = boa.loads(
            source,
            boa.env.generate_address(),
            boa.env.generate_address(),
            PARAMS["A"],
            PARAMS["gamma"],
            PARAMS["mid_fee"],
            PARAMS["out_fee"],
            PARAMS["allowed_extra_profit"],
            PARAMS["fee_gamma"],
            PARAMS["adjustment_step"],
            PARAMS["admin_fee"],
            PARAMS["ma_time"],
            INITIAL_PRICES,
        )
        if not optimized:
            token.set_minter(swap.address)

    # optimized tricrypto is an erc20 implementation:
    if optimized:
        token = swap

    return swap, token, math, views, coins


def main():

    swap, token, math, views, _ = deploy(optimized=False)

    # print bytecode size
    print("OG Tricrypto Contract sizes:")
    print(f"Swap: {len(swap.bytecode)}")
    print(f"Token: {len(token.bytecode)}")
    print(f"Math: {len(math.bytecode)}")
    print(f"Views: {len(views.bytecode)} (not included in calcs)")
    total_size_og = sum(len(i.bytecode) for i in [swap, token, math])
    print(f"Total: {total_size_og}")

    params = PARAMS
    params["ma_time"] = 866  # 600 / ln(2)
    swap, token, math, views, _ = deploy(optimized=True, params=params)

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
