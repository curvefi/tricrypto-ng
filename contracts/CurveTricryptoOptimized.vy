# @version 0.3.7

# (c) Curve.Fi, 2021
# Pool for USDT/BTC/ETH or similar

from vyper.interfaces import ERC20


# interfaces
interface ERC1271:
    def isValidSignature(_hash: bytes32, _signature: Bytes[65]) -> bytes32: view


interface Math:
    def geometric_mean(unsorted_x: uint256[N_COINS]) -> uint256: view
    def wad_exp(_power: int256) -> uint256: view
    def cbrt(x: uint256) -> uint256: view
    def reduction_coefficient(
        x: uint256[N_COINS], fee_gamma: uint256
    ) -> uint256: view
    def newton_D(
        ANN: uint256,
        gamma: uint256,
        x_unsorted: uint256[N_COINS],
        K0_prev: uint256
    ) -> uint256: view
    def get_y(
        ANN: uint256,
        gamma: uint256,
        x: uint256[N_COINS],
        D: uint256,
        i: uint256,
    ) -> uint256[2]: view

interface WETH:
    def deposit(): payable
    def withdraw(_amount: uint256): nonpayable


# Events
event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256

event TokenExchange:
    buyer: indexed(address)
    sold_id: uint256
    tokens_sold: uint256
    bought_id: uint256
    tokens_bought: uint256
    fee: uint256

event AddLiquidity:
    provider: indexed(address)
    token_amounts: uint256[N_COINS]
    fee: uint256
    token_supply: uint256

event RemoveLiquidity:
    provider: indexed(address)
    token_amounts: uint256[N_COINS]
    token_supply: uint256

event RemoveLiquidityOne:
    provider: indexed(address)
    token_amount: uint256
    coin_index: uint256
    coin_amount: uint256
    approx_fee: uint256

event CommitNewAdmin:
    deadline: indexed(uint256)
    admin: indexed(address)

event NewAdmin:
    admin: indexed(address)

event CommitNewParameters:
    deadline: indexed(uint256)
    admin_fee: uint256
    mid_fee: uint256
    out_fee: uint256
    fee_gamma: uint256
    allowed_extra_profit: uint256
    adjustment_step: uint256
    ma_time: uint256

event NewParameters:
    admin_fee: uint256
    mid_fee: uint256
    out_fee: uint256
    fee_gamma: uint256
    allowed_extra_profit: uint256
    adjustment_step: uint256
    ma_time: uint256

event RampAgamma:
    initial_A: uint256
    future_A: uint256
    initial_gamma: uint256
    future_gamma: uint256
    initial_time: uint256
    future_time: uint256

event StopRampA:
    current_A: uint256
    current_gamma: uint256
    time: uint256

event ClaimAdminFee:
    admin: indexed(address)
    tokens: uint256

event AdjustPrices:
    price_scale: uint256[N_COINS-1]


N_COINS: constant(uint256) = 3
PRECISION: constant(uint256) = 10**18  # The precision to convert to
A_MULTIPLIER: constant(uint256) = 10000

# These addresses are replaced by the deployer
math: public(constant(address)) = 0x0000000000000000000000000000000000000000
coins: constant(address[N_COINS]) = [
    0x0000000000000000000000000000000000000010,
    0x0000000000000000000000000000000000000011,
    0x0000000000000000000000000000000000000012,
]

price_scale_packed: uint256  # Internal price scale
price_oracle_packed: uint256  # Price target given by MA

last_prices_packed: uint256
last_prices_timestamp: public(uint256)

initial_A_gamma: public(uint256)
future_A_gamma: public(uint256)
initial_A_gamma_time: public(uint256)
future_A_gamma_time: public(uint256)

allowed_extra_profit: public(uint256)  # 2 * 10**12 - recommended value
future_allowed_extra_profit: public(uint256)

fee_gamma: public(uint256)
future_fee_gamma: public(uint256)

adjustment_step: public(uint256)
future_adjustment_step: public(uint256)

ma_time: public(uint256)
future_ma_time: public(uint256)

mid_fee: public(uint256)
out_fee: public(uint256)
admin_fee: public(uint256)
future_mid_fee: public(uint256)
future_out_fee: public(uint256)
future_admin_fee: public(uint256)

balances: public(uint256[N_COINS])
D: public(uint256)

owner: public(address)
future_owner: public(address)

xcp_profit: public(uint256)
xcp_profit_a: public(uint256)  # Full profit at last claim of admin fees
virtual_price: public(
    uint256
)  # Cached (fast to read) virtual price also used internally
not_adjusted: uint256

is_killed: public(bool)
kill_deadline: public(uint256)
transfer_ownership_deadline: public(uint256)
admin_actions_deadline: public(uint256)

admin_fee_receiver: public(address)

KILL_DEADLINE_DT: constant(uint256) = 2 * 30 * 86400
ADMIN_ACTIONS_DELAY: constant(uint256) = 3 * 86400
MIN_RAMP_TIME: constant(uint256) = 86400

MAX_ADMIN_FEE: constant(uint256) = 10 * 10**9
MIN_FEE: constant(uint256) = 5 * 10**5  # 0.5 bps
MAX_FEE: constant(uint256) = 10 * 10**9
MIN_A: constant(uint256) = N_COINS**N_COINS * A_MULTIPLIER / 100
MAX_A: constant(uint256) = 1000 * A_MULTIPLIER * N_COINS**N_COINS
MAX_A_CHANGE: constant(uint256) = 10
MIN_GAMMA: constant(uint256) = 10**10
MAX_GAMMA: constant(uint256) = 5 * 10**16
NOISE_FEE: constant(uint256) = 10**5  # 0.1 bps

PRICE_SIZE: constant(int128) = 256 / (N_COINS - 1)
PRICE_MASK: constant(uint256) = 2**PRICE_SIZE - 1
PRECISIONS: constant(uint256[N_COINS]) = [
    1,  # 0
    1,  # 1
    1,  # 2
]

INF_COINS: constant(uint256) = 15

# erc20 implementation vars
name: public(constant(String[64])) = "Curve.fi USDT-BTC-ETH"
symbol: public(constant(String[32])) = "crv3crypto2"
decimals: public(constant(uint8)) = 18
version: public(constant(String[8])) = "1"

balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])
totalSupply: public(uint256)
nonces: public(HashMap[address, uint256])

EIP712_TYPEHASH: constant(bytes32) = keccak256(
    "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract,bytes32 salt)"
)
EIP2612_TYPEHASH: constant(bytes32) = keccak256(
    "Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)"
)
VERSION_HASH: constant(bytes32) = keccak256(version)
NAME_HASH: constant(bytes32) = keccak256(name)
CACHED_CHAIN_ID: immutable(uint256)
salt: public(immutable(bytes32))
CACHED_DOMAIN_SEPARATOR: immutable(bytes32)


@external
def __init__(
    owner: address,
    admin_fee_receiver: address,
    A: uint256,
    gamma: uint256,
    mid_fee: uint256,
    out_fee: uint256,
    allowed_extra_profit: uint256,
    fee_gamma: uint256,
    adjustment_step: uint256,
    admin_fee: uint256,
    ma_time: uint256,
    initial_prices: uint256[N_COINS - 1],
):
    self.owner = owner

    # Pack A and gamma:
    # shifted A + gamma
    A_gamma: uint256 = shift(A, 128)
    A_gamma = A_gamma | gamma
    self.initial_A_gamma = A_gamma
    self.future_A_gamma = A_gamma

    self.mid_fee = mid_fee
    self.out_fee = out_fee
    self.allowed_extra_profit = allowed_extra_profit
    self.fee_gamma = fee_gamma
    self.adjustment_step = adjustment_step
    self.admin_fee = admin_fee

    self.not_adjusted = 1  # anything less than 2 is False

    # Packing prices
    packed_prices: uint256 = 0
    for k in range(N_COINS - 1):
        packed_prices = shift(packed_prices, PRICE_SIZE)
        p: uint256 = initial_prices[N_COINS - 2 - k]
        assert p < PRICE_MASK
        packed_prices = p | packed_prices

    self.price_scale_packed = packed_prices
    self.price_oracle_packed = packed_prices
    self.last_prices_packed = packed_prices
    self.last_prices_timestamp = block.timestamp
    self.ma_time = ma_time
    self.xcp_profit_a = 10**18
    self.kill_deadline = block.timestamp + KILL_DEADLINE_DT
    self.admin_fee_receiver = admin_fee_receiver

    CACHED_CHAIN_ID = chain.id
    salt = block.prevhash
    CACHED_DOMAIN_SEPARATOR = keccak256(
        _abi_encode(
            EIP712_TYPEHASH,
            NAME_HASH,
            VERSION_HASH,
            chain.id,
            self,
            salt,
        )
    )

    # fire empty transfer for indexers
    log Transfer(empty(address), self, 0)


@payable
@external
def __default__():
    pass


# --- erc20 ---

@internal
def _approve(_owner: address, _spender: address, _value: uint256):
    self.allowance[_owner][_spender] = _value

    log Approval(_owner, _spender, _value)


@internal
def _transfer(_from: address, _to: address, _value: uint256):
    assert _to not in [self, empty(address)]

    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value

    log Transfer(_from, _to, _value)


@view
@internal
def _domain_separator() -> bytes32:
    if chain.id != CACHED_CHAIN_ID:
        return keccak256(
            _abi_encode(
                EIP712_TYPEHASH,
                NAME_HASH,
                VERSION_HASH,
                chain.id,
                self,
                salt,
            )
        )
    return CACHED_DOMAIN_SEPARATOR


@external
def transferFrom(_from: address, _to: address, _value: uint256) -> bool:
    """
    @dev Transfer tokens from one address to another.
    @param _from address The address which you want to send tokens from
    @param _to address The address which you want to transfer to
    @param _value uint256 the amount of tokens to be transferred
    """
    _allowance: uint256 = self.allowance[_from][msg.sender]
    if _allowance != max_value(uint256):
        self._approve(_from, msg.sender, _allowance - _value)

    self._transfer(_from, _to, _value)
    return True


@external
def transfer(_to: address, _value: uint256) -> bool:
    """
    @dev Transfer token for a specified address
    @param _to The address to transfer to.
    @param _value The amount to be transferred.
    """
    self._transfer(msg.sender, _to, _value)
    return True


@external
def approve(_spender: address, _value: uint256) -> bool:
    """
    @notice Allow `_spender` to transfer up to `_value` amount
            of tokens from the caller's account.
    @dev Non-zero to non-zero approvals are allowed, but should
         be used cautiously. The methods increaseAllowance + decreaseAllowance
         are available to prevent any front-running that may occur.
    @param _spender The account permitted to spend up to `_value` amount of
                    caller's funds.
    @param _value The amount of tokens `_spender` is allowed to spend.
    @return bool success
    """
    self._approve(msg.sender, _spender, _value)
    return True


@external
def increaseAllowance(_spender: address, _add_value: uint256) -> bool:
    """
    @notice Increase the allowance granted to `_spender`.
    @dev This function will never overflow, and instead will bound
         allowance to MAX_UINT256. This has the potential to grant an
         infinite approval.
    @param _spender The account to increase the allowance of.
    @param _add_value The amount to increase the allowance by.
    """
    cached_allowance: uint256 = self.allowance[msg.sender][_spender]
    allowance: uint256 = unsafe_add(cached_allowance, _add_value)

    # check for an overflow
    if allowance < cached_allowance:
        allowance = max_value(uint256)

    if allowance != cached_allowance:
        self._approve(msg.sender, _spender, allowance)

    return True


@external
def decreaseAllowance(_spender: address, _sub_value: uint256) -> bool:
    """
    @notice Decrease the allowance granted to `_spender`.
    @dev This function will never underflow, and instead will bound
        allowance to 0.
    @param _spender The account to decrease the allowance of.
    @param _sub_value The amount to decrease the allowance by.
    """
    cached_allowance: uint256 = self.allowance[msg.sender][_spender]
    allowance: uint256 = unsafe_sub(cached_allowance, _sub_value)

    # check for an underflow
    if cached_allowance < allowance:
        allowance = 0

    if allowance != cached_allowance:
        self._approve(msg.sender, _spender, allowance)

    return True


