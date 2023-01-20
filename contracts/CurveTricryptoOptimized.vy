# @version 0.3.7
# (c) Curve.Fi, 2021
# Pool for 3 coin unpegged assets (e.g. ETH, BTC, USD)
# note: View methods for `get_dy`, `get_dx`, `calc_token_amounts`
#       etc. are available in the `views_implementation` of the Factory.


from vyper.interfaces import ERC20
implements: ERC20  # <--------------------- AMM contract is also the LP token.

# --------------------------------- Interfaces -------------------------------

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

interface Factory:
    def admin() -> address: view
    def fee_receiver() -> address: view


# ------------------------------- Events -------------------------------------

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

event CommitNewParameters:
    deadline: indexed(uint256)
    mid_fee: uint256
    out_fee: uint256
    fee_gamma: uint256
    allowed_extra_profit: uint256
    adjustment_step: uint256
    ma_time: uint256

event NewParameters:
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

event TweakPriceScale:
    price_scale: uint256[2]
    adjustment_step: uint256


# ----------------------- Storage/State Variables ----------------------------

WETH20: immutable(address)  # <- Address of wrapper contract for native asset.

N_COINS: constant(uint256) = 3
PRECISION: constant(uint256) = 10**18  # <------- The precision to convert to.
A_MULTIPLIER: constant(uint256) = 10000
packed_precisions: uint256

math: address  # <--------- Math implementation contract is stored in Factory.
coins: public(address[N_COINS])
factory: public(address)

price_scale_packed: uint256  # <------------------------ Internal price scale.
price_oracle_packed: uint256  # <------- Price target given by moving average.

last_prices_packed: uint256
last_prices_timestamp: public(uint256)

initial_A_gamma: public(uint256)
initial_A_gamma_time: public(uint256)

future_A_gamma: public(uint256)
future_A_gamma_time: public(uint256)  # <------ Time when ramping is finished.
# ----------------- This value is 0 (default) when pool is first deployed, and
# -------------------- only gets populated by block.timestamp + future_time in
# ------------- in `ramp_A_gamma` when the ramping process is initiated. After
# ----- ramping is finished (i.e. self.future_A_gamma_time < block.timestamp),
# --------------- the self.future_A_gamma_time is left as is and not set to 0.

balances: public(uint256[N_COINS])
D: public(uint256)

# -------------- Params that affect how price_scale get adjusted -------------

packed_rebalancing_params: public(uint256)  # <---------- Contains rebalancing
# ------------- parameters allowed_extra_profit, adjustment_step, and ma_time.
future_packed_rebalancing_params: uint256

xcp_profit: public(uint256)
xcp_profit_a: public(uint256)  # <--- Full profit at last claim of admin fees.
virtual_price: public(uint256)  # <------ Cached (fast to read) virtual price.
# -------------------------The cached `virtual_price` is also used internally.

# ---------------- Fee params that determine dynamic fees --------------------

packed_fee_params: public(uint256)  # <---- Packs mid_fee, out_fee, fee_gamma.
future_packed_fee_params: uint256

ADMIN_FEE: constant(uint256) = 5 * 10**9  # <------------- 50% of earned fees.
MIN_FEE: constant(uint256) = 5 * 10**5  # <-------------------------- 0.5 BPS.
MAX_FEE: constant(uint256) = 10 * 10**9
NOISE_FEE: constant(uint256) = 10**5  # <---------------------------- 0.1 BPS.

# ----------------------- Admin params ---------------------------------------

admin_actions_deadline: public(uint256)

ADMIN_ACTIONS_DELAY: constant(uint256) = 3 * 86400
MIN_RAMP_TIME: constant(uint256) = 86400

MIN_A: constant(uint256) = N_COINS**N_COINS * A_MULTIPLIER / 100
MAX_A: constant(uint256) = 1000 * A_MULTIPLIER * N_COINS**N_COINS
MAX_A_CHANGE: constant(uint256) = 10
MIN_GAMMA: constant(uint256) = 10**10
MAX_GAMMA: constant(uint256) = 5 * 10**16

PRICE_SIZE: constant(int128) = 256 / (N_COINS - 1)
PRICE_MASK: constant(uint256) = 2**PRICE_SIZE - 1

INF_COINS: constant(uint256) = 15

# ----------------------- ERC20 Specific vars --------------------------------

name: public(immutable(String[64]))
symbol: public(immutable(String[32]))
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
NAME_HASH: immutable(bytes32)
CACHED_CHAIN_ID: immutable(uint256)
salt: public(immutable(bytes32))
CACHED_DOMAIN_SEPARATOR: immutable(bytes32)


# ----------------------- Contract -------------------------------------------

@external
def __init__(
    _name: String[64],
    _symbol: String[32],
    _coins: address[N_COINS],
    _math: address,
    _weth: address,
    packed_precisions: uint256,
    packed_A_gamma: uint256,
    packed_fee_params: uint256,
    packed_rebalancing_params: uint256,
    packed_prices: uint256,
):

    self.factory = msg.sender

    name = _name
    symbol = _symbol

    self.math = _math
    self.coins = _coins
    self.packed_precisions = packed_precisions  # <------- Precisions of coins
    # -------------------------- are calculated as 10**(18 - coin.decimals()).

    self.initial_A_gamma = packed_A_gamma  # <------------------ A and gamma.
    self.future_A_gamma = packed_A_gamma

    self.packed_rebalancing_params = packed_rebalancing_params  # <-- Contains
    # ------------- rebalancing params: allowed_extra_profit, adjustment_step,
    # ------------------------------------------------------- and ma_exp_time.

    self.packed_fee_params = packed_fee_params  # <-------------- Contains Fee
    # -------------------------------- params: mid_fee, out_fee and fee_gamma.

    self.price_scale_packed = packed_prices
    self.price_oracle_packed = packed_prices
    self.last_prices_packed = packed_prices
    self.last_prices_timestamp = block.timestamp
    self.xcp_profit_a = 10**18

    # ------- Cache DOMAIN_SEPARATOR. If chain.id is not CACHED_CHAIN_ID, then
    # ---- DOMAIN_SEPARATOR will be re-calculated each time `permit` is called.
    # ------------------ Otherwise, it will always use CACHED_DOMAIN_SEPARATOR.
    # ---------------------- see: `_domain_separator()` for its implementation.
    NAME_HASH = keccak256(name)
    salt = block.prevhash
    CACHED_CHAIN_ID = chain.id
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
    WETH20 = _weth

    log Transfer(empty(address), self, 0)  # <------- Fire empty transfer from
    # ------------------------------------- 0x0 to self for indexers to catch.


