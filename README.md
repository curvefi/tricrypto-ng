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