@external
def permit(
    _owner: address,
    _spender: address,
    _value: uint256,
    _deadline: uint256,
    _v: uint8,
    _r: bytes32,
    _s: bytes32,
) -> bool:
    """
    @notice Permit `_spender` to spend up to `_value` amount of `_owner`'s
            tokens via a signature.
    @dev In the event of a chain fork, replay attacks are prevented as
         domain separator is recalculated. However, this is only if the
         resulting chains update their chainId.
    @param _owner The account which generated the signature and is granting an
                  allowance.
    @param _spender The account which will be granted an allowance.
    @param _value The approval amount.
    @param _deadline The deadline by which the signature must be submitted.
    @param _v The last byte of the ECDSA signature.
    @param _r The first 32 bytes of the ECDSA signature.
    @param _s The second 32 bytes of the ECDSA signature.
    """
    assert _owner != empty(address), "dev: invalid owner"
    assert block.timestamp <= _deadline, "dev: permit expired"

    nonce: uint256 = self.nonces[_owner]
    digest: bytes32 = keccak256(
        concat(
            b"\x19\x01",
            self._domain_separator(),
            keccak256(
                _abi_encode(
                    EIP2612_TYPEHASH, _owner, _spender, _value, nonce, _deadline
                )
            ),
        )
    )
    assert ecrecover(digest, _v, _r, _s) == _owner, "dev: invalid signature"

    self.nonces[_owner] = nonce + 1
    self._approve(_owner, _spender, _value)
    return True


@internal
def mint(_to: address, _value: uint256) -> bool:
    """
    @dev Mint an amount of the token and assigns it to an account.
         This encapsulates the modification of balances such that the
         proper events are emitted.
    @param _to The account that will receive the created tokens.
    @param _value The amount that will be created.
    """
    self.totalSupply += _value
    self.balanceOf[_to] += _value

    log Transfer(empty(address), _to, _value)
    return True


@internal
def mint_relative(_to: address, frac: uint256) -> uint256:
    """
    @dev Increases supply by factor of (1 + frac/1e18) and mints it for _to
    """
    supply: uint256 = self.totalSupply
    d_supply: uint256 = supply * frac / 10**18
    if d_supply > 0:
        self.totalSupply = supply + d_supply
        self.balanceOf[_to] += d_supply
        log Transfer(empty(address), _to, d_supply)

    return d_supply


@internal
def burnFrom(_to: address, _value: uint256) -> bool:
    """
    @dev Burn an amount of the token from a given account.
    @param _to The account whose tokens will be burned.
    @param _value The amount that will be burned.
    """
    self.totalSupply -= _value
    self.balanceOf[_to] -= _value

    log Transfer(_to, empty(address), _value)
    return True

# ---------------------------- AMM Functions ---------------------------------


@internal
@view
def _packed_view(k: uint256, p: uint256) -> uint256:
    assert k < N_COINS - 1
    return shift(p, -PRICE_SIZE * convert(k, int256)) & PRICE_MASK


@external
@view
@nonreentrant("lock")
def price_oracle(k: uint256) -> uint256:
    price_oracle: uint256 = self._packed_view(k, self.price_oracle_packed)
    last_prices_timestamp: uint256 = self.last_prices_timestamp

    if last_prices_timestamp < block.timestamp:
        last_prices: uint256 = self._packed_view(k, self.last_prices_packed)
        ma_time: uint256 = self.ma_time
        alpha: uint256 = Math(math).wad_exp(
            -convert(
                (block.timestamp - last_prices_timestamp) * 10**18 / ma_time,
                int256,
            )
        )
        return (
            last_prices * (10**18 - alpha) + price_oracle * alpha
        ) / 10**18

    return price_oracle


@external
@view
def price_scale(k: uint256) -> uint256:
    return self._packed_view(k, self.price_scale_packed)


@external
@view
@nonreentrant("lock")
def lp_price() -> uint256:
    price_oracle: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
    packed_prices: uint256 = self.price_oracle_packed
    for k in range(N_COINS - 1):
        price_oracle[k] = packed_prices & PRICE_MASK
        packed_prices = shift(packed_prices, -PRICE_SIZE)
    return (
        3 * self.virtual_price *
        Math(math).cbrt(price_oracle[0] * price_oracle[1]) / 10**18
    )


@external
@view
def last_prices(k: uint256) -> uint256:
    return self._packed_view(k, self.last_prices_packed)


@external
@view
def coins(i: uint256) -> address:
    _coins: address[N_COINS] = coins
    return _coins[i]


@internal
@view
def xp() -> uint256[N_COINS]:
    result: uint256[N_COINS] = self.balances
    packed_prices: uint256 = self.price_scale_packed

    precisions: uint256[N_COINS] = PRECISIONS

    result[0] *= PRECISIONS[0]
    for i in range(1, N_COINS):
        p: uint256 = (packed_prices & PRICE_MASK) * precisions[i]
        result[i] = result[i] * p / PRECISION
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    return result


@view
@internal
def _A_gamma() -> uint256[2]:
    t1: uint256 = self.future_A_gamma_time

    A_gamma_1: uint256 = self.future_A_gamma
    gamma1: uint256 = A_gamma_1 & 2**128 - 1
    A1: uint256 = shift(A_gamma_1, -128)

    if block.timestamp < t1:

        # handle ramping up and down of A
        A_gamma_0: uint256 = self.initial_A_gamma
        t0: uint256 = self.initial_A_gamma_time

        t1 -= t0
        t0 = block.timestamp - t0
        t2: uint256 = t1 - t0

        A1 = (shift(A_gamma_0, -128) * t2 + A1 * t0) / t1
        gamma1 = ((A_gamma_0 & 2**128 - 1) * t2 + gamma1 * t0) / t1

    return [A1, gamma1]


@view
@external
def A() -> uint256:
    return self._A_gamma()[0]


@view
@external
def gamma() -> uint256:
    return self._A_gamma()[1]


@internal
@view
def _fee(xp: uint256[N_COINS]) -> uint256:
    f: uint256 = Math(math).reduction_coefficient(xp, self.fee_gamma)
    return (self.mid_fee * f + self.out_fee * (10**18 - f)) / 10**18


@external
@view
def fee() -> uint256:
    return self._fee(self.xp())


@external
@view
def fee_calc(xp: uint256[N_COINS]) -> uint256:
    return self._fee(xp)


