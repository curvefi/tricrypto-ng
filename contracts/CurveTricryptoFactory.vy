# @version 0.3.7
"""
@title Curve Factory
@license MIT
@author Curve.Fi
@notice Permissionless 3-coin cryptoswap pool deployer and registry
"""


interface TricryptoPool:
    def balances(i: uint256) -> uint256: view
    def initialize(
        A: uint256,
        gamma: uint256,
        mid_fee: uint256,
        out_fee: uint256,
        allowed_extra_profit: uint256,
        fee_gamma: uint256,
        adjustment_step: uint256,
        admin_fee: uint256,
        ma_half_time: uint256,
        initial_price: uint256,
        _coins: address[N_COINS],
        _precisions: uint256[N_COINS],
    ): nonpayable

interface ERC20:
    def decimals() -> uint256: view

interface LiquidityGauge:
    def initialize(_lp_token: address): nonpayable


event TricryptoPoolDeployed:
    coins: address[N_COINS]
    A: uint256
    gamma: uint256
    mid_fee: uint256
    out_fee: uint256
    allowed_extra_profit: uint256
    fee_gamma: uint256
    adjustment_step: uint256
    admin_fee: uint256
    ma_half_time: uint256
    initial_price: uint256
    deployer: address

event LiquidityGaugeDeployed:
    pool: address
    gauge: address

event UpdateFeeReceiver:
    _old_fee_receiver: address
    _new_fee_receiver: address

event UpdatePoolImplementation:
    _old_pool_implementation: address
    _new_pool_implementation: address

event UpdateGaugeImplementation:
    _old_gauge_implementation: address
    _new_gauge_implementation: address

event TransferOwnership:
    _old_owner: address
    _new_owner: address


struct PoolArray:
    token: address
    liquidity_gauge: address
    coins: address[N_COINS]
    decimals: uint256[N_COINS]


N_COINS: constant(int128) = 3
A_MULTIPLIER: constant(uint256) = 10000

# Limits
MAX_ADMIN_FEE: constant(uint256) = 10 * 10 ** 9
MIN_FEE: constant(uint256) = 5 * 10 ** 5  # 0.5 bps
MAX_FEE: constant(uint256) = 10 * 10 ** 9

MIN_GAMMA: constant(uint256) = 10 ** 10
MAX_GAMMA: constant(uint256) = 2 * 10 ** 16

MIN_A: constant(uint256) = N_COINS ** N_COINS * A_MULTIPLIER / 10
MAX_A: constant(uint256) = N_COINS ** N_COINS * A_MULTIPLIER * 100000


WETH: immutable(address)


admin: public(address)
future_admin: public(address)

# fee receiver for plain pools
fee_receiver: public(address)

pool_implementation: public(address)
gauge_implementation: public(address)

views: public(address)

# mapping of coins -> pools for trading
# a mapping key is generated for each pair of addresses via
# `bitwise_xor(convert(a, uint256), convert(b, uint256))`
markets: HashMap[uint256, address[4294967296]]
market_counts: HashMap[uint256, uint256]

pool_count: public(uint256)              # actual length of pool_list
pool_data: HashMap[address, PoolArray]
pool_list: public(address[4294967296])   # master list of pools


@external
def __init__(
    _fee_receiver: address,
    _pool_implementation: address,
    _gauge_implementation: address,
    _math: address,
    _views: address,
    _weth: address
):
    self.fee_receiver = _fee_receiver

    self.pool_implementation = _pool_implementation
    self.gauge_implementation = _gauge_implementation

    self.views = _views

    self.admin = msg.sender
    WETH = _weth

    log UpdateFeeReceiver(empty(address), _fee_receiver)
    log UpdatePoolImplementation(empty(address), _pool_implementation)
    log UpdateGaugeImplementation(empty(address), _gauge_implementation)
    log TransferOwnership(empty(address), msg.sender)


# <--- Pool Deployers --->

