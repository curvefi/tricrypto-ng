# Curve TriCrypto Factory

This github contains smart contracts (and accompanying tests) on an optimised version of [Curve Finance](https://curve.exchange/) [Tricrypto pool](https://etherscan.io/address/0xd51a44d3fae010294c616388b506acda1bfaae46) deployed on Ethereum.

The AMM (automatic market maker) infrastructure involves the following parts:

1. Factory
2. AMM blueprint contract
3. Math
4. Views
5. Liquidity Gauge blueprint contract

The Factory can accommodate multiple blueprints of the AMM contract (deployed on chain). These blueprints are then specified by the user while deploying the pool. Similarly, liquidity gauges can be deployed through the factory contract as well for a specific pool, through liquidity gauge blueprint contracts.

The AMM is a 3-coin, auto-rebalancing Curve Cryptoswap implementation with several optimisations that make the contract cheaper for the end user. Also, unlike the older version: the pool contract is an ERC20-compliant LP token as well.

The Math contract contains the different math functions used in the AMM.

The Views contract contains view methods relevant for integrators and users looking to interact with the AMMs. Unlike the older tricrypto contracts. The address of the deployed Views contract is stored in the Factory: users are advised to query the stored views contract, since that is upgradeable by the Factory's admin.

The Factory AMMs have a hardcoded `ADMIN_FEE`, set to 50% of the earned profits. Factory admins can also implement parameter changes to the AMMs, change the fee recepient, upgrade/add blueprint contract addresses stored in the factory. Unlike the original tricrypto contracts, Factory tricrypto contracts cannot be killed by the admin.

In case of any issues that result in a borked AMM state, users can safely withdraw liquidity using `remove_liquidity` at balances proportional to the AMM balances.

# TriCrypto versions overview


The different implementations of Curve's CryptoSwap invariant AMM are noted in the following:

0. The genesis cryptoswap invariant amm contracts:

    a. [tricrypto2 (genesis)](https://github.com/curvefi/curve-crypto-contract/blob/master/contracts/tricrypto/CurveCryptoSwap.vy)

    b. [twocrypto (genesis)](https://github.com/curvefi/curve-crypto-contract/blob/master/contracts/two/CurveCryptoSwap2ETH.vy)
1. [TricryptoNGWETH (1st gen)](https://github.com/curvefi/tricrypto-ng/blob/main/contracts/main/CurveTricryptoOptimizedWETH.vy)
2. [TwocryptoNG (second gen)](https://github.com/curvefi/twocrypto-ng/blob/main/contracts/main/CurveTwocryptoOptimized.vy)
3. [TricryptoNG (second gen)](https://github.com/curvefi/tricrypto-ng/blob/main/contracts/main/CurveTricryptoOptimized.vy)

### From genesis to NG 1st gen


There are significant improvements from the genesis cryptoswap invariant AMM contract to the 1st gen (NG, or next gen). Gas costs are reduced by half between the genesis and the first gen implementations. This was a labor of love, requiring development work in the compiler, dev tools (titanoboa was basically built to build tricryptong), coordination with etherscan, coordination with math researchers to optimise math in tricrypto, come up with better cube roots, auditors coming up with their own optimisations etc. The optimisations are listed in the following:

1. Replace [Bubble sort](https://github.com/curvefi/curve-crypto-contract/blob/d7d04cd9ae038970e40be850df99de8c1ff7241b/contracts/tricrypto/CurveCryptoMath3.vy#L20) with [dumb sorting](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveCryptoMathOptimized3.vy#L845)
2. [Bespoke cube root algorithm that costs 2000 gas on average](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveCryptoMathOptimized3.vy#L789). Implemented in [Snekmate](https://github.com/pcaversaccio/snekmate/blob/9f7eec740fcaf8e5d4397fc1cc79d507ff11d613/src/snekmate/utils/Math.vy#L490) as well.
3. Replace [expensive geometric mean](https://github.com/curvefi/curve-crypto-contract/blob/d7d04cd9ae038970e40be850df99de8c1ff7241b/contracts/tricrypto/CurveCryptoMath3.vy#L42) with [simple geometric mean](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveCryptoMathOptimized3.vy#L868)
4. Use unsafe math operations wherever it is safe to do so. [Old implementation](https://github.com/curvefi/curve-crypto-contract/blob/d7d04cd9ae038970e40be850df99de8c1ff7241b/contracts/tricrypto/CurveCryptoMath3.vy#L96) -> [new implementation with explanation for why we can do unsafe maths](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveCryptoMathOptimized3.vy#L431)
5. Replace [newton_y](https://github.com/curvefi/curve-crypto-contract/blob/d7d04cd9ae038970e40be850df99de8c1ff7241b/contracts/tricrypto/CurveCryptoMath3.vy#L172) for [mathematically verified analytical solution with fallback to newton method for edge cases](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveCryptoMathOptimized3.vy#L35).
6. [Bespoke and very cheap calculation of partial derivatives of x w.r.t y, which allows the calculation of state prices](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveCryptoMathOptimized3.vy#L539). This was a contribution from Taynan Richards of ChainSecurity, which [replaced the old and initially proposed version](https://github.com/curvefi/tricrypto-ng/commit/b3350d4b7e92d4e12720584b2d1aeb1d74b5a99f).
7. Introduce [Blueprint contracts](https://eips.ethereum.org/EIPS/eip-5202). This allowed factory deployed contracts to have immutables, since blueprint contracts are not like minimal proxies where immutables are not possible whatsoever. 

The implementation of state prices allowed the creation of very good oracles that power today's curve stablecoin. State prices, as opposed to last traded prices which every other AMM or oracle uses, reduce the impact of price manipulation significantly.

[TricryptoNGWETH](contracts/main/CurveTricddryptoOptimizedWETH.vy) is the first optimised implementation of the old 3-coin cryptoswap AMM which allowed native token transfers. 

### From NG 1st gen to NG 2nd gen
 
Cryptoswap (like everything Curve has) is an ongoing process of improvement. It's immediate upgrade (almost a year or so after it's launch) removes some of the features and adds new ones. The features added in the second iteration of NG are simply features that come out of a natural progression of improving contracts after user feedback, experiences with speaking to auditors etc. There are no known vulnerabilities in the first NG implementation that prompted the second iteration of cryptoswap NG contracts.

Some of the features removed from the first gen (in the second gen) are (not exhaustive list):

1. [Native token transfers](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimizedWETH.vy#L394)
2. [Gulping of tokens (i.e. when the `self.balances` can be updated with a read of `coin.balanceOf(self)`).](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimizedWETH.vy#L1193)
3. [exchange_extended, which is exchanging after calling an external callback first).](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimizedWETH.vy#L477)
4. [Admin fees collected in LP tokens.](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimizedWETH.vy#L1223)
5. [exposed claim_admin_fees](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimizedWETH.vy#L786)
6. [commit-apply scheme for parameters](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimizedWETH.vy#L2033). New version simply applies parameters [which is quicker to do](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimized.vy#L1994) (in one tx after governance approves).

The second gen adds several new features including:

1. [An xcp oracle to measure the amount of liquidity in the pool](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimized.vy#L1705)
2. [fees are collected in individual tokens and not lp tokens.](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimized.vy#L1216)
3. [Claiming individual tokens means LP token supply does not go up](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimized.vy#L1173)
4. stricter conditions to claiming fees

    a. [claim sparingly](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimized.vy#L1116)

    b. [do not claim in vprice goes below 1e18](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimized.vy#L1182)
5. [exchange_received](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimized.vy#L409): swap tokens donated to the pool.The advantage of the new implementation is that, if tokens in the pool are rebasing, there is no `self.balances[i] = coins[i].balanceOf(self)` in the `self._claim_admin_fees()` method [like the old contract does](https://github.com/curvefi/tricrypto-ng/blob/33707fc8b84e08786acf184fcfdb744eb4657a99/contracts/main/CurveTricryptoOptimizedWETH.vy#L1197)

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

Please check [./deployments.yaml][the deployments file to get addresses for deployed contracts.]

### License

(c) Curve.Fi, 2023 - [All rights reserved](LICENSE).