@internal
@view
def get_xcp(D: uint256) -> uint256:
    x: uint256[N_COINS] = empty(uint256[N_COINS])
    x[0] = D / N_COINS
    packed_prices: uint256 = self.price_scale_packed
    # No precisions here because we don't switch to "real" units

    for i in range(1, N_COINS):
        x[i] = D * 10**18 / (N_COINS * (packed_prices & PRICE_MASK))
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    return Math(math).geometric_mean(x)


@external
@view
@nonreentrant("lock")
def get_virtual_price() -> uint256:
    return 10**18 * self.get_xcp(self.D) / self.totalSupply


@internal
def _claim_admin_fees():
    A_gamma: uint256[2] = self._A_gamma()

    xcp_profit: uint256 = self.xcp_profit
    xcp_profit_a: uint256 = self.xcp_profit_a

    # Gulp here
    _coins: address[N_COINS] = coins
    for i in range(N_COINS):
        self.balances[i] = ERC20(_coins[i]).balanceOf(self)

    vprice: uint256 = self.virtual_price

    if xcp_profit > xcp_profit_a:
        fees: uint256 = (
            (xcp_profit - xcp_profit_a) * self.admin_fee / (2 * 10**10)
        )
        if fees > 0:
            receiver: address = self.admin_fee_receiver
            if receiver != empty(address):
                frac: uint256 = vprice * 10**18 / (vprice - fees) - 10**18
                claimed: uint256 = self.mint_relative(receiver, frac)
                xcp_profit -= fees * 2
                self.xcp_profit = xcp_profit
                log ClaimAdminFee(receiver, claimed)

    total_supply: uint256 = self.totalSupply

    # Recalculate D b/c we gulped
    D: uint256 = Math(math).newton_D(A_gamma[0], A_gamma[1], self.xp(), 0)
    self.D = D

    self.virtual_price = 10**18 * self.get_xcp(D) / total_supply

    if xcp_profit > xcp_profit_a:
        self.xcp_profit_a = xcp_profit


@internal
def tweak_price(
    A_gamma: uint256[2],
    _xp: uint256[N_COINS],
    i: uint256,
    p_i: uint256,
    new_D: uint256,
    K0_prev: uint256 = 0
):
    price_oracle: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
    last_prices: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
    price_scale: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    p_new: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])

    # ------------- Get internal oracle and last prices ----------------------

    packed_prices: uint256 = self.price_oracle_packed
    for k in range(N_COINS - 1):
        price_oracle[k] = packed_prices & PRICE_MASK
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    last_prices_timestamp: uint256 = self.last_prices_timestamp
    packed_prices = self.last_prices_packed  # reuse `packed_prices`
    for k in range(N_COINS - 1):
        last_prices[k] = packed_prices & PRICE_MASK
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    # ----------------------- Update MA if needed ----------------------------

    if last_prices_timestamp < block.timestamp:
        # update moving average:
        ma_time: uint256 = self.ma_time
        alpha: uint256 = Math(math).wad_exp(
            -convert(
                (block.timestamp - last_prices_timestamp) * 10**18 / ma_time,
                int256,
            )
        )
        packed_prices = 0
        for k in range(N_COINS - 1):
            price_oracle[k] = (
                last_prices[k] * (10**18 - alpha) + price_oracle[k] * alpha
            ) / 10**18

        for k in range(N_COINS - 1):
            packed_prices = shift(packed_prices, PRICE_SIZE)
            p: uint256 = price_oracle[N_COINS - 2 - k]
            assert p < PRICE_MASK
            packed_prices = p | packed_prices
        self.price_oracle_packed = packed_prices
        self.last_prices_timestamp = block.timestamp

    # ------------------------------------------------------------------------

    D_unadjusted: uint256 = new_D  # Withdrawal methods know new D already
    if new_D == 0:
        D_unadjusted = Math(math).newton_D(A_gamma[0], A_gamma[1], _xp, K0_prev)

    packed_prices = self.price_scale_packed
    for k in range(N_COINS - 1):
        price_scale[k] = packed_prices & PRICE_MASK
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    if p_i > 0:

        # Save the last price
        if i > 0:
            last_prices[i - 1] = p_i
        else:
            # If 0th price changed - change all prices instead
            for k in range(N_COINS - 1):
                last_prices[k] = last_prices[k] * 10**18 / p_i
    else:

        # ------------------------ Calculate real prices ---------------------
        __xp: uint256[N_COINS] = _xp
        dx_price: uint256 = __xp[0] / 10**6
        __xp[0] += dx_price
        y_out: uint256[2] = empty(uint256[2])
        for k in range(N_COINS - 1):
            y_out = Math(math).get_y(A_gamma[0], A_gamma[1], __xp, D_unadjusted, k + 1)
            last_prices[k] = price_scale[k] * dx_price / (_xp[k + 1] - y_out[0])

    packed_prices = 0
    for k in range(N_COINS - 1):
        packed_prices = shift(packed_prices, PRICE_SIZE)
        p: uint256 = last_prices[N_COINS - 2 - k]
        assert p < PRICE_MASK
        packed_prices = p | packed_prices
    self.last_prices_packed = packed_prices

    total_supply: uint256 = self.totalSupply
    old_xcp_profit: uint256 = self.xcp_profit
    old_virtual_price: uint256 = self.virtual_price

    # ------- Update profit numbers without price adjustment first -----------
    xp[0] = D_unadjusted / N_COINS
    for k in range(N_COINS - 1):
        xp[k + 1] = D_unadjusted * 10**18 / (N_COINS * price_scale[k])
    xcp_profit: uint256 = 10**18
    virtual_price: uint256 = 10**18

    if old_virtual_price > 0:
        xcp: uint256 = Math(math).geometric_mean(xp)
        virtual_price = 10**18 * xcp / total_supply
        xcp_profit = old_xcp_profit * virtual_price / old_virtual_price

        t: uint256 = self.future_A_gamma_time
        if virtual_price < old_virtual_price and t == 0:
            raise "Loss"
        if t == 1:
            self.future_A_gamma_time = 0

    self.xcp_profit = xcp_profit
    needs_adjustment: uint256 = self.not_adjusted

    # ------- Check if there are enough profits to rebalance liquidity -------
    if (
        needs_adjustment < 2
        and virtual_price * 2 - 10**18
        > xcp_profit + 2 * self.allowed_extra_profit
    ):
        needs_adjustment = 3
        self.not_adjusted = 3  # 3 means True (saves gas over bools)

    if needs_adjustment == 3:

        # ------------------- Get adjustment step ----------------------------
        norm: uint256 = 0
        for k in range(N_COINS - 1):
            ratio: uint256 = price_oracle[k] * 10**18 / price_scale[k]
            if ratio > 10**18:
                ratio -= 10**18
            else:
                ratio = 10**18 - ratio
            norm += ratio**2

        norm = isqrt(norm)
        adjustment_step: uint256 = max(self.adjustment_step, norm / 10)

        if norm > adjustment_step and old_virtual_price > 0:

            # -------------- Calculate new price scale -----------------------
            for k in range(N_COINS - 1):
                p_new[k] = (
                    price_scale[k] * (norm - adjustment_step)
                    + adjustment_step * price_oracle[k]
                ) / norm

            xp = _xp
            for k in range(N_COINS - 1):
                xp[k + 1] = _xp[k + 1] * p_new[k] / price_scale[k]

            # check: K0_prev be used here?
            D: uint256 = Math(math).newton_D(A_gamma[0], A_gamma[1], xp, K0_prev)
            xp[0] = D / N_COINS
            for k in range(N_COINS - 1):
                xp[k + 1] = D * 10**18 / (N_COINS * p_new[k])

            # reuse old_virtual_price
            old_virtual_price = (
                10**18 * Math(math).geometric_mean(xp) / total_supply
            )

            # --------- Proceed if we've got enough profit -------------------
            if (
                old_virtual_price > 10**18 and
                2 * old_virtual_price - 10**18 > xcp_profit
            ):
                packed_prices = 0
                for k in range(N_COINS - 1):
                    packed_prices = shift(packed_prices, PRICE_SIZE)
                    p: uint256 = p_new[N_COINS - 2 - k]
                    assert p < PRICE_MASK
                    packed_prices = p | packed_prices

                self.price_scale_packed = packed_prices
                self.D = D
                self.virtual_price = old_virtual_price

                log AdjustPrices(p_new)

                return

            else:
                self.not_adjusted = 1  # anything less than 2 is (False).

    # If we are here, the price_scale adjustment did not happen
    # Still need to update the profit counter and D
    self.D = D_unadjusted
    self.virtual_price = virtual_price


