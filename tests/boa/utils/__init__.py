from math import log


def approx(x1, x2, precision):
    return abs(log(x1 / x2)) <= precision