@external
def deploy_pool(
    _name: String[32],
    _symbol: String[10],
    _coins: address[N_COINS],
    A: uint256,
    gamma: uint256,
    mid_fee: uint256,
    out_fee: uint256,
    allowed_extra_profit: uint256,
    fee_gamma: uint256,
    adjustment_step: uint256,
    admin_fee: uint256,
    ma_exp_time: uint256,
    initial_price: uint256
) -> address:
    """
    @notice Deploy a new pool
    @param _name Name of the new plain pool
    @param _symbol Symbol for the new plain pool - will be concatenated with factory symbol
    Other parameters need some description
    @return Address of the deployed pool
    """
    # Validate parameters
    assert A > MIN_A-1
    assert A < MAX_A+1
    assert gamma > MIN_GAMMA-1
    assert gamma < MAX_GAMMA+1
    assert mid_fee > MIN_FEE-1
    assert mid_fee < MAX_FEE-1
    assert out_fee >= mid_fee
    assert out_fee < MAX_FEE-1
    assert admin_fee < 10**18+1
    assert allowed_extra_profit < 10**16+1
    assert fee_gamma < 10**18+1
    assert fee_gamma > 0
    assert adjustment_step < 10**18+1
    assert adjustment_step > 0
    assert ma_exp_time < 872542  # 7 * 24 * 60 * 60 / ln(2)
    assert ma_exp_time > 0
    assert initial_price > 10**6
    assert initial_price < 10**30
    assert _coins[0] != _coins[1], "Duplicate coins"
    assert _coins[1] != _coins[2], "Duplicate coins"
    assert _coins[0] != _coins[2], "Duplicate coins"

    decimals: uint256[N_COINS] = empty(uint256[N_COINS])
    precisions: uint256[N_COINS] = empty(uint256[N_COINS])
    for i in range(N_COINS):
        d: uint256 = ERC20(_coins[i]).decimals()
        assert d < 19, "Max 18 decimals for coins"
        decimals[i] = d
        precisions[i] = 18 - d


    name: String[64] = concat("Curve.fi Factory 3crypto Pool: ", _name)
    symbol: String[32] = concat(_symbol, "-f")

    # pool is an ERC20 implementation
    pool: address = create_forwarder_to(self.pool_implementation)

    TricryptoPool(pool).initialize(
        A,
        gamma,
        mid_fee,
        out_fee,
        allowed_extra_profit,
        fee_gamma,
        adjustment_step,
        admin_fee,
        ma_exp_time,
        initial_price,
        _coins,
        precisions
    )

    length: uint256 = self.pool_count
    self.pool_list[length] = pool
    self.pool_count = length + 1
    self.pool_data[pool].decimals = decimals
    self.pool_data[pool].coins = _coins

    # add coins to market:
    for coin_a in _coins:
        for coin_b in _coins:

            if coin_a == coin_b:
                continue

            key: uint256 = bitwise_xor(
                convert(coin_a, uint256),
                convert(coin_b, uint256)
            )

            length = self.market_counts[key]
            self.markets[key][length] = pool
            self.market_counts[key] = length + 1

    log TricryptoPoolDeployed(
        _coins,
        A,
        gamma,
        mid_fee,
        out_fee,
        allowed_extra_profit,
        fee_gamma,
        adjustment_step,
        admin_fee,
        ma_exp_time,
        initial_price,
        msg.sender
    )

    return pool


@external
def deploy_gauge(_pool: address) -> address:
    """
    @notice Deploy a liquidity gauge for a factory pool
    @param _pool Factory pool address to deploy a gauge for
    @return Address of the deployed gauge
    """
    assert self.pool_data[_pool].coins[0] != empty(address), "Unknown pool"
    assert self.pool_data[_pool].liquidity_gauge == empty(address), "Gauge already deployed"

    gauge: address = create_forwarder_to(self.gauge_implementation)
    token: address = self.pool_data[_pool].token
    LiquidityGauge(gauge).initialize(token)
    self.pool_data[_pool].liquidity_gauge = gauge

    log LiquidityGaugeDeployed(_pool, gauge)
    return gauge


# <--- Admin / Guarded Functionality --->


@external
def set_fee_receiver(_fee_receiver: address):
    """
    @notice Set fee receiver
    @param _fee_receiver Address that fees are sent to
    """
    assert msg.sender == self.admin  # dev: admin only

    log UpdateFeeReceiver(self.fee_receiver, _fee_receiver)
    self.fee_receiver = _fee_receiver