@payable
@external
@nonreentrant("lock")
def exchange(
    i: uint256, j: uint256, dx: uint256, min_dy: uint256, use_eth: bool = False
) -> uint256:
    assert not self.is_killed  # dev: the pool is killed
    assert i != j  # dev: coin index out of range
    assert i < N_COINS  # dev: coin index out of range
    assert j < N_COINS  # dev: coin index out of range
    assert dx > 0  # dev: do not exchange 0 coins

    A_gamma: uint256[2] = self._A_gamma()
    xp: uint256[N_COINS] = self.balances
    ix: uint256 = j
    p: uint256 = 0
    dy: uint256 = 0

    _coins: address[N_COINS] = coins
    if i == 2 and use_eth:
        assert msg.value == dx  # dev: incorrect eth amount
        WETH(coins[2]).deposit(value=msg.value)
    else:
        assert msg.value == 0  # dev: nonzero eth amount
        # assert might be needed for some tokens - removed one to save bytespace
        ERC20(_coins[i]).transferFrom(msg.sender, self, dx)

    y: uint256 = xp[j]
    x0: uint256 = xp[i]
    xp[i] = x0 + dx
    self.balances[i] = xp[i]

    price_scale: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
    packed_prices: uint256 = self.price_scale_packed
    for k in range(N_COINS - 1):
        price_scale[k] = packed_prices & PRICE_MASK
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    precisions: uint256[N_COINS] = PRECISIONS
    xp[0] *= PRECISIONS[0]
    for k in range(1, N_COINS):
        xp[k] = xp[k] * price_scale[k - 1] * precisions[k] / PRECISION

    prec_i: uint256 = precisions[i]

    # Update invariant if parameter are undergoing ramps:
    t: uint256 = self.future_A_gamma_time
    if t > 0:
        x0 *= prec_i
        if i > 0:
            x0 = x0 * price_scale[i - 1] / PRECISION
        x1: uint256 = xp[i]  # Back up old value in xp
        xp[i] = x0
        self.D = Math(math).newton_D(A_gamma[0], A_gamma[1], xp, 0)
        xp[i] = x1  # And restore
        if block.timestamp >= t:
            self.future_A_gamma_time = 1

    prec_j: uint256 = precisions[j]
    y_out: uint256[2] = Math(math).get_y(A_gamma[0], A_gamma[1], xp, self.D, j)
    dy = xp[j] - y_out[0]

    # Not defining new "y" here to have less variables / make subsequent calls cheaper
    xp[j] -= dy
    dy -= 1

    if j > 0:
        dy = dy * PRECISION / price_scale[j - 1]
    dy /= prec_j

    fee: uint256 = self._fee(xp) * dy / 10**10

    dy -= fee
    assert dy >= min_dy, "Slippage"
    y -= dy

    self.balances[j] = y
    # assert might be needed for some tokens - removed one to save bytespace
    if j == 2 and use_eth:
        WETH(coins[2]).withdraw(dy)
        raw_call(msg.sender, b"", value=dy)
    else:
        ERC20(_coins[j]).transfer(msg.sender, dy)

    y *= prec_j
    if j > 0:
        y = y * price_scale[j - 1] / PRECISION
    xp[j] = y

    # Calculate price
    if dx > 10**5 and dy > 10**5:
        _dx: uint256 = dx * prec_i
        _dy: uint256 = dy * prec_j
        if i != 0 and j != 0:
            p = (
                (
                    shift(
                        self.last_prices_packed,
                        -PRICE_SIZE * convert(i - 1, int256)
                    )
                    & PRICE_MASK
                )
                * _dx
                / _dy
            )
        elif i == 0:
            p = _dx * 10**18 / _dy
        else:  # j == 0
            p = _dy * 10**18 / _dx
            ix = i

    # tweak price with good initial guess:
    self.tweak_price(A_gamma, xp, ix, p, 0, y_out[1])

    log TokenExchange(msg.sender, i, dx, j, dy, fee)

    return dy