# ------------------- Token transfers in and out of the AMM ------------------


@payable
@external
def __default__():
    if msg.value > 0:
        assert WETH20 in self.coins  # dev: ETH not in pool
        # ------------------------------ Checks if deployed pool contains ETH.
        # ---- This ensures no ETH is stuck in a pool where ETH is not a coin.


@internal
def _transfer_in(
    _coin: address,
    dx: uint256,
    dy: uint256,
    mvalue: uint256,
    callbacker: address,
    callback_sig: bytes32,
    sender: address,
    receiver: address,
    use_eth: bool
):
    """
    @notice Transfers `_coin` from `sender` to `self` and calls `callback_sig`
            if it is not empty.
    @dev The callback sig must have the following args:
         sender: address
         receiver: address
         coin: address
         dx: uint256
         dy: uint256
    @params _coin: address of the coin to transfer in.
    @params dx: amount of `_coin` to transfer into the pool.
    @params dy: amount of `_coin` to transfer out of the pool.
    @params mvalue: msg.value if the transfer is ETH, 0 otherwise.
    @params callbacker: address to call `callback_sig` on.
    @params callback_sig: signature of the callback function.
    @params sender: address to transfer `_coin` from.
    @params receiver: address to transfer `_coin` to.
    @params use_eth: True if the transfer is ETH, False otherwise.
    """

    if use_eth and _coin == WETH20:
        assert mvalue == dx  # dev: incorrect eth amount
    else:
        assert mvalue == 0  # dev: nonzero eth amount

        if callback_sig == empty(bytes32):

            assert ERC20(_coin).transferFrom(
                sender, self, dx, default_return_value=True
            )

        else:

            # --------------- First call callback logic and then check if pool
            # ---------------- gets dx amounts of _coins[i], revert otherwise.
            b: uint256 = ERC20(_coin).balanceOf(self)
            raw_call(
                callbacker,
                concat(
                    slice(callback_sig, 0, 4),
                    _abi_encode(sender, receiver, _coin, dx, dy)
                )
            )
            assert ERC20(_coin).balanceOf(self) - b == dx  # dev: callback didn't give us coins

        if _coin == WETH20:
            WETH(WETH20).withdraw(dx)  # <--------- if WETH was transferred in
            # --------- previous step and `not use_eth`, withdraw WETH to ETH.


@internal
def _transfer_out(
    _amount: uint256, i: uint256, use_eth: bool, receiver: address
):
    """
    @notice Withdraws a single token from the pool
    @dev This function is called by `remove_liquidity` and
         `remove_liquidity_one` and `_exchange` methods.
    @params _amount Amount of token to withdraw
    @params i Index of token to withdraw
    @params use_eth Whether to withdraw ETH or not
    @params receiver Address to send the withdrawn tokens to
    """

    if use_eth and self.coins[i] == WETH20:
        raw_call(receiver, b"", value=_amount)
    else:
        if self.coins[i] == WETH20:
            WETH(WETH20).deposit(value=_amount)

        assert ERC20(self.coins[i]).transfer(
            receiver, _amount, default_return_value=True
        )


# -------------------------- AMM Main Functions ------------------------------


@payable
@external
@nonreentrant("lock")
def exchange(
    i: uint256,
    j: uint256,
    dx: uint256,
    min_dy: uint256,
    use_eth: bool = False,
    receiver: address = msg.sender
) -> uint256:
    """
    Exchange using WETH by default
    """
    return self._exchange(
        msg.sender,
        msg.value,
        i,
        j,
        dx,
        min_dy,
        use_eth,
        receiver,
        empty(address),
        empty(bytes32)
    )


@payable
@external
@nonreentrant('lock')
def exchange_underlying(
    i: uint256,
    j: uint256,
    dx: uint256,
    min_dy: uint256,
    receiver: address = msg.sender
) -> uint256:
    """
    Exchange using ETH
    """
    return self._exchange(
        msg.sender,
        msg.value,
        i,
        j,
        dx,
        min_dy,
        True,
        receiver,
        empty(address),
        empty(bytes32)
    )


@payable
@external
@nonreentrant('lock')
def exchange_extended(
    i: uint256,
    j: uint256,
    dx: uint256,
    min_dy: uint256,
    use_eth: bool,
    sender: address,
    receiver: address,
    cb: bytes32
) -> uint256:

    assert cb != empty(bytes32)  # dev: No callback specified
    return self._exchange(
        sender, msg.value, i, j, dx, min_dy, use_eth, receiver, msg.sender, cb
    )


