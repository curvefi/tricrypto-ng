# Curve TriCrypto Factory

This github contains smart contracts (and accompanying tests) on an optimised version of [Curve Finance](https://curve.exchange/) [Tricrypto pool](https://etherscan.io/address/0xd51a44d3fae010294c616388b506acda1bfaae46) deployed on Ethereum.

The AMM (automatic market maker) infrastructure involves the following parts:

1. Factory
2. AMM blueprint contract
3. Math
4. Views
5. Liquidity Gauge blueprint contract

The Factory can accommodate multiple blueprints of the AMM contract (deployed on chain). These blueprints are then specified by the user while deploying the pool. Similarly, liquidity gauges can be deployed through the factory contract as well for a specific pool, through liquidity gauge blueprint contracts.

The AMM is a 3-coin, auto-rebalancing Curve Cryptoswap implementation. The contract is a version 2.0.0, with several optimisations that make the contract cheaper for the end user. Also, unlike the older version: the pool contract is an ERC20-compliant LP token as well.

The Math contract contains the different math functions used in the AMM.

The Views contract contains view methods relevant for integrators and users looking to interact with the AMMs. Unlike the older tricrypto contracts. The address of the deployed Views contract is stored in the Factory: users are advised to query the stored views contract, since that is upgradeable by the Factory's admin.

The Factory AMMs have a hardcoded `ADMIN_FEE`, set to 50% of the earned profits. Factory admins can also implement parameter changes to the AMMs, change the fee recepient, upgrade/add blueprint contract addresses stored in the factory. Unlike the original tricrypto contracts, Factory tricrypto contracts cannot be killed by the admin.

In case of any issues that result in a borked AMM state, users can safely withdraw liquidity using `remove_liquidity` at balances proportional to the AMM balances.

# Change Notes
The organizing principle of TriCrypto: Next Generation is to improve gas efficiency and user experience while maintaining readability to the end user.  The changes introduced throughout were documented robustly, with further notes placed into this README file.

![Gas Profile](https://user-images.githubusercontent.com/13426766/219870036-34e6d55a-c094-47ea-8b67-334e6853095a.png)

## AMM Improvements

### ERC20 Compatibility

**Problem:** Earlier Curve pools would separate the pool (for depositing and transacting) and the LP token into separate contracts.  In addition to being occasionally confusing, this also increases gas costs when the pool has to make external calls.

[![TriCrypto Separate Pool and Token](https://user-images.githubusercontent.com/13426766/219870168-4fd73196-4aa8-4009-ad3f-9e20f21f9f60.png)](https://curve.fi/#/ethereum/pools/tricrypto2/deposit)

**Solution:** Bringing the LP token logic into the pool contract has been done with more modern Curve pools to great effect and is done so here in the new TriCrypto:

[![ERC20 Compatibility](https://user-images.githubusercontent.com/13426766/219871966-8b028651-0e4d-483a-a10e-fe5b25afd4d1.png)](/contracts/CurveTricryptoOptimizedWETH.vy)

### Permit Method

Add a `permit()` method for gasless approvals

[![Vyper permit method](https://user-images.githubusercontent.com/13426766/219872009-93a8dc00-b3fc-461b-b357-06be4ab16c87.png)](/contracts/CurveTricryptoOptimizedWETH.vy#L1480)

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

[![Vyper former square root function](https://user-images.githubusercontent.com/13426766/219870584-094dd49f-b6c9-4d7c-9315-691ee682bced.png)](/contracts/old/CurveCryptoMath3.vy#L307)

**Solution:** *~450 gas*

Created a new [cheap isqrt() function built into Vyper 3.7](https://github.com/vyperlang/vyper/pull/3069)

[![Vyper optimized cheap isqrt function](https://user-images.githubusercontent.com/13426766/219870884-260ae167-5dd0-40b9-8c0d-26154f2fa939.png)](https://github.com/vyperlang/vyper/pull/3069)

The inspiration in this case came from [t11s’s solmate](https://github.com/Gaussian-Process/solmate/blob/837de01395312eb89e607fdc64fb7bb9c03207c3/src/utils/FixedPointMathLib.sol) and ported to Vyper.

### Cube Root

**Problem:** *~40K Gas*

Expensive iterative process in `newton_y` 

[![Vyper iterative newton_y](https://user-images.githubusercontent.com/13426766/219872070-f8dff5bd-e641-4a5e-a153-c1515a64a91b.png)](/contracts/old/CurveCryptoMath3.vy#L180)

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

[![Vyper insertion sort](https://user-images.githubusercontent.com/13426766/219871232-28d07351-3d7e-4455-a2cb-185c6549eb7d.png)](/contracts/old/CurveCryptoMath3.vy#L19)

**Solution:** *~400 gas*

In this rare case, dumbing things down proved to be better.  [Brute forcing the results](/contracts/CurveCryptoMathOptimized3.vy#L831) resulted in significant gas savings.

[![Vyper Brute Force Sort](https://user-images.githubusercontent.com/13426766/219872476-a44bd9c3-bab1-4588-ae41-a98050dbbffa.png)](/contracts/CurveCryptoMathOptimized3.vy#L831)


### Half Power

**Problem:** *~10k gas*

The former custom method of raising to a number to the 0.5 power required an expensive iterative loop.

[![Vyper half power unoptimized](https://user-images.githubusercontent.com/13426766/219871338-f9949769-bd1f-4a16-ab83-44d46028b81d.png)](/contracts/old/CurveCryptoMath3.vy#L268)

**Solution:** *~800 gas*

Using the exponent method, again [inspired by solmate](https://github.com/transmissions11/solmate/blob/main/src/utils/SignedWadMath.sol), makes it significantly cheaper to calculate exponents.  This method used frequently when calculating the weights for moving average prices, because crypto is so volatile. 

[![Vyper half power optimized](https://user-images.githubusercontent.com/13426766/219872558-66298a0e-79de-43e2-b8ca-a55adb613460.png)](https://github.com/curvefi/tricrypto-ng/blob/main/contracts/CurveTricryptoOptimizedWETH.vy#L976)

### Geometric Mean

**Problem:** *~21k gas*

One of the more expensive functions, [which required a loop through 255 elements](/contracts/old/CurveCryptoMath3.vy#L41).

[![Vyper Geometric Mean 255 element loop](https://user-images.githubusercontent.com/13426766/219871461-71eb0122-69fd-45d0-89f1-76a8779236f1.png)](/contracts/old/CurveCryptoMath3.vy#L41)

**Solution:** 

Using the cube root function described above provides a savings.

[![Vyper cube root geometric mean](https://user-images.githubusercontent.com/13426766/219871577-a4403f3c-0818-4f7e-8c57-0a5ea068c100.png)](/contracts/CurveCryptoMathOptimized3.vy#L854)


### reduction_coefficient

**Problem:** *~1.3k gas*

Not the most expensive function, but still able to squeeze some savings.

[![Vyper unoptimized reduction_coefficient](https://user-images.githubusercontent.com/13426766/219871599-f0f62684-1015-40a2-8436-b004f1b05d09.png)](/contracts/old/CurveCryptoMath3.vy#L73)


**Solution:** *~500 gas*

Rewritten with a few savings (heavily due to the knowledge that unsafe math functions can be used) cuts gas costs in half.

[![Vyper optimized reduction_coeffficient](https://user-images.githubusercontent.com/13426766/219871643-260eb2d3-895e-4320-b4df-85459627439e.png)](/contracts/CurveCryptoMathOptimized3.vy#L667)


## Other Optimizations

- Packing variables into groups helps reduce bytecode space.  This was used for more efficient storage of prices and variables.

[![Vyper variable packing](https://user-images.githubusercontent.com/13426766/219871814-ec2a0bdd-c740-4448-ac80-8827b5e07086.png)](/contracts/CurveTricryptoFactory.vy#L129)

- Adjustments to logic in storage variables, which created inconsistencies in transaction prices.  This meant sometimes a transaction may cost 21k gas extra, where the next user gets a 21k gf, searchers and aggregators.  The new logic is more consistent:
  - `not_adjusted`: a true/false toggle called in tweak_price — removed completely, thanks to lower rebalancing costs this is no longer necessary.
  - `future_A_gamma_timestamp`: toggled among three different values — new logic for the variable encapsulated in tweak_price
- `remove_liquidity` can empty pool completely.  Previously, the pool could never be completely drained.
- Logic to optimize v2 pools using just two coins, given the pool is now built for 3 coins 


----

# For developers

### To run tests:

```
> python -m pytest
```

### To contribute

In order to contribute, please fork off of the `main` branch and make your changes there. Your commit messages should detail why you made your change in addition to what you did (unless it is a tiny change).

If you need to pull in any changes from `main` after making your fork (for example, to resolve potential merge conflicts), please avoid using `git merge` and instead, `git rebase` your branch

Please also include sufficient test cases, and sufficient docstrings. All tests must pass before a pull request can be accepted into `main`

### Smart Contract Security Vulnerability Reporting

Please refrain from reporting any smart contract vulnerabilities publicly. The best place to report first is [security@curve.fi](mailto:security@curve.fi).

# Deployments

To be deployed (TBD) ...

### License

(c) Curve.Fi, 2023 - [All rights reserved](LICENSE).
