import click
from ape import Contract, accounts, project
from ape.cli import NetworkBoundCommand, account_option, network_option

from scripts.deployment_utils import _get_tx_params

POOL = "0x7f86bf177dd4f3494b841a37e810a34dd56c829b"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"


@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def main(network, account):

    account.set_autosign(True)
    pool = Contract(POOL)
    with accounts.use_sender(account) as account:

        # deploy strategy:
        # strategy = account.deploy(
        #     project.CurveExchangeExtendedDemo,
        #     account,
        #     POOL,
        #     account,
        #     **_get_tx_params()
        # )
        strategy = project.CurveExchangeExtendedDemo.at(
            "0x506f594ceb4e33f5161139bae3ee911014df9f7f"
        )

        # get weth:
        # weth = Contract(WETH)
        # weth.approve(
        #     strategy.address, 10**12, **_get_tx_params()
        # )

        expected_out = pool.get_dy(2, 1, 10**12)

        tx = strategy.callback_and_swap(
            2, 1, 10**12, int(0.99 * expected_out), **_get_tx_params()
        )

        dy_wbtc = tx.decode_logs()[2].tokens_bought

        wbtc = Contract(pool.coins(1))
        wbtc.approve(strategy.address, dy_wbtc, **_get_tx_params())

        expected_out = pool.get_dy(1, 2, dy_wbtc)

        strategy.callback_and_swap(
            1, 2, dy_wbtc, int(0.99 * expected_out), **_get_tx_params()
        )