@payable
@external
@nonreentrant("lock")
def add_liquidity(
    amounts: uint256[N_COINS],
    min_mint_amount: uint256,
    use_eth: bool = False,
    receiver: address = msg.sender
) -> uint256:

    A_gamma: uint256[2] = self._A_gamma()
    xp: uint256[N_COINS] = self.balances
    amountsp: uint256[N_COINS] = empty(uint256[N_COINS])
    xx: uint256[N_COINS] = empty(uint256[N_COINS])
    d_token: uint256 = 0
    d_token_fee: uint256 = 0
    old_D: uint256 = 0
    ix: uint256 = INF_COINS

    # --------------------- Get prices, balances -----------------------------

    xp_old: uint256[N_COINS] = xp
    for i in range(N_COINS):
        bal: uint256 = xp[i] + amounts[i]
        xp[i] = bal
        self.balances[i] = bal
    xx = xp

    packed_prices: uint256 = self.price_scale_packed
    precisions: uint256[N_COINS] = self._unpack(self.packed_precisions)

    xp[0] *= precisions[0]
    xp_old[0] *= precisions[0]
    for i in range(1, N_COINS):
        price_scale: uint256 = (packed_prices & PRICE_MASK) * precisions[i]
        xp[i] = xp[i] * price_scale / PRECISION
        xp_old[i] = xp_old[i] * price_scale / PRECISION
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    # ---------------------- transferFrom token ------------------------------

    if not use_eth:
        assert msg.value == 0  # dev: nonzero eth amount

    for i in range(N_COINS):

        if use_eth and self.coins[i] == WETH20:
            assert msg.value == amounts[i]  # dev: incorrect eth amount

        if amounts[i] > 0:

            if not use_eth or self.coins[i] != WETH20:

                assert ERC20(self.coins[i]).transferFrom(
                    msg.sender, self, amounts[i], default_return_value=True
                )

                if self.coins[i] == WETH20:
                    WETH(WETH20).withdraw(amounts[i])

            amountsp[i] = xp[i] - xp_old[i]

        if ix == INF_COINS:
            ix = i
        else:
            ix = INF_COINS - 1

    assert ix != INF_COINS  # dev: no coins to add

    # -------------------- Calculate LP tokens to mint -----------------------

    check_loss: bool = True
    if self.future_A_gamma_time > block.timestamp:  # <--- A_gamma is ramping.

        check_loss = False  # <----------- If the A_gamma is undergoing a ramp
        # -------- then new virtual_price can be lower than old virtual_price.
        # -------- In this case, we want to switch off this Loss check so that
        # ----------------------- the pool continues to function even during a
        # ----------------------- ramp and collect profits to offset the loss.

        # ----- Recalculate the invariant if A or gamma are undergoing a ramp.
        old_D = Math(self.math).newton_D(A_gamma[0], A_gamma[1], xp_old, 0)

    else:
        old_D = self.D

    D: uint256 = Math(self.math).newton_D(A_gamma[0], A_gamma[1], xp, 0)

    token_supply: uint256 = self.totalSupply
    if old_D > 0:
        d_token = token_supply * D / old_D - token_supply
    else:
        d_token = self.get_xcp(D)  # <------------------------- Making initial
        # ------------------------------------------ virtual price equal to 1.

    assert d_token > 0  # dev: nothing minted

    if old_D > 0:

        d_token_fee = (
            self._calc_token_fee(amountsp, xp) * d_token / 10**10 + 1
        )

        d_token -= d_token_fee
        token_supply += d_token
        self.mint(receiver, d_token)

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
                            S += xx[0] * precisions[0]
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

        self.tweak_price(A_gamma, xp, ix, p, D, 0, check_loss)

    else:

        self.D = D
        self.virtual_price = 10**18
        self.xcp_profit = 10**18
        self.mint(receiver, d_token)

    assert d_token >= min_mint_amount, "Slippage"

    log AddLiquidity(receiver, amounts, d_token_fee, token_supply)

    return d_token


@external
@nonreentrant("lock")
def remove_liquidity(
    _amount: uint256,
    min_amounts: uint256[N_COINS],
    use_eth: bool = False,
    receiver: address = msg.sender
):
    """
    @notice This withdrawal method is very safe, does no complex math since
            tokens are withdrawn in balanced proportions. No fees are charged.
    @param _amount Amount of LP tokens to burn
    @param min_amounts Minimum amounts of tokens to withdraw
    @param use_eth Whether to withdraw ETH or not
    @param receiver Address to send the withdrawn tokens to
    """
    total_supply: uint256 = self.totalSupply
    self.burnFrom(msg.sender, _amount)
    balances: uint256[N_COINS] = self.balances
    d_balances: uint256[N_COINS] = empty(uint256[N_COINS])

    # -------------- There are two cases for withdrawing tokens from the pool:
    # - Case 1. Withdrawal does not empty the pool.
    # --------- In this situation, D is adjusted proportional to the amount of
    # --------- LP tokens burnt. ERC20 tokens transferred is proportional
    # --------- to : (AMM balance * LP tokens in) / LP token total supply
    # - Case 2. Withdrawal empties the pool.
    # --------- In this situation, D is set to 0 and all but 1 Wei of each
    # --------- token is withdrawn.

    if _amount == total_supply:  # <---------------------------------- Case 1.

        for i in range(N_COINS):

            d_balances[i] = balances[i] - 1
            self.balances[i] = 1  # <--------------------- Leave 1 wei behind.

        self.D = 0  # <--------- Set D to 0 and reset the pool to start state.

    else:  # <-------------------------------------------------------- Case 2.

        amount: uint256 = _amount - 1

        for i in range(N_COINS):
            d_balances[i] = balances[i] * amount / total_supply
            assert d_balances[i] >= min_amounts[i]
            self.balances[i] = balances[i] - d_balances[i]
            balances[i] = d_balances[i]  # <-- Now it's the amounts going out.

        D: uint256 = self.D
        self.D = D - D * amount / total_supply  # <----- Reduce D proportional
        # ----------------------------------- to the amount of tokens leaving.
        # ------ Since withdrawals are balanced, this is a simple subtraction.

    # ---------------------------------- Transfers ---------------------------

    for i in range(N_COINS):
        self._transfer_out(d_balances[i], i, use_eth, receiver)

    log RemoveLiquidity(msg.sender, balances, total_supply - _amount)