@view
@internal
def _calc_token_fee(amounts: uint256[N_COINS], xp: uint256[N_COINS]) -> uint256:
    # fee = sum(amounts_i - avg(amounts)) * fee' / sum(amounts)
    fee: uint256 = self._fee(xp) * N_COINS / (4 * (N_COINS - 1))
    S: uint256 = 0
    for _x in amounts:
        S += _x
    avg: uint256 = S / N_COINS
    Sdiff: uint256 = 0
    for _x in amounts:
        if _x > avg:
            Sdiff += _x - avg
        else:
            Sdiff += avg - _x
    return fee * Sdiff / S + NOISE_FEE


@external
@view
def calc_token_fee(amounts: uint256[N_COINS], xp: uint256[N_COINS]) -> uint256:
    return self._calc_token_fee(amounts, xp)


@external
@nonreentrant("lock")
def add_liquidity(amounts: uint256[N_COINS], min_mint_amount: uint256):
    assert not self.is_killed  # dev: the pool is killed

    A_gamma: uint256[2] = self._A_gamma()

    _coins: address[N_COINS] = coins

    xp: uint256[N_COINS] = self.balances
    amountsp: uint256[N_COINS] = empty(uint256[N_COINS])
    xx: uint256[N_COINS] = empty(uint256[N_COINS])
    d_token: uint256 = 0
    d_token_fee: uint256 = 0
    old_D: uint256 = 0
    ix: uint256 = INF_COINS

    xp_old: uint256[N_COINS] = xp
    for i in range(N_COINS):
        bal: uint256 = xp[i] + amounts[i]
        xp[i] = bal
        self.balances[i] = bal
    xx = xp

    precisions: uint256[N_COINS] = PRECISIONS
    packed_prices: uint256 = self.price_scale_packed
    xp[0] *= PRECISIONS[0]
    xp_old[0] *= PRECISIONS[0]
    for i in range(1, N_COINS):
        price_scale: uint256 = (packed_prices & PRICE_MASK) * precisions[i]
        xp[i] = xp[i] * price_scale / PRECISION
        xp_old[i] = xp_old[i] * price_scale / PRECISION
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    for i in range(N_COINS):
        if amounts[i] > 0:
            # assert might be needed for some tokens - removed one to save bytespace
            ERC20(_coins[i]).transferFrom(msg.sender, self, amounts[i])
            amountsp[i] = xp[i] - xp_old[i]
            if ix == INF_COINS:
                ix = i
            else:
                ix = INF_COINS - 1
    assert ix != INF_COINS  # dev: no coins to add

    t: uint256 = self.future_A_gamma_time
    if t > 0:
        old_D = Math(math).newton_D(A_gamma[0], A_gamma[1], xp_old, 0)
        if block.timestamp >= t:
            self.future_A_gamma_time = 1
    else:
        old_D = self.D

    D: uint256 = Math(math).newton_D(A_gamma[0], A_gamma[1], xp, 0)

    token_supply: uint256 = self.totalSupply
    if old_D > 0:
        d_token = token_supply * D / old_D - token_supply
    else:
        d_token = self.get_xcp(D)  # making initial virtual price equal to 1
    assert d_token > 0  # dev: nothing minted

    if old_D > 0:

        d_token_fee = (
            self._calc_token_fee(amountsp, xp) * d_token / 10**10 + 1
        )

        d_token -= d_token_fee
        token_supply += d_token
        self.mint(msg.sender, d_token)

        # Calculate price
        # p_i * (dx_i - dtoken / token_supply * xx_i) = sum{k!=i}(p_k * (dtoken / token_supply * xx_k - dx_k))
        # Only ix is nonzero
        p: uint256 = 0
        if d_token > 10**5:

            if ix < N_COINS:

                S: uint256 = 0

                last_prices: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
                packed_prices = self.last_prices_packed
                for k in range(N_COINS - 1):
                    last_prices[k] = packed_prices & PRICE_MASK
                    packed_prices = shift(packed_prices, -PRICE_SIZE)

                for i in range(N_COINS):
                    if i != ix:
                        if i == 0:
                            S += xx[0] * PRECISIONS[0]
                        else:
                            S += (
                                xx[i]
                                * last_prices[i - 1]
                                * precisions[i]
                                / PRECISION
                            )
                S = S * d_token / token_supply
                p = (
                    S
                    * PRECISION
                    / (
                        amounts[ix] * precisions[ix]
                        - d_token * xx[ix] * precisions[ix] / token_supply
                    )
                )

        self.tweak_price(A_gamma, xp, ix, p, D)

    else:

        self.D = D
        self.virtual_price = 10**18
        self.xcp_profit = 10**18
        self.mint(msg.sender, d_token)

    assert d_token >= min_mint_amount, "Slippage"

    log AddLiquidity(msg.sender, amounts, d_token_fee, token_supply)


@external
@nonreentrant("lock")
def remove_liquidity(_amount: uint256, min_amounts: uint256[N_COINS]):
    """
    This withdrawal method is very safe, does no complex math
    """
    _coins: address[N_COINS] = coins
    total_supply: uint256 = self.totalSupply
    self.burnFrom(msg.sender, _amount)
    balances: uint256[N_COINS] = self.balances
    amount: uint256 = (
        _amount - 1
    )  # Make rounding errors favoring other LPs a tiny bit

    for i in range(N_COINS):
        d_balance: uint256 = balances[i] * amount / total_supply
        assert d_balance >= min_amounts[i]
        self.balances[i] = balances[i] - d_balance
        balances[i] = d_balance  # now it's the amounts going out
        # assert might be needed for some tokens - removed one to save bytespace
        ERC20(_coins[i]).transfer(msg.sender, d_balance)

    D: uint256 = self.D
    self.D = D - D * amount / total_supply

    log RemoveLiquidity(msg.sender, balances, total_supply - _amount)


