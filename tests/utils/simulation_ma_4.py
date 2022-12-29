#!/usr/bin/env python3
# flake8: noqa
import json
from decimal import Decimal


def reduction_coefficient(x, gamma):
    x_prod = 1.0
    N = len(x)
    for x_i in x:
        x_prod *= x_i
    K = x_prod / sum(x) ** N * N**N
    if gamma > 0:
        K = gamma / (gamma + (1 - K))
    return K


def absnewton(f, fprime, x0, handle_x=False, handle_D=False):
    x = x0
    i = 0
    while True:
        x_prev = x
        _f = f(x)
        _fprime = fprime(x)
        x -= _f / _fprime

        # XXX vulnerable to edge-cases
        # Need to take out of unstable equilibrium if ever gets there
        # Might be an issue in smart contracts
        if handle_x:
            if x < 0 or _fprime < 0:
                x = x_prev / 2
        elif handle_D:
            if x < 0:
                x = -x / 2

        i += 1
        if i > 1000:  # XXX
            print(i, (x - x_prev) / x_prev)
        if abs(x - x_prev) < x_prev * 1e-12:
            return x


def inv_target(A, gamma, x, D):
    N = len(x)

    x_prod = 1.0
    for x_i in x:
        x_prod *= x_i
    K0 = x_prod / (D / N) ** N

    if gamma > 0:
        K = gamma**2 * K0 / (gamma + 10**18 * (1.0 - K0)) ** 2
    K *= A

    f = K * D ** (N - 1) * sum(x) + x_prod - (K * D**N + (D / N) ** N)
    return f


def inv_target_decimal(A, gamma, x, D):
    N = len(x)

    x_prod = Decimal(1)
    for x_i in x:
        x_prod *= x_i
    K0 = x_prod / (Decimal(D) / N) ** N
    K0 *= 10**18

    if gamma > 0:
        # K = gamma**2 * K0 / (gamma + 10**18*(Decimal(1) - K0))**2
        K = gamma**2 * K0 / (gamma + 10**18 - K0) ** 2 / 10**18
    K *= A

    f = (
        K * D ** (N - 1) * sum(x)
        + x_prod
        - (K * D**N + (Decimal(D) / N) ** N)
    )
    return f


def inv_dfdD(A, gamma, x, D):
    N = len(x)

    x_prod = 1.0
    for x_i in x:
        x_prod *= x_i
    K0 = x_prod / (D / N) ** N
    K0deriv = -N / D * K0

    if gamma > 0:
        K = gamma**2 * K0 / (gamma + (1 - K0)) ** 2
        Kderiv = (
            2 * gamma**2 * K0 / (gamma + (1 - K0)) ** 3
            + gamma**2 / (gamma + (1 - K0)) ** 2
        ) * K0deriv
    else:
        K = K0
        Kderiv = K0deriv
    K *= A
    Kderiv *= A

    return (
        sum(x) * D ** (N - 2) * (Kderiv * D + K * (N - 1))
        - D ** (N - 1) * (Kderiv * D + K * N)
        - (D / N) ** (N - 1)
    )


def inv_dfdxi(A, gamma, x, D, i):
    N = len(x)
    x_prod = 1.0
    x_prod_i = 1.0
    for j, x_i in enumerate(x):
        x_prod *= x_i
        if j != i:
            x_prod_i *= x_i
    K0 = x_prod / (D / N) ** N
    K0deriv = x_prod_i / (D / N) ** N
    if gamma:
        K = gamma**2 * K0 / (gamma + (1 - K0)) ** 2
        Kderiv = (
            2 * gamma**2 * K0 / (gamma + (1 - K0)) ** 3
            + gamma**2 / (gamma + (1 - K0)) ** 2
        ) * K0deriv
    else:
        K = K0
        Kderiv = K0deriv
    K *= A
    Kderiv *= A

    return D ** (N - 1) * (K + sum(x) * Kderiv) + x_prod_i - D**N * Kderiv


def solve_x(A, gamma, x, D, i, method="newton"):
    prod_i = 1.0
    for j, _x in enumerate(x):
        if j != i:
            prod_i *= _x

    def f(x_i):
        xx = x[:]
        xx[i] = x_i
        return inv_target(A, gamma, xx, D)

    def f_der(x_i):
        xx = x[:]
        xx[i] = x_i
        return inv_dfdxi(A, gamma, xx, D, i)

    try:
        result = absnewton(f, f_der, (D / 2) ** len(x) / prod_i, handle_x=True)
    except KeyboardInterrupt:
        print("x")
        raise
    return result


def solve_D(A, gamma, x):
    f = lambda D: inv_target(A, gamma, x, D)
    f_der = lambda D: inv_dfdD(A, gamma, x, D)

    D0 = 1
    for _x in x:
        D0 *= _x
    D0 = D0 ** (1 / len(x)) * len(x)
    try:
        return absnewton(f, f_der, D0, handle_D=True)
    except KeyboardInterrupt:
        print("D")
        raise