@external
@nonreentrant("lock")
def remove_liquidity_one_coin(
    token_amount: uint256,
    i: uint256,
    min_amount: uint256,
    use_eth: bool = False,
    receiver: address = msg.sender
) -> uint256:
    """
    @notice Withdraw liquidity in a single token. Involves fees.
    """

    A_gamma: uint256[2] = self._A_gamma()

    dy: uint256 = 0
    D: uint256 = 0
    p: uint256 = 0
    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    K0_prev: uint256 = 0
    approx_fee: uint256 = 0

    # ------------------------------------------------------------------------

    check_loss: bool = True
    if self.future_A_gamma_time > block.timestamp:
        check_loss = False  # <---- If A and/or gamma are being ramped, do not
        # ----- check if re-computed virtual price after removing liquidity is
        # ------------------- above the current virtual price. This is because
        # ------------------ ramping of pool parameters can cause pool losses.

    dy, p, D, xp, approx_fee = self._calc_withdraw_one_coin(
        A_gamma, token_amount, i, not check_loss, True
    )  #                           ^--- If check_loss is True, then `update_D`
    # ------------- is False. If check_loss is False, then `update_D` is True.
    # -------- We need to update D if ramps are happening. This is because the
    # ---------------- invariant experiences a change while parameter ramping.
    # ----------- If we do not recalculate invariant during ramping, then the
    # --------------------------------------- calculated dy will be incorrect.

    assert dy >= min_amount, "Slippage"

    # ------------------------------------------------------------------------

    self.balances[i] -= dy
    self.burnFrom(msg.sender, token_amount)

    self._transfer_out(dy, i, use_eth, receiver)  # <--------- Withdraw token.

    self.tweak_price(A_gamma, xp, i, p, D, 0, check_loss)

    log RemoveLiquidityOne(msg.sender, token_amount, i, dy, approx_fee)

    self._claim_admin_fees()  # <--------------------------- Claim admin fees.

    return dy


@external
@nonreentrant("lock")
def claim_admin_fees():
    self._claim_admin_fees()


# ----------------------------- Packing function -----------------------------


@internal
@view
def _pack(x: uint256[3]) -> uint256:
    """
    @notice Packs 3 integers with values <= 10**18 into a uint256
    @param x The uint256[3] to pack
    @return The packed uint256
    """
    return shift(x[0], 128) | shift(x[1], 64) | x[2]


@internal
@view
def _unpack(_packed: uint256) -> uint256[3]:
    """
    @notice Unpacks a uint256 into 3 integers (values must be <= 10**18)
    @param val The uint256 to unpack
    @return The unpacked uint256[3]
    """
    return [
        shift(_packed, -128) & 18446744073709551615,
        shift(_packed, -64) & 18446744073709551615,
        _packed & 18446744073709551615,
    ]


@internal
@view
def _pack_prices(prices_to_pack: uint256[N_COINS-1]) -> uint256:
    packed_prices: uint256 = 0
    p: uint256 = 0
    for k in range(N_COINS - 1):
        packed_prices = shift(packed_prices, PRICE_SIZE)
        p = prices_to_pack[N_COINS - 2 - k]
        assert p < PRICE_MASK
        packed_prices = p | packed_prices
    return packed_prices


@internal
@view
def _unpack_prices(_packed_prices: uint256) -> uint256[2]:
    unpacked_prices: uint256[N_COINS-1] = empty(uint256[N_COINS-1])
    packed_prices: uint256 = _packed_prices
    for k in range(N_COINS - 1):
        unpacked_prices[k] = packed_prices & PRICE_MASK
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    return unpacked_prices


@internal
@view
def _packed_view(k: uint256, p: uint256) -> uint256:
    assert k < N_COINS - 1
    return shift(p, -PRICE_SIZE * convert(k, int256)) & PRICE_MASK


# ---------------------- AMM Internal Functions -------------------------------