@internal
@view
def _calc_withdraw_one_coin(
    A_gamma: uint256[2],
    token_amount: uint256,
    i: uint256,
    update_D: bool,
    calc_price: bool,
) -> (uint256, uint256, uint256, uint256[N_COINS], uint256, uint256):
    token_supply: uint256 = self.totalSupply
    assert token_amount <= token_supply  # dev: token amount more than supply
    assert i < N_COINS  # dev: coin out of range

    xx: uint256[N_COINS] = self.balances
    xp: uint256[N_COINS] = PRECISIONS
    D0: uint256 = 0

    price_scale_i: uint256 = PRECISION * PRECISIONS[0]
    packed_prices: uint256 = self.price_scale_packed
    xp[0] *= xx[0]
    for k in range(1, N_COINS):
        p: uint256 = (packed_prices & PRICE_MASK)
        if i == k:
            price_scale_i = p * xp[i]
        xp[k] = xp[k] * xx[k] * p / PRECISION
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    if update_D:
        D0 = Math(math).newton_D(A_gamma[0], A_gamma[1], xp, 0)
    else:
        D0 = self.D

    D: uint256 = D0

    # -------------------------------- Fee Calc ------------------------------
    # Charge the fee on D, not on y, e.g. reducing invariant LESS than charging the user
    fee: uint256 = self._fee(xp)
    dD: uint256 = token_amount * D / token_supply

    # approx fee (assuming balanced state) in ith token is:
    D_fee: uint256 = fee * dD / (2 * 10**10) + 1
    approx_fee: uint256 = N_COINS * D_fee * xx[i] / D

    # D = D - D_fee
    D -= (dD - D_fee)

    # ------------------------------------------------------------------------

    # calculate y_out with (D - D_fee)
    y_out: uint256[2] = Math(math).get_y(A_gamma[0], A_gamma[1], xp, D, i)
    dy: uint256 = (xp[i] - y_out[0]) * PRECISION / price_scale_i
    xp[i] = y_out[0]

    # --------------------------------- Price calc ---------------------------
    p: uint256 = 0
    if calc_price and dy > 10**5 and token_amount > 10**5:

        # p_i = dD / D0 * sum'(p_k * x_k) / (dy - dD / D0 * y0)
        S: uint256 = 0
        precisions: uint256[N_COINS] = PRECISIONS
        last_prices: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])

        packed_prices = self.last_prices_packed
        for k in range(N_COINS - 1):
            last_prices[k] = packed_prices & PRICE_MASK
            packed_prices = shift(packed_prices, -PRICE_SIZE)

        for k in range(N_COINS):
            if k != i:
                if k == 0:
                    S += xx[0] * PRECISIONS[0]
                else:
                    S += xx[k] * last_prices[k - 1] * precisions[k] / PRECISION

        S = S * dD / D0
        p = (
            S
            * PRECISION
            / (dy * precisions[i] - dD * xx[i] * precisions[i] / D0)
        )

    return dy, p, D, xp, y_out[1], approx_fee


@view
@external
def calc_withdraw_one_coin(token_amount: uint256, i: uint256) -> uint256:
    """
    @notice Calculates output tokens with fee
    @param token_amount LP Token amount to burn
    @param i token in which liquidity is withdrawn
    @returns Num received ith tokens
    """

    return self._calc_withdraw_one_coin(
        self._A_gamma(), token_amount, i, True, False
    )[0]


@external
@nonreentrant("lock")
def remove_liquidity_one_coin(
    token_amount: uint256, i: uint256, min_amount: uint256
):
    assert not self.is_killed  # dev: the pool is killed

    A_gamma: uint256[2] = self._A_gamma()

    dy: uint256 = 0
    D: uint256 = 0
    p: uint256 = 0
    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    K0_prev: uint256 = 0
    approx_fee: uint256 = 0

    # ---------------------------------------------------------
    # TODO: Check the if statement in this section

    future_A_gamma_time: uint256 = self.future_A_gamma_time
    dy, p, D, xp, K0_prev, approx_fee = self._calc_withdraw_one_coin(
        A_gamma, token_amount, i, (future_A_gamma_time > 0), True
    )
    assert dy >= min_amount, "Slippage"

    if block.timestamp >= future_A_gamma_time and future_A_gamma_time > 1:
        self.future_A_gamma_time = 1  # consumes 20k gas!
    # ---------------------------------------------------------

    self.balances[i] -= dy
    self.burnFrom(msg.sender, token_amount)
    _coins: address[N_COINS] = coins
    # assert might be needed for some tokens - removed one to save bytespace
    ERC20(_coins[i]).transfer(msg.sender, dy)

    self.tweak_price(A_gamma, xp, i, p, D, K0_prev)

    log RemoveLiquidityOne(msg.sender, token_amount, i, dy, approx_fee)


@external
@nonreentrant("lock")
def claim_admin_fees():
    self._claim_admin_fees()


# Admin parameters
@external
def ramp_A_gamma(
    future_A: uint256, future_gamma: uint256, future_time: uint256
):
    assert msg.sender == self.owner  # dev: only owner
    assert block.timestamp > self.initial_A_gamma_time + (MIN_RAMP_TIME - 1)
    assert future_time > block.timestamp + MIN_RAMP_TIME - 1  # dev: insufficient time

    A_gamma: uint256[2] = self._A_gamma()
    initial_A_gamma: uint256 = shift(A_gamma[0], 128)
    initial_A_gamma = initial_A_gamma | A_gamma[1]

    assert future_A > MIN_A - 1
    assert future_A < MAX_A + 1
    assert future_gamma > MIN_GAMMA - 1
    assert future_gamma < MAX_GAMMA + 1

    ratio: uint256 = 10**18 * future_A / A_gamma[0]
    assert ratio < 10**18 * MAX_A_CHANGE + 1
    assert ratio > 10**18 / MAX_A_CHANGE - 1

    ratio = 10**18 * future_gamma / A_gamma[1]
    assert ratio < 10**18 * MAX_A_CHANGE + 1
    assert ratio > 10**18 / MAX_A_CHANGE - 1

    self.initial_A_gamma = initial_A_gamma
    self.initial_A_gamma_time = block.timestamp

    future_A_gamma: uint256 = shift(future_A, 128)
    future_A_gamma = future_A_gamma | future_gamma
    self.future_A_gamma_time = future_time
    self.future_A_gamma = future_A_gamma

    log RampAgamma(
        A_gamma[0],
        future_A,
        A_gamma[1],
        future_gamma,
        block.timestamp,
        future_time,
    )