class Curve:
    def __init__(self, A, gamma, D, n, p=None):
        self.A = A
        self.gamma = gamma
        self.n = n
        if p:
            self.p = p
        else:
            self.p = [10**18] * n
        self.x = [D // n * 10**18 // self.p[i] for i in range(n)]

    def xp(self):
        return [x * p // 10**18 for x, p in zip(self.x, self.p)]

    def D(self):
        xp = self.xp()
        if any(x <= 0 for x in xp):
            raise ValueError
        return int(solve_D(self.A, self.gamma, xp))

    def cp_invariant(self):
        prod = 10**18
        for x in self.x:
            prod = x * prod // 10**18
        return prod

    def y(self, x, i, j):
        xp = self.xp()
        xp[i] = x * self.p[i] // 10**18
        yp = solve_x(self.A, self.gamma, xp, self.D(), j)
        return int(yp) * 10**18 // self.p[j]


def get_ethbtc():
    # with open('download/crvusdt.json', 'r') as f:
    with open("download/ethbtc.json", "r") as f:
        return [
            {
                "open": float(t[1]),
                "high": float(t[2]),
                "low": float(t[3]),
                "close": float(t[4]),
                "t": t[0] // 1000,
                "volume": float(t[5]),
                "pair": (0, 1),
            }
            for t in json.load(f)
        ]
    # Volume is in ETH


def get_all():
    # btc - 0
    # eth - 1
    btceth = get_ethbtc()
    out = []
    for trade in btceth:
        trade["pair"] = (0, 1)
        out.append((trade["t"], trade))
    out = sorted(out)
    return [i[1] for i in out]


def plot_sample():
    import numpy as np
    import pylab

    c = Curve(100, 0.1, 10**18, 2, p=[10**18, 2 * 10**18])
    X = np.logspace(-2, 1) * 1e18
    Y = [c.y(x, 0, 1) for x in X]
    pylab.plot(X, Y)
    pylab.show()


class Trader:
    def __init__(
        self,
        A,
        gamma,
        D,
        n,
        p0,
        mid_fee=1e-3,
        out_fee=3e-3,
        price_threshold=0.01,
        fee_gamma=None,
        log=True,
    ):
        self.p0 = p0
        self.curve = Curve(A, gamma, D, n, p=[10**18, int(p0 * 10**18)])
        self.Amax = A
        self.dx = int(D * 1e-8)
        self.mid_fee = mid_fee
        self.out_fee = out_fee
        self.D0 = self.curve.D()
        self.xcp_0 = self.get_xcp()
        self.xcp_profit = 1.0
        self.xcp_profit_real = 1.0
        self.xcp = self.xcp_0
        self.price_threshold = price_threshold
        self.adjustment_step = 3e-3
        self.log = log
        self.fee_gamma = fee_gamma or gamma
        self.total_vol = 0.0
        self.ext_fee = 0  # 0.03e-2
        self.slippage = []

    def fee(self):
        f = reduction_coefficient(self.curve.xp(), self.fee_gamma)
        return self.mid_fee**f * self.out_fee ** (1 - f)  # <- prod
        # return self.mid_fee * f + self.out_fee * (1 - f)  # <- sum

    def price(self, i, j):
        dx_raw = self.dx * 10**18 // self.curve.p[i]
        return dx_raw / (
            self.curve.x[j] - self.curve.y(self.curve.x[i] + dx_raw, i, j)
        )

    def step_for_price(self, dp, sign=1):
        p0 = self.price(0, 1)
        x0 = self.curve.x[:]
        step = self.dx
        while True:
            self.curve.x[0] = x0[0] + sign * step
            dp_ = abs(p0 - self.price(0, 1))
            if dp_ >= dp or step >= 0.1 * self.curve.x[0]:
                self.curve.x = x0
                self.slippage.append(step / dp_)
                return step
            step *= 2

    def get_xcp(self):
        # First calculate the ideal balance
        # Then calculate, what the constant-product would be
        D = self.curve.D()
        N = len(self.curve.x)
        X = [D * 10**18 // (N * p) for p in self.curve.p]
        prod = 1
        for x in X:
            prod = prod * x
        return int(prod ** (1 / N))

    def update_xcp(self, only_real=False):
        xcp = self.get_xcp()
        mul = xcp / self.xcp
        self.xcp_profit_real *= mul
        if not only_real:
            self.xcp_profit *= mul
        self.xcp = xcp

    def buy(self, dx, i, j, max_price=1e100):
        """
        Buy y for x
        """
        try:
            fee = self.fee()
            x_old = self.curve.x[:]
            x = self.curve.x[i] + dx
            y = self.curve.y(x, i, j)
            dy = self.curve.x[j] - y
            self.curve.x[i] = x
            self.curve.x[j] = y + int(dy * fee)
            dy = int(dy * (1 - fee))
            if dx / dy > max_price or dy < 0:
                self.curve.x = x_old
                return False
            self.update_xcp()
            return dy
        except ValueError:
            return False

    def sell(self, dy, i, j, min_price=0):
        """
        Sell y for x
        """
        try:
            fee = self.fee()
            x_old = self.curve.x[:]
            y = self.curve.x[j] + dy
            x = self.curve.y(y, j, i)
            dx = self.curve.x[i] - x
            self.curve.x[i] = x + int(dx * fee)
            self.curve.x[j] = y
            dx = int(dx * (1 - fee))
            if dx / dy < min_price or dx < 0:
                self.curve.x = x_old
                return False
            self.update_xcp()
            return dx
        except ValueError:
            return False

    def tweak_price(self, last_price):
        dp = last_price / (self.curve.p[1] / 1e18) - 1
        old_p = self.curve.p[:]
        old_profit = self.xcp_profit_real
        old_xcp = self.xcp

        env_threshold = 1  # - 1 / (1 + (dp / self.price_threshold)**2)
        _threshold = self.adjustment_step * env_threshold
        # if dp > _threshold:
        if dp > self.price_threshold:
            # pump it
            self.curve.p[1] = int((1 + _threshold) * self.curve.p[1])
            self.update_xcp(only_real=True)

        # elif dp < -_threshold:
        elif dp < -self.price_threshold:
            # dump it
            self.curve.p[1] = int((1 - _threshold) * self.curve.p[1])
            self.update_xcp(only_real=True)

        if 2 * (self.xcp_profit_real - 1) <= self.xcp_profit - 1:
            self.curve.p = old_p
            self.xcp_profit_real = old_profit
            self.xcp = old_xcp

    def simulate(self, mdata):
        last = self.p0
        avg = last
        for i, d in enumerate(mdata):
            a, b = d["pair"]
            vol = 0
            ext_vol = int(d["volume"] * 1e18)
            ctr = 0
            _high = last
            _low = last

            # Dynamic step
            # f = reduction_coefficient(self.curve.xp(), self.curve.gamma)
            candle = min(
                max(self.mid_fee, abs((d["high"] - d["low"]) / d["high"])), 0.1
            )
            step1 = self.step_for_price(candle * 0.002, sign=1)
            step2 = self.step_for_price(candle * 0.002, sign=-1)
            step = min(step1, step2)
            # step = int(self.D0 * self.p0 ** .5 * candle * 0.0005 * (1**f * self.curve.A ** (1-f)))

            max_price = d["high"]
            while last < max_price and vol < ext_vol / 2:
                dy = self.buy(step, a, b, max_price=max_price)
                if dy is False:
                    break
                vol += dy
                last = step / dy
                max_price = d["high"]
                ctr += 1
            _high = last
            min_price = d["low"]
            while last > min_price and vol < ext_vol / 2:
                dy = self.sell(int(step / last), a, b, min_price=min_price)
                if dy is False:
                    break
                vol += int(step / last)
                last = dy / int(step / last)
                min_price = d["low"]
                ctr += 1
            _low = last
            avg = avg * 0.8 + (_high + _low) / 2 * 0.2  # MA price
            if ctr > 0:
                self.tweak_price(avg)
            self.total_vol += vol
            if self.log:
                try:
                    print(
                        "{0}\ttrades: {1}\tAMM: {2:.6f}\tTarget: {3:.6f}\tVol: {4:.4f}\tPR: {5: .2f}\txCP-growth: {6:.5f}\tAPY:{7:.1f}%\tfee:{8:.3f}%".format(
                            i,
                            ctr,
                            last,
                            self.curve.p[1] / 1e18,
                            self.total_vol / 1e18,
                            (self.xcp_profit_real - 1) / (self.xcp_profit - 1),
                            self.xcp_profit_real,
                            (
                                self.xcp_profit_real
                                ** (86400 * 365 / (d["t"] - mdata[0]["t"] + 1))
                                - 1
                            )
                            * 100,
                            self.fee() * 100,
                        )
                    )
                except Exception:
                    pass


if __name__ == "__main__":
    test_data = get_all()
    print(test_data[-1])

    trader = Trader(
        100,
        1.5e-4,
        10**18,
        2,
        test_data[0]["close"],
        mid_fee=0.7e-3,
        out_fee=4.0e-3,
        price_threshold=0.004,
        fee_gamma=0.01,
    )

    # trader = Trader(1000, 0.00004, 10**18, 2, test_data[0]['close'], mid_fee=1e-3, out_fee=4.0e-3, price_threshold=0.0039,
    #                 fee_gamma=0.01)

    # trader = Trader(20000, 0.5e-4, 10**18, 2, test_data[0]['close'], mid_fee=1.2e-3, out_fee=4.0e-3, price_threshold=0.013,
    #                 fee_gamma=1e-2)

    # trader = Trader(5000, 3e-4, 10**18, 2, test_data[0]['close'], mid_fee=1.2e-3, out_fee=4.0e-3, price_threshold=0.013,
    #                 fee_gamma=1e-2)

    # crv
    # trader = Trader(40, 2e-9, 10**18, 2, test_data[0]['close'], mid_fee=4e-3, out_fee=10.0e-3, price_threshold=0.05,
    #                 fee_gamma=2e-6)
    print(trader.price(0, 1))

    trader.simulate(test_data)
    import IPython

    IPython.embed()