@internal
def _exchange(
    sender: address,
    mvalue: uint256,
    i: uint256,
    j: uint256,
    dx: uint256,
    min_dy: uint256,
    use_eth: bool,
    receiver: address,
    callbacker: address,
    callback_sig: bytes32
) -> uint256:

    assert i != j  # dev: coin index out of range
    assert i < N_COINS  # dev: coin index out of range
    assert j < N_COINS  # dev: coin index out of range
    assert dx > 0  # dev: do not exchange 0 coins

    A_gamma: uint256[2] = self._A_gamma()
    xp: uint256[N_COINS] = self.balances
    precisions: uint256[N_COINS] = self._unpack(self.packed_precisions)
    ix: uint256 = j
    p: uint256 = 0
    dy: uint256 = 0

    y: uint256 = xp[j]
    x0: uint256 = xp[i]
    xp[i] = x0 + dx
    self.balances[i] = xp[i]

    price_scale: uint256[N_COINS - 1] = self._unpack_prices(
        self.price_scale_packed
    )

    xp[0] *= precisions[0]
    for k in range(1, N_COINS):
        xp[k] = unsafe_div(
            xp[k] * price_scale[k - 1] * precisions[k],
            PRECISION
        )

    prec_i: uint256 = precisions[i]

    # ----------- Update invariant if A, gamma are undergoing ramps ---------

    t: uint256 = self.future_A_gamma_time
    check_loss: bool = True
    if t > block.timestamp:

        check_loss = False  # <----------------- Do not check loss if ramping.
        # --------- This is because during ramping, virtual_price can go down.
        # --------- If it does, then the check will raise an error and the AMM
        # ----------------------------------------------------- will not work.

        x0 *= prec_i

        if i > 0:
            x0 = x0 * price_scale[i - 1] / PRECISION

        x1: uint256 = xp[i]  # <------------------ Back up old value in xp ...
        xp[i] = x0                                                         # |
        self.D = Math(self.math).newton_D(A_gamma[0], A_gamma[1], xp, 0)   # |
        xp[i] = x1  # <-------------------------------------- ... and restore.

    # ----------------------- Calculate dy and fees --------------------------

    prec_j: uint256 = precisions[j]
    y_out: uint256[2] = Math(
        self.math
    ).get_y(A_gamma[0], A_gamma[1], xp, self.D, j)
    dy = xp[j] - y_out[0]  # <------------------------- y_out[0] is the new y.

    xp[j] -= dy  # <----------------------------- Not defining new "y" here to
    # ------------------- have less variables / make subsequent calls cheaper.
    dy -= 1  # <----------------- This ensures that the pool isn't emptied one
    # ----------------------------------------- sided and math equations work.

    if j > 0:
        dy = dy * PRECISION / price_scale[j - 1]
    dy /= prec_j

    fee: uint256 = self._fee(xp) * dy / 10**10

    dy -= fee
    assert dy >= min_dy, "Slippage"
    y -= dy

    self.balances[j] = y

    # ---------------------- Do Transfers in and out -------------------------

    # TRANSFER IN <-------
    self._transfer_in(
        self.coins[i], dx, dy, mvalue,
        callbacker, callback_sig,  # <-------- Callback method is called here.
        sender, receiver, use_eth,
    )

    # -------> TRANSFER OUT
    self._transfer_out(dy, i, use_eth, receiver)

    # --------------------- Calculate and adjust prices ----------------------

    y *= prec_j
    if j > 0:
        y = y * price_scale[j - 1] / PRECISION
    xp[j] = y  # <-------------------------------------------------- Update xp

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

    # ----------------------------------------------------- Tweak price_scale.
    self.tweak_price(A_gamma, xp, ix, p, 0, 0, check_loss)
    #                                    ^  ^-- No initial guess for newton_D.
    #                                    ^--------- recalculate invariant (D).

    log TokenExchange(sender, i, dx, j, dy, fee)

    return dy


