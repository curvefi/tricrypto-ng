import pytest
from ape import Contract, Project, chain
from ape.contracts import ContractContainer

from scripts.deploy import deploy_infra


@pytest.fixture(scope="function")
def admin():
    return "0x40907540d8a6C65c637785e8f8B742ae6b0b9968"


@pytest.fixture(scope="function")
def deploy(admin, project: Project):
    pool, coins, fee_receiver, _account = deploy_infra(
        project.network_manager.network.name, admin
    )
    return Contract(pool), [Contract(c) for c in coins], fee_receiver, _account


@pytest.fixture(scope="function")
def admin_mint_tokens(admin, project):
    # USDC
    token_impl = ContractContainer(
        Contract("0xB7277a6e95992041568D9391D09d0122023778A2").contract_type
    )
    token_contract = token_impl.at(
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    )
    token_minter = "0xe982615d461dd5cd06575bbea87624fda4e3de17"
    project.provider.set_balance(token_minter, 10**18)
    amount = 1000 * 10**6
    token_contract.configureMinter(token_minter, amount, sender=token_minter)
    token_contract.mint(admin, amount, sender=token_minter)
    assert token_contract.balanceOf(admin) >= amount

    # WETH
    project.provider.set_balance(admin, 2 * 10**18)
    weth_contract = Contract(
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        contract_type=chain.contracts._get_contract_type_from_explorer(
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        ),
    )
    weth_contract.deposit(value=1 * 10**18, sender=admin)
    assert weth_contract.balanceOf(admin) >= 1 * 10**18

    # WBTC
    wbtc_contract = Contract(
        "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        contract_type=chain.contracts._get_contract_type_from_explorer(
            "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
        ),
    )
    wbtc_owner = wbtc_contract.owner()
    project.provider.set_balance(wbtc_owner, 1 * 10**18)
    wbtc_contract.mint(admin, 1 * 10**7, sender=wbtc_owner)
    assert wbtc_contract.balanceOf(admin) >= 1 * 10**7


@pytest.fixture(scope="function")
def approve_admin(admin, deploy):
    pool = deploy[0]
    for coin in deploy[1]:
        coin.approve(pool.address, 2**256 - 1, sender=admin)
