# Change Notes


The organizing principle of TriCrypto: Next Generation is to improve gas efficiency and user experience while maintaining readability to the end user.  The changes introduced throughout were documented robustly, with further notes placed into this README file.

![Gas Profile](https://user-images.githubusercontent.com/13426766/219870036-34e6d55a-c094-47ea-8b67-334e6853095a.png)

## AMM Improvements

### ERC20 Compatibility

**Problem:** Earlier Curve pools would separate the pool (for depositing and transacting) and the LP token into separate contracts.  In addition to being occasionally confusing, this also increases gas costs when the pool has to make external calls.

**Solution:** Bringing the LP token logic into the pool contract has been done with more modern Curve pools to great effect and is done so here in the new TriCrypto.

[CurveTriCryptoOptimizedWETH.vy](/contracts/CurveTricryptoOptimizedWETH.vy#L14)

    14 from vyper.interfaces import ERC20
    15 implements: ERC20  # <--------------------- AMM contract is also the LP token.


### Permit Method

Add a `permit()` method for gasless approvals


[CurveTriCryptoOptimizedWETH.vy](/contracts/CurveTricryptoOptimizedWETH.vy#L1479)

    1479 @external
    1480 def permit(
    1481     _owner: address,
    1482     _spender: address,
    1483     _value: uint256,
    1484     _deadline: uint256,
    1485     _v: uint8,
    1486     _r: bytes32,
    1487     _s: bytes32,
    1488 ) -> bool:
    1489     """
    1490     @notice Permit `_spender` to spend up to `_value` amount of `_owner`'s
    1491             tokens via a signature.
    1492     @dev In the event of a chain fork, replay attacks are prevented as
    1493          domain separator is recalculated. However, this is only if the
    1494          resulting chains update their chainId.
    1495     @param _owner The account which generated the signature and is granting an
    1496                   allowance.
    1497     @param _spender The account which will be granted an allowance.
    1498     @param _value The approval amount.
    1499     @param _deadline The deadline by which the signature must be submitted.
    1500     @param _v The last byte of the ECDSA signature.
    1501     @param _r The first 32 bytes of the ECDSA signature.
    1502     @param _s The second 32 bytes of the ECDSA signature.
    1503     """


### Factory Deployment

The current crypto factory only supports coin *pairings*.  The new factory allows creation of pools using *3 coins*.

Deployment features the `create_from_blueprint` function built into Vyper.  This stems from EIP-5202, authored by [Charles](https://github.com/charles-cooper) (lead Vyper core dev) and [skelletor](https://github.com/skellet0r) (core contributor, Curve), which has also been utilized in the previous generations of Curve factories.  This function allows contract templates to be stored on chain to decrease deployment costs.

### Fee Logic

All swaps, `add_liquidity`, and `remove_liquidity_one_coi`n will have fees associated with it, in contrast with the prior fee structure.

Additionally, fee claim logic is not triggered as frequently to save on gas.  Previously fees were claimed every liquidity action, which ate gas on nearly every exchange.  New logic only auto-claims fees on `remove_liquidity_one_coin`, which may be thought of as a gas penalty for leaving — run errands as you depart.

## MATH IMPROVEMENTS

### Square Root

**Problem:** *~2500 Gas*

Expensive iterative process to find solution

[CurveTriCryptoOptimizedWETH.vy](/contracts/CurveTricryptoOptimizedWETH.vy#L1479)

    307 @external
    308 @view
    309 def sqrt_int(x: uint256) -> uint256:
    310     """
    311     Originating from: https://github.com/vyperlang/vyper/issues/1266
    312     """
    313 
    314     if x == 0:
    315         return 0
    316 
    317     z: uint256 = (x + 10**18) / 2
    318     y: uint256 = x
    319 
    320     for i in range(256):
    321         if z == y:
    322             return y
    323         y = z
    324         z = (x * 10**18 / z + z) / 2
    325 
    326     raise "Did not converge"


**Solution:** *~450 gas*

Created a new [cheap isqrt() function built into Vyper 3.7](https://github.com/vyperlang/vyper/pull/3069).  The inspiration in this case came from [t11s’s solmate](https://github.com/Gaussian-Process/solmate/blob/837de01395312eb89e607fdc64fb7bb9c03207c3/src/utils/FixedPointMathLib.sol) and ported to Vyper.


### Cube Root

**Problem:** *~40K Gas*

Expensive iterative process in `newton_y` 

[old/CurveCryptoMath3.vy](/contracts/old/CurveCryptoMath3.vy#L180)

    215 for j in range(255):
    216     y_prev: uint256 = y
    217
    218     K0: uint256 = K0_i * y * N_COINS / D
    219     S: uint256 = S_i + y
    220
    221     _g1k0: uint256 = gamma + 10**18
    222     if _g1k0 > K0:
    223         _g1k0 = _g1k0 - K0 + 1
    224     else:
    225         _g1k0 = K0 - _g1k0 + 1
    226
    227     mul1: uint256 = (
    228         10**18 * D / gamma * _g1k0 / gamma * _g1k0 * A_MULTIPLIER / ANN
    229     )
    230 
    231     # 2*K0 / _g1k0
    232     mul2: uint256 = 10**18 + (2 * 10**18) * K0 / _g1k0


**Solution:** *~7K gas*

Instead of an iterative approach, use an analytical approach described in the [white paper](/docs/tricrypto_optimisation.pdf).

[![Vyper optimized newton_y](https://user-images.githubusercontent.com/13426766/219871044-07885d8a-9a32-42d6-b0f0-b80424efd656.png)](/docs/tricrypto_optimisation.pdf)

Use the logic from solmate’s log2(x), which costs ~3K gas, for further savings

### newton_D

**Problem:** *~55K-65K gas*

Named for the Sir Isaac Newton, the [Newton method](https://en.wikipedia.org/wiki/Newton%27s_method) uses an iterative approach to come up with a solution for the “D” in the equation.

**Solution:** *~10K-13K gas*

Named after Edmond Halley of comet fame, the [Halley method](https://en.wikipedia.org//wiki/Halley's_method) is a historical improvement on the Newton method, and used in its place.

[![TriCrypto Optimisation White Paper](https://user-images.githubusercontent.com/13426766/219871113-88bdddcf-99f0-47e0-b8a4-f628930a3638.png)](/docs/tricrypto_optimisation.pdf)

As an iterative solution, a more accurate initial D_0 can reduce the number of iterations to find a solution, thus saving gas.  Again, the [white paper describes the full derivation](/docs/tricrypto_optimisation.pdf).

Given that convergence is sensitive to the starting point, the optimized TriCrypto only uses this initial guess for the `_exchange` method, not others, reaping a significant gas savings. 

### Sorting

**Problem:** *~10K gas*

The [original sort](/contracts/old/CurveCryptoMath3.vy#L19) was too clever by half.  Using insertion sort worked, but for sorting 3 coins proved to be overkill.

[old/CurveCryptoMath3.vy](/contracts/old/CurveCryptoMath3.vy#L19)


    19 @internal
    20 @pure
    21 def sort(A0: uint256[N_COINS]) -> uint256[N_COINS]:
    22     """
    23     Insertion sort from high to low
    24     """
    25     A: uint256[N_COINS] = A0
    26     for i in range(1, N_COINS):
    27         x: uint256 = A[i]
    28         cur: uint256 = i
    29         for j in range(N_COINS):
    30             y: uint256 = A[cur - 1]
    31             if y > x:
    32                 break
    33             A[cur] = y
    34             cur -= 1
    35             if cur == 0:
    36                 break
    37         A[cur] = x
    38     return A


**Solution:** *~400 gas*

In this rare case, dumbing things down proved to be better.  [Brute forcing the results](/contracts/CurveCryptoMathOptimized3.vy#L831) resulted in significant gas savings.

[CurveCryptoMathOptimized3.vy](/contracts/CurveCryptoMathOptimized3.vy#L831)

    831 @internal
    832 @pure
    833 def _sort(unsorted_x: uint256[3]) -> uint256[3]:
    834 
    835     # Sorts a three-array number in a descending order:
    836 
    837     x: uint256[N_COINS] = unsorted_x
    838     temp_var: uint256 = x[0]
    839     if x[0] < x[1]:
    840         x[0] = x[1]
    841         x[1] = temp_var
    842     if x[0] < x[2]:
    843         temp_var = x[0]
    844         x[0] = x[2]
    845         x[2] = temp_var
    846     if x[1] < x[2]:
    847         temp_var = x[1]
    848         x[1] = x[2]
    849         x[2] = temp_var
    850 
    851     return x


### Half Power

**Problem:** *~10k gas*

The former custom method of raising to a number to the 0.5 power required an expensive iterative loop.

[old/CurveCryptoMath3.vy](/contracts/old/CurveCryptoMath3.vy#L268)

    268 @external
    269 @view
    270 def halfpow(power: uint256, precision: uint256) -> uint256:
    271     """
    272     1e18 * 0.5 ** (power/1e18)
    273     Inspired by: https://github.com/balancer-labs/balancer-core/blob/master/contracts/BNum.sol#L128
    274     """
    275     intpow: uint256 = power / 10**18
    276     otherpow: uint256 = power - intpow * 10**18
    277     if intpow > 59:
    278         return 0
    279     result: uint256 = 10**18 / (2**intpow)
    280     if otherpow == 0:
    281         return result
    282 
    283     term: uint256 = 10**18
    284     x: uint256 = 5 * 10**17
    285     S: uint256 = 10**18
    286     neg: bool = False
    287 
    288     for i in range(1, 256):
    289         K: uint256 = i * 10**18
    290         c: uint256 = K - 10**18
    291         if otherpow > c:
    292             c = otherpow - c
    293             neg = not neg
    294         else:
    295             c -= otherpow
    296         term = term * (c * x / 10**18) / K
    297         if neg:
    298             S -= term
    299         else:
    300             S += term
    301         if term < precision:
    302             return result * S / 10**18
    303     raise "Did not converge"


**Solution:** *~800 gas*

Using the exponent method, again [inspired by solmate](https://github.com/transmissions11/solmate/blob/main/src/utils/SignedWadMath.sol), makes it significantly cheaper to calculate exponents.  This method used frequently when calculating the weights for moving average prices, because crypto is so volatile. 

[CurveTricryptoOptimizedWETH.vy](/contracts/old/CurveCryptoMath3.vy#L976)

    976     # ----------------------- Update MA if needed ----------------------------
    977 
    978     if last_prices_timestamp < block.timestamp:
    979 
    980         #   The moving average price oracle is calculated using the last_price
    981         #      of the trade at the previous block, and the price oracle logged
    982         #              before that trade. This can happen only once per block.
    983 
    984         # ------------------ Calculate moving average params -----------------
    985 
    986         alpha: uint256 = MATH.wad_exp(
    987             -convert(
    988                 (
    989                     (block.timestamp - last_prices_timestamp) * 10**18 /
    990                     rebalancing_params[2]  # <----------------------- ma_time.
    991                 ),
    992                 int256,
    993             )
    994         )


### Geometric Mean

**Problem:** *~21k gas*

One of the more expensive functions, [which required a loop through 255 elements](/contracts/old/CurveCryptoMath3.vy#L41).

[old/CurveCryptoMath3.vy](/contracts/old/CurveCryptoMath3.vy#L41)

    41 @internal
    42 @view
    43 def _geometric_mean(unsorted_x: uint256[N_COINS], sort: bool = True) -> uint256:
    44     """
    45     (x[0] * x[1] * ...) ** (1/N)
    46     """
    47     x: uint256[N_COINS] = unsorted_x
    48     if sort:
    49         x = self.sort(x)
    50     D: uint256 = x[0]
    51     diff: uint256 = 0
    52     for i in range(255):
    53         D_prev: uint256 = D
    54         tmp: uint256 = 10**18
    55         for _x in x:
    56             tmp = tmp * _x / D
    57         D = D * ((N_COINS - 1) * 10**18 + tmp) / (N_COINS * 10**18)
    58         if D > D_prev:
    59             diff = D - D_prev
    60         else:
    61             diff = D_prev - D
    62         if diff <= 1 or diff * 10**18 < D:
    63             return D
    64     raise "Did not converge"



**Solution:** 

Using the cube root function described above provides a savings.

[CurveCryptoMathOptimized3.vy](/contracts/CurveCryptoMathOptimized3.vy#L854)

    854 @internal
    855 @view
    856 def _geometric_mean(_x: uint256[3]) -> uint256:
    857 
    858     # calculates a geometric mean for three numbers.
    859 
    860     prod: uint256 = _x[0] * _x[1] / 10**18 * _x[2] / 10**18
    861     assert prod > 0
    862 
    863     return self._cbrt(prod)


### reduction_coefficient

**Problem:** *~1.3k gas*

Not the most expensive function, but still able to squeeze some savings.

[old/CurveCryptoMath3.vy](/contracts/old/CurveCryptoMath3.vy#L73)

    73 @external
    74 @view
    75 def reduction_coefficient(x: uint256[N_COINS], fee_gamma: uint256) -> uint256:
    76     """
    77     fee_gamma / (fee_gamma + (1 - K))
    78     where
    79     K = prod(x) / (sum(x) / N)**N
    80     (all normalized to 1e18)
    81     """
    82     K: uint256 = 10**18
    83     S: uint256 = 0
    84     for x_i in x:
    85         S += x_i
    86     # Could be good to pre-sort x, but it is used only for dynamic fee,
    87     for x_i in x:
    88         K = K * N_COINS * x_i / S
    89     if fee_gamma > 0:
    90         K = fee_gamma * 10**18 / (fee_gamma + 10**18 - K)
    91     return K


**Solution:** *~500 gas*

Rewritten with a few savings (heavily due to the knowledge that unsafe math functions can be used) cuts gas costs in half.


[CurveCryptoMathOptimized3.vy](/contracts/CurveCryptoMathOptimized3.vy#L667)

    667 @internal
    668 @pure
    669 def _reduction_coefficient(x: uint256[N_COINS], fee_gamma: uint256) -> uint256:
    670 
    671     # fee_gamma / (fee_gamma + (1 - K))
    672     # where
    673     # K = prod(x) / (sum(x) / N)**N
    674     # (all normalized to 1e18)
    675 
    676     K: uint256 = 10**18
    677     S: uint256 = x[0]
    678     S = unsafe_add(S, x[1])
    679     S = unsafe_add(S, x[2])
    680 
    681     # Could be good to pre-sort x, but it is used only for dynamic fee,
    682     # so that is not so important
    683     K = unsafe_div(unsafe_mul(unsafe_mul(K, N_COINS), x[0]), S)
    684     K = unsafe_div(unsafe_mul(unsafe_mul(K, N_COINS), x[1]), S)
    685     K = unsafe_div(unsafe_mul(unsafe_mul(K, N_COINS), x[2]), S)
    686 
    687     if fee_gamma > 0:
    688         K = unsafe_mul(fee_gamma, 10**18) / unsafe_sub(unsafe_add(fee_gamma, 10**18), K)
    689 
    690     return K


## Other Optimizations

- Packing variables into groups helps reduce bytecode space.  This was used for more efficient storage of prices and variables.

[CurveTricryptoFactory.vy](/contracts/CurveTricryptoFactory.vy#L129)

    129 @internal
    130 @view
    131 def _pack(x: uint256[3]) -> uint256:
    132     """
    133     @notice Packs 3 integers with values <= 10**18 into a uint256
    134     @param x The uint256[3] to pack
    135     @return The packed uint256
    136     """
    137     return shift(x[0], 128) | shift(x[1], 64) | x[2]

- Adjustments to logic in storage variables, which created inconsistencies in transaction prices.  This meant sometimes a transaction may cost 21k gas extra, where the next user gets a 21k gf, searchers and aggregators.  The new logic is more consistent:
  - `not_adjusted`: a true/false toggle called in tweak_price — removed completely, thanks to lower rebalancing costs this is no longer necessary.
  - `future_A_gamma_timestamp`: toggled among three different values — new logic for the variable encapsulated in tweak_price
- `remove_liquidity` can empty pool completely.  Previously, the pool could never be completely drained.
- Logic to optimize v2 pools using just two coins, given the pool is now built for 3 coins 