@internal
def tweak_price(
    A_gamma: uint256[2],
    _xp: uint256[N_COINS],
    i: uint256,
    p_i: uint256,
    new_D: uint256,
    K0_prev: uint256 = 0,
    check_loss: bool = True,
):
    """
    @notice Conditionally adjust prices in the pool.
    @dev Contains main liquidity rebalancing logic, by tweaking `price_scale`
    @param A_gamma Array of A and gamma parameters
    @param _xp Array of current balances
    @param i Index of the coin to tweak
    @param p_i Current price of the coin
    @param new_D New D value
    @param K0_prev Initial guess for `newton_D`
    """
    price_oracle: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
    last_prices: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
    price_scale: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    p_new: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])

    rebalancing_params: uint256[3] = self._unpack(
        self.packed_rebalancing_params
    )  # <---------- Contains: allowed_extra_profit, adjustment_step, ma_time.

    # ------------------ Unpack internal oracle and last prices --------------

    price_oracle = self._unpack_prices(self.price_oracle_packed)

    last_prices_timestamp: uint256 = self.last_prices_timestamp
    last_prices = self._unpack_prices(self.last_prices_packed)

    # ----------------------- Update MA if needed ----------------------------

    if last_prices_timestamp < block.timestamp:

        # ------------------ Calculate moving average params -----------------

        alpha: uint256 = Math(self.math).wad_exp(
            -convert(
                (
                    (block.timestamp - last_prices_timestamp) * 10**18 /
                    rebalancing_params[2]  # <----------------------- ma_time.
                ),
                int256,
            )
        )

        for k in range(N_COINS - 1):
            price_oracle[k] = (
                last_prices[k] * (10**18 - alpha) + price_oracle[k] * alpha
            ) / 10**18

        self.price_oracle_packed = self._pack_prices(price_oracle)
        self.last_prices_timestamp = block.timestamp  # <---- Store timestamp.

    # ------------------ If new_D is set to 0, calculate it ------------------

    D_unadjusted: uint256 = new_D  # <- Withdrawal methods know new D already.
    if new_D == 0:  # <----------------- _exchange method does not know new D.
        D_unadjusted = (
            Math(self.math).newton_D(A_gamma[0], A_gamma[1], _xp, K0_prev)
        )

    price_scale = self._unpack_prices(self.price_scale_packed)

    if p_i > 0:

        # -------------------------- Save the last price ---------------------
        if i > 0:
            last_prices[i - 1] = p_i
        else:
            for k in range(N_COINS - 1):
                last_prices[k] = last_prices[k] * 10**18 / p_i  # <---- If 0th
                # ----------------- price changed - change all prices instead.
    else:

        # ------------------------ Calculate real prices ---------------------

        __xp: uint256[N_COINS] = _xp
        dx_price: uint256 = __xp[0] / 10**6
        __xp[0] += dx_price

        y_out: uint256[2] = empty(uint256[2])

        for k in range(N_COINS - 1):

            y_out = Math(self.math).get_y(
                A_gamma[0],
                A_gamma[1],
                __xp,
                D_unadjusted,
                k + 1
            )

            last_prices[k] = (
                price_scale[k] * dx_price / (_xp[k + 1] - y_out[0])
            )

    self.last_prices_packed = self._pack_prices(last_prices)

    total_supply: uint256 = self.totalSupply
    old_xcp_profit: uint256 = self.xcp_profit
    old_virtual_price: uint256 = self.virtual_price

    # ------- Update profit numbers without price adjustment first -----------

    xp[0] = unsafe_div(D_unadjusted, N_COINS)
    for k in range(N_COINS - 1):
        xp[k + 1] = D_unadjusted * 10**18 / (N_COINS * price_scale[k])

    xcp_profit: uint256 = 10**18
    virtual_price: uint256 = 10**18

    if old_virtual_price > 0:

        xcp: uint256 = Math(self.math).geometric_mean(xp)
        virtual_price = 10**18 * xcp / total_supply
        xcp_profit = unsafe_div(
            old_xcp_profit * virtual_price,
            old_virtual_price
        )  # <---------------- Safe to do unsafe_div as old_virtual_price > 0.

        # ------ If A and gamma re not undergoing ramps (t < block.timestamp),
        # ------- ensure new virtual_price is not less than old virtual_price,
        # -------------------------------------- else the pool suffers a loss.
        if check_loss:
            assert virtual_price > old_virtual_price, "Loss"

    self.xcp_profit = xcp_profit

    # ------------ Rebalance liquidity if there's enough profits to adjust it:
    if virtual_price * 2 - 10**18 > xcp_profit + 2 * rebalancing_params[0]:
        #                          allowed_extra_profit --------^

        # ------------------- Get adjustment step ----------------------------

        norm: uint256 = 0
        ratio: uint256 = 0
        for k in range(N_COINS - 1):
            ratio = price_oracle[k] * 10**18 / price_scale[k]
            if ratio > 10**18:
                ratio = unsafe_sub(ratio, 10**18)
            else:
                ratio = unsafe_sub(10**18, ratio)
            norm = unsafe_add(norm, ratio**2)

        norm = isqrt(norm)
        adjustment_step: uint256 = max(
            rebalancing_params[1], unsafe_div(norm, 5)
        )  #           ^------------------------------------- adjustment_step.

        if norm > adjustment_step and old_virtual_price > 0:  # <----- We only
            # ------------------- adjust prices if the vector distance between
            # ------ price_oracle and price_scale are large enough. This check
            # --- ensures that no rebalancing occurs if the distance is small,
            # ---------- i.e. the pool prices are pegged to the oracle prices.

            # -------------- Calculate new price scale -----------------------

            for k in range(N_COINS - 1):
                p_new[k] = unsafe_div(
                    price_scale[k] * unsafe_sub(norm, adjustment_step)
                    + adjustment_step * price_oracle[k],
                    norm
                )

            xp = _xp
            for k in range(N_COINS - 1):
                xp[k + 1] = _xp[k + 1] * p_new[k] / price_scale[k]

            D: uint256 = (
                Math(self.math).newton_D(A_gamma[0], A_gamma[1], xp, K0_prev)
            )

            xp[0] = D / N_COINS
            for k in range(N_COINS - 1):
                xp[k + 1] = D * 10**18 / (N_COINS * p_new[k])

            # ------------------------------------- Reuse `old_virtual_price`.
            old_virtual_price = (
                10**18 * Math(self.math).geometric_mean(xp) / total_supply
            )

            # --------- Proceed if we've got enough profit -------------------

            if (
                old_virtual_price > 10**18 and
                2 * old_virtual_price - 10**18 > xcp_profit
            ):

                self.price_scale_packed = self._pack_prices(p_new)
                self.D = D
                self.virtual_price = old_virtual_price

                log TweakPriceScale(p_new, adjustment_step)  # <--- Log tweak.

                return  # <------------------------- Return if we've adjusted.

    # --------------------- If we are here, the price_scale adjustment did not
    # -------------- happen. We Still need to update the profit counter and D.
    self.D = D_unadjusted
    self.virtual_price = virtual_price


@internal
def _claim_admin_fees():
    A_gamma: uint256[2] = self._A_gamma()

    xcp_profit: uint256 = self.xcp_profit
    xcp_profit_a: uint256 = self.xcp_profit_a

    for i in range(N_COINS):  # <---------------------------------- Gulp here.
        if self.coins[i] == WETH20:
            self.balances[i] = self.balance
        else:
            self.balances[i] = ERC20(self.coins[i]).balanceOf(self)

    vprice: uint256 = self.virtual_price

    if xcp_profit > xcp_profit_a:
        fees: uint256 = (xcp_profit - xcp_profit_a) * ADMIN_FEE / (2 * 10**10)

        # ------------------------ Claim admin fee ---------------------------

        receiver: address = Factory(self.factory).fee_receiver()
        if receiver != empty(address):
            frac: uint256 = vprice * 10**18 / (vprice - fees) - 10**18
            claimed: uint256 = self.mint_relative(receiver, frac)
            xcp_profit -= fees * 2
            self.xcp_profit = xcp_profit
            log ClaimAdminFee(receiver, claimed)

    total_supply: uint256 = self.totalSupply

    D: uint256 = (
        Math(self.math).newton_D(A_gamma[0], A_gamma[1], self.xp(), 0)
    )  # <--------------------------------------- Recalculate D b/c we gulped.
    self.D = D

    self.virtual_price = 10**18 * self.get_xcp(D) / total_supply

    if xcp_profit > xcp_profit_a:
        self.xcp_profit_a = xcp_profit


@internal
@view
def xp() -> uint256[N_COINS]:
    result: uint256[N_COINS] = self.balances
    packed_prices: uint256 = self.price_scale_packed
    precisions: uint256[N_COINS] = self._unpack(self.packed_precisions)

    result[0] *= precisions[0]
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

        # --------------- Handle ramping up and down of A --------------------

        A_gamma_0: uint256 = self.initial_A_gamma
        t0: uint256 = self.initial_A_gamma_time

        t1 -= t0
        t0 = block.timestamp - t0
        t2: uint256 = t1 - t0

        A1 = (shift(A_gamma_0, -128) * t2 + A1 * t0) / t1
        gamma1 = ((A_gamma_0 & 2**128 - 1) * t2 + gamma1 * t0) / t1

    return [A1, gamma1]