@external
def stop_ramp_A_gamma():
    assert msg.sender == self.owner  # dev: only owner

    A_gamma: uint256[2] = self._A_gamma()
    current_A_gamma: uint256 = shift(A_gamma[0], 128)
    current_A_gamma = current_A_gamma | A_gamma[1]
    self.initial_A_gamma = current_A_gamma
    self.future_A_gamma = current_A_gamma
    self.initial_A_gamma_time = block.timestamp
    self.future_A_gamma_time = block.timestamp
    # now (block.timestamp < t1) is always False, so we return saved A

    log StopRampA(A_gamma[0], A_gamma[1], block.timestamp)


@external
def commit_new_parameters(
    _new_mid_fee: uint256,
    _new_out_fee: uint256,
    _new_admin_fee: uint256,
    _new_fee_gamma: uint256,
    _new_allowed_extra_profit: uint256,
    _new_adjustment_step: uint256,
    _new_ma_time: uint256,
):
    assert msg.sender == self.owner  # dev: only owner
    assert self.admin_actions_deadline == 0  # dev: active action

    new_mid_fee: uint256 = _new_mid_fee
    new_out_fee: uint256 = _new_out_fee
    new_admin_fee: uint256 = _new_admin_fee
    new_fee_gamma: uint256 = _new_fee_gamma
    new_allowed_extra_profit: uint256 = _new_allowed_extra_profit
    new_adjustment_step: uint256 = _new_adjustment_step
    new_ma_time: uint256 = _new_ma_time

    # Fees
    if new_out_fee < MAX_FEE + 1:
        assert new_out_fee > MIN_FEE - 1  # dev: fee is out of range
    else:
        new_out_fee = self.out_fee
    if new_mid_fee > MAX_FEE:
        new_mid_fee = self.mid_fee
    assert new_mid_fee <= new_out_fee  # dev: mid-fee is too high
    if new_admin_fee > MAX_ADMIN_FEE:
        new_admin_fee = self.admin_fee

    if new_fee_gamma < 10**18:
        assert new_fee_gamma > 0  # dev: fee_gamma out of range [1 .. 10**18]
    else:
        new_fee_gamma = self.fee_gamma
    if new_allowed_extra_profit > 10**18:
        new_allowed_extra_profit = self.allowed_extra_profit
    if new_adjustment_step > 10**18:
        new_adjustment_step = self.adjustment_step

    if new_ma_time < 872542:  # 7 * 24 * 60 * 60 / ln(2)
        assert new_ma_time > 0  # dev: MA time should be longer than 1 second
    else:
        new_ma_time = self.ma_time

    _deadline: uint256 = block.timestamp + ADMIN_ACTIONS_DELAY
    self.admin_actions_deadline = _deadline

    self.future_admin_fee = new_admin_fee
    self.future_mid_fee = new_mid_fee
    self.future_out_fee = new_out_fee
    self.future_fee_gamma = new_fee_gamma
    self.future_allowed_extra_profit = new_allowed_extra_profit
    self.future_adjustment_step = new_adjustment_step
    self.future_ma_time = new_ma_time

    log CommitNewParameters(
        _deadline,
        new_admin_fee,
        new_mid_fee,
        new_out_fee,
        new_fee_gamma,
        new_allowed_extra_profit,
        new_adjustment_step,
        new_ma_time,
    )


@external
@nonreentrant("lock")
def apply_new_parameters():
    assert msg.sender == self.owner  #dev: only owner
    assert block.timestamp >= self.admin_actions_deadline  #dev: insufficient time
    assert self.admin_actions_deadline != 0  #dev: no active action

    self.admin_actions_deadline = 0

    admin_fee: uint256 = self.future_admin_fee
    if self.admin_fee != admin_fee:
        self._claim_admin_fees()
        self.admin_fee = admin_fee

    mid_fee: uint256 = self.future_mid_fee
    self.mid_fee = mid_fee
    out_fee: uint256 = self.future_out_fee
    self.out_fee = out_fee
    fee_gamma: uint256 = self.future_fee_gamma
    self.fee_gamma = fee_gamma
    allowed_extra_profit: uint256 = self.future_allowed_extra_profit
    self.allowed_extra_profit = allowed_extra_profit
    adjustment_step: uint256 = self.future_adjustment_step
    self.adjustment_step = adjustment_step
    ma_time: uint256 = self.future_ma_time
    self.ma_time = ma_time

    log NewParameters(
        admin_fee,
        mid_fee,
        out_fee,
        fee_gamma,
        allowed_extra_profit,
        adjustment_step,
        ma_time,
    )


@external
def revert_new_parameters():
    assert msg.sender == self.owner  # dev: only owner

    self.admin_actions_deadline = 0


@external
def commit_transfer_ownership(_owner: address):
    assert msg.sender == self.owner  # dev: only owner
    assert self.transfer_ownership_deadline == 0  # dev: active transfer

    _deadline: uint256 = block.timestamp + ADMIN_ACTIONS_DELAY
    self.transfer_ownership_deadline = _deadline
    self.future_owner = _owner

    log CommitNewAdmin(_deadline, _owner)


@external
def apply_transfer_ownership():
    assert msg.sender == self.owner  # dev: only owner
    assert block.timestamp >= self.transfer_ownership_deadline  # dev: insufficient time
    assert self.transfer_ownership_deadline != 0  # dev: no active transfer

    self.transfer_ownership_deadline = 0
    _owner: address = self.future_owner
    self.owner = _owner

    log NewAdmin(_owner)


@external
def revert_transfer_ownership():
    assert msg.sender == self.owner  # dev: only owner

    self.transfer_ownership_deadline = 0


@external
def kill_me():
    assert msg.sender == self.owner  # dev: only owner
    assert self.kill_deadline > block.timestamp  # dev: deadline has passed
    self.is_killed = True


@external
def unkill_me():
    assert msg.sender == self.owner  # dev: only owner
    self.is_killed = False


@external
def set_admin_fee_receiver(_admin_fee_receiver: address):
    assert msg.sender == self.owner  # dev: only owner
    self.admin_fee_receiver = _admin_fee_receiver


@view
@external
def DOMAIN_SEPARATOR() -> bytes32:
    """
    @notice EIP712 domain separator.
    """
    return self._domain_separator()
