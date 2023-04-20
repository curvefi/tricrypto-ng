import warnings

import click
from ape import Contract, project
from ape.cli import NetworkBoundCommand, account_option, network_option
from ape.logging import logger
from eth_abi import encode
from eth_utils import to_checksum_address

import scripts.deployment_utils as deploy_utils
from scripts.simulate import simulate
from scripts.vote_utils import make_vote

warnings.filterwarnings("ignore")

DOLLAR_VALUE_OF_TOKENS_TO_DEPOSIT = 20


@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy_ethereum(network, account):

    assert "ethereum" in network

    is_sim = "mainnet-fork" in network
    PARAMS = deploy_utils.get_tricrypto_usdc_params()

    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if _network in network:

            owner = data.dao_ownership_contract
            fee_receiver = data.fee_receiver_address
            coins = [
                to_checksum_address(data.usdc_address),
                to_checksum_address(data.wbtc_address),
                to_checksum_address(data.weth_address),
            ]
            weth = coins[2]
            PARAMS["coins"] = coins

    assert owner, f"Curve's DAO contracts may not be on {network}."
    assert fee_receiver, f"Curve's DAO contracts may not be on {network}."

    logger.info("------------ DEPLOY MAIN + AUXILIARY CONTRACTS ------------")

    logger.info("Deploying math contract:")
    math_contract = account.deploy(project.CurveCryptoMathOptimized3)

    logger.info("Deploying views contract:")
    views_contract = account.deploy(project.CurveCryptoViews3Optimized)

    logger.info("Deploying AMM blueprint contract:")
    amm_impl = deploy_utils.deploy_blueprint(
        project.CurveTricryptoOptimizedWETH, account
    )

    logger.info("Deploying gauge blueprint contract:")
    gauge_impl = deploy_utils.deploy_blueprint(project.LiquidityGauge, account)

    logger.info("------------ DEPLOY FACTORY ------------")

    logger.info("Deploy factory:")
    constructor_args = [fee_receiver, account.address, weth]
    factory = account.deploy(project.CurveTricryptoFactory, *constructor_args)
    logger.info(
        f"Constructor args: {encode(['address', 'address', 'address'], constructor_args).hex()}\n"  # noqa: E501
    )

    logger.info("Set Pool Implementation:")
    factory.set_pool_implementation(amm_impl, 0, sender=account)

    logger.info("Set Gauge Implementation:")
    factory.set_gauge_implementation(gauge_impl, sender=account)

    logger.info("Set Views implementation:")
    factory.set_views_implementation(views_contract, sender=account)

    logger.info("Set Math implementation:")
    factory.set_math_implementation(math_contract, sender=account)

    logger.info("------------ DEPLOY POOL ------------")

    logger.info("Deploying Pool:")

    tx = factory.deploy_pool(
        PARAMS["name"],
        PARAMS["symbol"],
        PARAMS["coins"],
        PARAMS["implementation_index"],
        PARAMS["A"],
        PARAMS["gamma"],
        PARAMS["mid_fee"],
        PARAMS["out_fee"],
        PARAMS["fee_gamma"],
        PARAMS["allowed_extra_profit"],
        PARAMS["adjustment_step"],
        PARAMS["ma_time"],
        PARAMS["initial_prices"],
        sender=account,
    )
    pool = project.CurveTricryptoOptimizedWETH.at(
        tx.events.filter(factory.TricryptoPoolDeployed)[0].pool
    )
    logger.info(f"Success Deployed pool at {pool}!")

    # ----------------- Swap Tests ------------------

    logger.info(
        "------------ TEST IF CONTRACT WORKS AS INTENDED IN PROD ----------------"  # noqa: E501
    )

    for coin in coins:
        coin_contract = Contract(coin)
        bal = coin_contract.balanceOf(account)
        assert bal > 0, "Not enough coins!"

        coin_name = coin_contract.name()
        logger.info(f"Approve pool to spend deployer's {coin_name}:")

        coin_contract.approve(pool, bal, sender=account)

    logger.info("------------------------------ Add liquidity")

    logger.info("Deposit WETH with other tokens:")
    tokens_to_add = deploy_utils.get_deposit_amounts(
        DOLLAR_VALUE_OF_TOKENS_TO_DEPOSIT, PARAMS["initial_prices"], coins
    )

    logger.info(f"Add {tokens_to_add} tokens to deployed pool: ")

    tx = pool.add_liquidity(tokens_to_add, 0, False, sender=account)
    d_tokens = tx.return_value
    assert pool.balanceOf(account) == pool.totalSupply() == d_tokens
    logger.info(f"Received {d_tokens} number of LP Tokens.")

    logger.info("Deposit ETH with other tokens:")
    tx = pool.add_liquidity(
        tokens_to_add, 0, True, sender=account, value=tokens_to_add[2]
    )
    d_tokens = tx.return_value
    assert d_tokens > 0
    logger.info(f"Received {d_tokens} number of LP Tokens.")

    logger.info("------------------------------ Exchange")

    amt_usdc_in = 10 * 10 ** Contract(coins[0]).decimals()
    logger.info(f"Test exchange_underlying of {amt_usdc_in} USDC -> ETH:")
    tx = pool.exchange_underlying(0, 2, amt_usdc_in, 0, sender=account)
    dy_eth = tx.events.filter(pool.TokenExchange)[
        0
    ].tokens_bought  # return_value is broken in ape somehow
    assert dy_eth > 0
    logger.info(f"Received {dy_eth} ETH")

    logger.info(f"Test exchange_underlying of {dy_eth} ETH -> USDC:")
    tx = pool.exchange_underlying(
        2, 0, dy_eth, 0, sender=account, value=dy_eth
    )
    dy_usdc = tx.events.filter(pool.TokenExchange)[0].tokens_bought
    assert dy_usdc > 0
    logger.info(f"Received {dy_usdc} USDC")

    logger.info(f"Test exchange of {dy_usdc} USDC -> WBTC:")
    tx = pool.exchange(0, 1, dy_usdc * 2, 0, sender=account)
    dy_wbtc = tx.events.filter(pool.TokenExchange)[0].tokens_bought
    assert dy_wbtc > 0
    logger.info(f"Received {dy_wbtc} WBTC")

    logger.info("------------------------------ Remove Liquidity in one coin")

    eth_balance = account.balance
    bal = pool.balanceOf(account)
    amt_to_remove = int(bal / 4)
    logger.info("Remove {amt_to_remove} liquidity in native token (ETH):")
    tx = pool.remove_liquidity_one_coin(
        amt_to_remove, 2, 0, True, sender=account
    )
    dy_eth = tx.events.filter(pool.RemoveLiquidityOne)[0].coin_amount
    assert dy_eth > 0
    assert account.balance == eth_balance + dy_eth
    logger.info(f"Removed {dy_eth} of ETH.")

    for coin_id, coin in enumerate(coins):

        bal = pool.balanceOf(account)
        coin_contract = Contract(coin)
        coin_name = coin_contract.name()
        coin_balance = coin_contract.balanceOf(account)

        logger.info(f"Remove {int(bal/4)} liquidity in {coin_name}:")
        tx = pool.remove_liquidity_one_coin(
            int(bal / 4), coin_id, 0, False, sender=account
        )  # noqa: E501

        dy_coin = tx.events.filter(pool.RemoveLiquidityOne)[0].coin_amount
        assert dy_coin > 0
        assert coin_contract.balanceOf(account) == coin_balance + dy_coin
        logger.info(f"Removed {dy_coin} of {coin_name}.")

    logger.info("------------------------------ Claim admin fees")
    logger.info("(should not claim since pool hasn't accrued enough profits)")

    fees_claimed = pool.balanceOf(fee_receiver)
    pool.claim_admin_fees(sender=account)
    if pool.totalSupply() < 10**18:
        assert pool.balanceOf(fee_receiver) == fees_claimed
        logger.info("No fees claimed.")
    else:
        assert pool.balanceOf(fee_receiver) > fees_claimed
        logger.info(
            f"{pool.balanceOf(fee_receiver) - fees_claimed} LP tokens of admin fees claimed!"  # noqa: E501
        )

    logger.info(
        "------------------------------ Remove liquidity proportionally"
    )

    eth_balance = account.balance
    bal = pool.balanceOf(account)
    logger.info(
        f"Remove {int(bal/4)} amount of liquidity proportionally (with native ETH):"  # noqa: E501
    )
    tx = pool.remove_liquidity(int(bal / 4), [0, 0, 0], True, sender=account)
    dy_tokens = tx.events.filter(pool.RemoveLiquidity)[0].token_amounts
    for tkn_amt in dy_tokens:
        assert tkn_amt > 0

    logger.info(f"Removed {dy_tokens} of liquidity.")

    assert eth_balance + dy_tokens[2] == account.balance

    logger.info(
        f"Remove {int(bal/4)} amount of liquidity proportionally (with native ETH):"  # noqa: E501
    )
    tx = pool.remove_liquidity(int(bal / 4), [0, 0, 0], False, sender=account)
    dy_tokens = tx.return_value

    for tkn_amt in dy_tokens:
        assert tkn_amt > 0

    logger.info("Successfully tested deployment!")

    logger.info(
        "------------ DEPLOY GAUGE AND SET UP GAUGE FOR DAO VOTE -------------"  # noqa: E501
    )

    logger.info("Deploying Gauge:")
    tx = factory.deploy_gauge(pool, sender=account)
    gauge = project.LiquidityGauge.at(
        tx.events.filter(factory.LiquidityGaugeDeployed)[0].gauge
    )

    # ------------------- CURVE DAO RELATED CODE -----------------------------

    logger.info("Adding gauge to the gauge controller:")

    ACTIONS = [
        (deploy_utils.GAUGE_CONTROLLER, "add_gauge", gauge.address, 5, 0),
    ]
    DESCRIPTION = "Add tricryptoUSDC [ethereum] gauge to the gauge controller"

    vote_id = make_vote(
        deploy_utils.CURVE_DAO_OWNERSHIP, ACTIONS, DESCRIPTION, account
    )

    if is_sim:
        simulate(vote_id, deploy_utils.CURVE_DAO_OWNERSHIP["voting"])
        assert (
            Contract(deploy_utils.GAUGE_CONTROLLER).gauge_types(gauge.address)
            == 5
        )

    logger.info(
        "-------- TRANSFER FACTORY OWNERSHIP TO THE APPROPRIATE ENTITY ----------"  # noqa: E501
    )

    factory.commit_transfer_ownership(owner, sender=account)
    assert factory.future_admin() == owner

    logger.info(
        "----------- CREATE VOTE FOR THE DAO TO ACCEPT OWNERSHIP OF FACTORY -----"  # noqa: E501
    )

    ACTIONS = [
        (factory.address, "accept_transfer_ownership"),
    ]
    DESCRIPTION = "Accept ownership of optimized tricrypto factory [Ethereum]"

    vote_id = make_vote(
        deploy_utils.CURVE_DAO_OWNERSHIP, ACTIONS, DESCRIPTION, account
    )

    if is_sim:
        simulate(vote_id, deploy_utils.CURVE_DAO_OWNERSHIP["voting"])
        assert factory.admin() == owner