@internal
@view
def _fee(xp: uint256[N_COINS]) -> uint256:
    fee_params: uint256[3] = self._unpack(self.packed_fee_params)
    f: uint256 = Math(self.math).reduction_coefficient(xp, fee_params[2])
    return (fee_params[0] * f + fee_params[1] * (10**18 - f)) / 10**18


@internal
@view
def get_xcp(D: uint256) -> uint256:
    x: uint256[N_COINS] = empty(uint256[N_COINS])
    x[0] = D / N_COINS
    packed_prices: uint256 = self.price_scale_packed  # <-- No precisions here
    # ------------------------------- because we don't switch to "real" units.

    for i in range(1, N_COINS):
        x[i] = D * 10**18 / (N_COINS * (packed_prices & PRICE_MASK))
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    return Math(self.math).geometric_mean(x)


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


@internal
@view
def _calc_withdraw_one_coin(
    A_gamma: uint256[2],
    token_amount: uint256,
    i: uint256,
    update_D: bool,
    calc_price: bool,
) -> (uint256, uint256, uint256, uint256[N_COINS], uint256):

    token_supply: uint256 = self.totalSupply
    assert token_amount <= token_supply  # dev: token amount more than supply
    assert i < N_COINS  # dev: coin out of range

    xx: uint256[N_COINS] = self.balances
    precisions: uint256[N_COINS] = self._unpack(self.packed_precisions)
    xp: uint256[N_COINS] = precisions
    D0: uint256 = 0

    price_scale_i: uint256 = PRECISION * precisions[0]
    packed_prices: uint256 = self.price_scale_packed
    xp[0] *= xx[0]
    for k in range(1, N_COINS):
        p: uint256 = (packed_prices & PRICE_MASK)
        if i == k:
            price_scale_i = p * xp[i]
        xp[k] = xp[k] * xx[k] * p / PRECISION
        packed_prices = shift(packed_prices, -PRICE_SIZE)

    if update_D:  # <-------------- D is updated if pool is undergoing a ramp.
        D0 = Math(self.math).newton_D(A_gamma[0], A_gamma[1], xp, 0)
    else:
        D0 = self.D

    D: uint256 = D0

    # -------------------------------- Fee Calc ------------------------------
    # ----------------------------------------- Charge the fee on D, not on y.
    # -------------------- This reduces invariant LESS than charging the user.
    fee: uint256 = self._fee(xp)
    dD: uint256 = token_amount * D / token_supply

    D_fee: uint256 = fee * dD / (2 * 10**10) + 1  # <-------- Actual fee on D.
    approx_fee: uint256 = N_COINS * D_fee * xx[i] / D  # <---------- Calculate
    # ------------------ `approx_fee`` (assuming balanced state) in ith token.

    D -= (dD - D_fee)  # <----------------------------------- Charge fee on D.

    # ------------------------------------------------------------------------

    # --------------------------------- Calculate `y_out`` with `(D - D_fee)`.
    y_out: uint256[2] = Math(self.math).get_y(A_gamma[0], A_gamma[1], xp, D, i)
    dy: uint256 = (xp[i] - y_out[0]) * PRECISION / price_scale_i
    xp[i] = y_out[0]

    # --------------------------------- Price calc ---------------------------

    p: uint256 = 0
    if calc_price and dy > 10**5 and token_amount > 10**5:

        # p_i = dD / D0 * sum'(p_k * x_k) / (dy - dD / D0 * y0)
        S: uint256 = 0
        last_prices: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])

        packed_prices = self.last_prices_packed
        for k in range(N_COINS - 1):
            last_prices[k] = packed_prices & PRICE_MASK
            packed_prices = shift(packed_prices, -PRICE_SIZE)

        for k in range(N_COINS):
            if k != i:
                if k == 0:
                    S += xx[0] * precisions[0]
                else:
                    S += xx[k] * last_prices[k - 1] * precisions[k] / PRECISION

        S = S * dD / D0
        p = (
            S
            * PRECISION
            / (dy * precisions[i] - dD * xx[i] * precisions[i] / D0)
        )

    return dy, p, D, xp, approx_fee