@external
def set_pool_implementation(_pool_implementation: address):
    """
    @notice Set pool implementation
    @dev Set to empty(address) to prevent deployment of new pools
    @param _pool_implementation Address of the new pool implementation
    """
    assert msg.sender == self.admin  # dev: admin only

    log UpdatePoolImplementation(self.pool_implementation, _pool_implementation)
    self.pool_implementation = _pool_implementation


@external
def set_gauge_implementation(_gauge_implementation: address):
    """
    @notice Set gauge implementation
    @dev Set to empty(address) to prevent deployment of new gauges
    @param _gauge_implementation Address of the new token implementation
    """
    assert msg.sender == self.admin  # dev: admin-only function

    log UpdateGaugeImplementation(self.gauge_implementation, _gauge_implementation)
    self.gauge_implementation = _gauge_implementation


@external
def commit_transfer_ownership(_addr: address):
    """
    @notice Transfer ownership of this contract to `addr`
    @param _addr Address of the new owner
    """
    assert msg.sender == self.admin  # dev: admin only

    self.future_admin = _addr


@external
def accept_transfer_ownership():
    """
    @notice Accept a pending ownership transfer
    @dev Only callable by the new owner
    """
    assert msg.sender == self.future_admin  # dev: future admin only

    log TransferOwnership(self.admin, msg.sender)
    self.admin = msg.sender


# <--- Factory Getters --->


@view
@external
def find_pool_for_coins(_from: address, _to: address, i: uint256 = 0) -> address:
    """
    @notice Find an available pool for exchanging two coins
    @param _from Address of coin to be sent
    @param _to Address of coin to be received
    @param i Index value. When multiple pools are available
            this value is used to return the n'th address.
    @return Pool address
    """
    key: uint256 = convert(_from, uint256) ^ convert(_to, uint256)
    return self.markets[key][i]


# <--- Pool Getters --->


@view
@external
def get_coins(_pool: address) -> address[N_COINS]:
    """
    @notice Get the coins within a pool
    @param _pool Pool address
    @return List of coin addresses
    """
    return self.pool_data[_pool].coins


@view
@external
def get_decimals(_pool: address) -> uint256[N_COINS]:
    """
    @notice Get decimal places for each coin within a pool
    @param _pool Pool address
    @return uint256 list of decimals
    """
    return self.pool_data[_pool].decimals


@view
@external
def get_balances(_pool: address) -> uint256[N_COINS]:
    """
    @notice Get balances for each coin within a pool
    @dev For pools using lending, these are the wrapped coin balances
    @param _pool Pool address
    @return uint256 list of balances
    """
    return [
        TricryptoPool(_pool).balances(0),
        TricryptoPool(_pool).balances(1),
        TricryptoPool(_pool).balances(2),
    ]


@view
@external
def get_coin_indices(
    _pool: address,
    _from: address,
    _to: address
) -> (uint256, uint256):
    """
    @notice Convert coin addresses to indices for use with pool methods
    @param _pool Pool address
    @param _from Coin address to be used as `i` within a pool
    @param _to Coin address to be used as `j` within a pool
    @return uint256 `i`, uint256 `j`
    """
    coins: address[N_COINS] = self.pool_data[_pool].coins

    if _from == coins[0] and _to == coins[1]:
        return 0, 1
    elif _from == coins[1] and _to == coins[0]:
        return 1, 0
    else:
        raise "Coins not found"


@view
@external
def get_gauge(_pool: address) -> address:
    """
    @notice Get the address of the liquidity gauge contract for a factory pool
    @dev Returns `empty(address)` if a gauge has not been deployed
    @param _pool Pool address
    @return Implementation contract address
    """
    return self.pool_data[_pool].liquidity_gauge


@view
@external
def get_eth_index(_pool: address) -> uint256:
    """
    @notice Get the index of WETH for a pool
    @dev Returns max_value(uint256) if WETH is not a coin in the pool
    """
    for i in range(2):
        if self.pool_data[_pool].coins[i] == WETH:
            return i
    return max_value(uint256)
