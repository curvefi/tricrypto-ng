def _check_D(_xp):

    if (
        (min(_xp) * 10**18 // max(_xp) < 10**11)
        or (max(_xp) < 10**9 * 10**18)
        or (max(_xp) > 10**15 * 10**18)
    ):
        return False

    return True


def _check_y(_D, _xp):

    if (
        (_D < 10**17)
        or (_D > 10**15 * 10**18)
        or (min(_xp) * 10**18 // _D < 10**16)
        or (max(_xp) * 10**18 // _D > 10**20)
    ):
        return False

    return True


def check_limits(
    _D, price_scale, xp_0, coin_decimals, amounts, D=True, y=True
):
    """
    Should be good if within limits, but if outside - can be either

    xp_0 = [swap.balances(i) for i in range(N_COINS)]
    """
    xp = xp_0
    xp_0 = [
        x * p // 10**d for x, p, d in zip(xp_0, price_scale, coin_decimals)
    ]
    xp = [
        (x + a) * p // 10**d
        for a, x, p, d in zip(amounts, xp, price_scale, coin_decimals)
    ]

    if D:
        for _xp in [xp_0, xp]:
            if not _check_D(_xp):
                return False

    if y:
        for _xp in [xp_0, xp]:
            if not _check_y(_D, _xp):
                return False

    return True
