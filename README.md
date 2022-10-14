# Curve TriCrypto

This github contains smart contracts (and accompanying tests) on an optimised version of [Curve Finance](https://curve.exchange/) [Tricrypto pool](https://etherscan.io/address/0xd51a44d3fae010294c616388b506acda1bfaae46).

# Roadmap

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

### Roadmap

- [ ] Add further math optimisations to CurveCryptoMathOptimized.vy
- [ ] Port brownie tests to pytest
- [ ] Check CurveTricryptoOptimized.vy contract for optimisations
- [ ] Add oracle to tricrypto swap contract
- [ ] Report gas profiles
- [ ] Deployment scripts
- [ ] Deploy

<p align="right">(<a href="#readme-top">back to top</a>)</p>

# Deployments

To be deployed (TBD) ...

### License

(c) Curve.Fi, 2022 - [All rights reserved](LICENSE).