# ------------------------ ERC20 functions -----------------------------------

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
         allowance to max_value(uint256). This has the potential to grant an
         infinite approval.
    @param _spender The account to increase the allowance of.
    @param _add_value The amount to increase the allowance by.
    """
    cached_allowance: uint256 = self.allowance[msg.sender][_spender]
    allowance: uint256 = unsafe_add(cached_allowance, _add_value)

    if allowance < cached_allowance:  # <-------------- Check for an overflow.
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

    if cached_allowance < allowance:  # <------------- Check for an underflow.
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

    self.nonces[_owner] = unsafe_add(nonce, 1)  # <-- Unsafe add is safe here.
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


# ------------------------- AMM View Functions -------------------------------


@external
@view
@nonreentrant("lock")
def get_virtual_price() -> uint256:
    return 10**18 * self.get_xcp(self.D) / self.totalSupply


@external
@view
@nonreentrant("lock")
def price_oracle(k: uint256) -> uint256:
    price_oracle: uint256 = self._packed_view(k, self.price_oracle_packed)
    last_prices_timestamp: uint256 = self.last_prices_timestamp

    if last_prices_timestamp < block.timestamp:  # <------------ Update moving
        # ------------------------------------------------- average if needed.

        last_prices: uint256 = self._packed_view(k, self.last_prices_packed)
        ma_time: uint256 = self._unpack(self.packed_rebalancing_params)[2]
        alpha: uint256 = Math(self.math).wad_exp(
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
def last_prices(k: uint256) -> uint256:
    return self._packed_view(k, self.last_prices_packed)


@external
@view
def price_scale(k: uint256) -> uint256:
    return self._packed_view(k, self.price_scale_packed)


@external
@view
def fee() -> uint256:
    return self._fee(self.xp())


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
@view
def calc_token_fee(
    amounts: uint256[N_COINS], xp: uint256[N_COINS]
) -> uint256:
    return self._calc_token_fee(amounts, xp)


@view
@external
def A_gamma() -> uint256[2]:  # <- A and gamma in view to save bytecode space.
    return self._A_gamma()


@view
@external
def precisions() -> uint256[N_COINS]:  # <-------------- For by view contract.
    return self._unpack(self.packed_precisions)


@external
@view
def fee_calc(xp: uint256[N_COINS]) -> uint256:  # <----- For by view contract.
    return self._fee(xp)


@view
@external
def DOMAIN_SEPARATOR() -> bytes32:
    """
    @notice EIP712 domain separator.
    """
    return self._domain_separator()


# ------------------------- AMM Admin Functions ------------------------------


@external
def ramp_A_gamma(
    future_A: uint256, future_gamma: uint256, future_time: uint256
):
    assert msg.sender == Factory(self.factory).admin()  # dev: only owner
    assert block.timestamp > self.initial_A_gamma_time + (MIN_RAMP_TIME - 1)  # dev: ramp undergoing
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
    assert msg.sender == Factory(self.factory).admin()  # dev: only owner

    A_gamma: uint256[2] = self._A_gamma()
    current_A_gamma: uint256 = shift(A_gamma[0], 128)
    current_A_gamma = current_A_gamma | A_gamma[1]
    self.initial_A_gamma = current_A_gamma
    self.future_A_gamma = current_A_gamma
    self.initial_A_gamma_time = block.timestamp
    self.future_A_gamma_time = block.timestamp

    # ------ Now (block.timestamp < t1) is always False, so we return saved A.

    log StopRampA(A_gamma[0], A_gamma[1], block.timestamp)


@external
def commit_new_parameters(
    _new_mid_fee: uint256,
    _new_out_fee: uint256,
    _new_fee_gamma: uint256,
    _new_allowed_extra_profit: uint256,
    _new_adjustment_step: uint256,
    _new_ma_time: uint256,
):
    assert msg.sender == Factory(self.factory).admin()  # dev: only owner
    assert self.admin_actions_deadline == 0  # dev: active action

    _deadline: uint256 = block.timestamp + ADMIN_ACTIONS_DELAY
    self.admin_actions_deadline = _deadline

    # ----------------------------- Set fee params ---------------------------

    new_mid_fee: uint256 = _new_mid_fee
    new_out_fee: uint256 = _new_out_fee
    new_fee_gamma: uint256 = _new_fee_gamma

    current_fee_params: uint256[3] = self._unpack(self.packed_fee_params)

    if new_out_fee < MAX_FEE + 1:
        assert new_out_fee > MIN_FEE - 1  # dev: fee is out of range
    else:
        new_out_fee = current_fee_params[1]

    if new_mid_fee > MAX_FEE:
        new_mid_fee = current_fee_params[0]
    assert new_mid_fee <= new_out_fee  # dev: mid-fee is too high

    if new_fee_gamma < 10**18:
        assert new_fee_gamma > 0  # dev: fee_gamma out of range [1 .. 10**18]
    else:
        new_fee_gamma = current_fee_params[2]

    self.future_packed_fee_params = self._pack(
        [new_mid_fee, new_out_fee, new_fee_gamma]
    )

    # ----------------- Set liquidity rebalancing parameters -----------------

    new_allowed_extra_profit: uint256 = _new_allowed_extra_profit
    new_adjustment_step: uint256 = _new_adjustment_step
    new_ma_time: uint256 = _new_ma_time

    current_rebalancing_params: uint256[3] = self._unpack(self.packed_rebalancing_params)

    if new_allowed_extra_profit > 10**18:
        new_allowed_extra_profit = current_rebalancing_params[0]

    if new_adjustment_step > 10**18:
        new_adjustment_step = current_rebalancing_params[1]

    if new_ma_time < 872542:  # <----- Calculated as: 7 * 24 * 60 * 60 / ln(2)
        assert new_ma_time > 86  # dev: MA time should be longer than 60/ln(2)
    else:
        new_ma_time = current_rebalancing_params[2]

    self.future_packed_rebalancing_params = self._pack(
        [new_allowed_extra_profit, new_adjustment_step, new_ma_time]
    )

    # ---------------------------------- LOG ---------------------------------

    log CommitNewParameters(
        _deadline,
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
    assert msg.sender == Factory(self.factory).admin()  #dev: only owner
    assert block.timestamp >= self.admin_actions_deadline  #dev: insufficient time
    assert self.admin_actions_deadline != 0  #dev: no active action

    self.admin_actions_deadline = 0

    packed_fee_params: uint256 = self.future_packed_fee_params
    self.packed_fee_params = packed_fee_params

    packed_rebalancing_params: uint256 = self.future_packed_rebalancing_params
    self.packed_rebalancing_params = packed_rebalancing_params

    rebalancing_params: uint256[3] = self._unpack(packed_rebalancing_params)
    fee_params: uint256[3] = self._unpack(packed_fee_params)

    log NewParameters(
        fee_params[0],
        fee_params[1],
        fee_params[2],
        rebalancing_params[0],
        rebalancing_params[1],
        rebalancing_params[2],
    )


@external
def revert_new_parameters():
    assert msg.sender == Factory(self.factory).admin()  # dev: only owner
    self.admin_actions_deadline = 0
