# @version 0.3.10

"""
@title CurveExchangeExtendedDemo
@author fiddyresearch.eth
@notice A demo of a strategy execution that swaps on
        Curve pools without granting an ERC20 approvals to the DEX contracts
@dev Only works with Curve Cryptoswap contracts that have `exchange_extended`
     Does not do native token swaps (ETH <> whatever).
"""

from vyper.interfaces import ERC20

interface Swap:
    def exchange_extended(
        i: uint256,
        j: uint256,
        dx: uint256,
        min_dy: uint256,
        use_eth: bool,
        sender: address,
        receiver: address,
        cb: bytes32
    ) -> uint256: nonpayable


vault: public(immutable(address))
keeper: public(immutable(address))
whitelisted_pool: public(immutable(Swap))


@external
def __init__(
    _vault: address,
    _whitelisted_pool: address,
    _keeper: address
):

    vault = _vault
    whitelisted_pool = Swap(_whitelisted_pool)
    keeper = _keeper


@external
def transfer_callback(
    sender: address,
    receiver: address,
    coin: address,
    amount_to_transfer: uint256,
    amount_to_receive: uint256,
):
    """
    Curve CryptoSwap (factory only) pools expect the callback to have the inputs:
        sender: address
        receiver: address
        coin: address
        dx: uint256
        dy: uint256

    The logic of how the callback is handled is:

    ```pool.internal._transfer_in(...):

    b: uint256 = ERC20(_coin).balanceOf(self)
    raw_call(
        callbacker,
        concat(
            slice(callback_sig, 0, 4),
            _abi_encode(sender, receiver, _coin, dx, dy)
        )
    )
    assert ERC20(_coin).balanceOf(self) - b == dx  # dev: callback didn't give us coins
    ```

    The callback fn sig expects several inputs, but we only care about amount_to_transfer.
    Everything else can be simply ignored: or you can use it to do more complex things in
    the callback fn (checks etc.).
    """
    assert msg.sender == whitelisted_pool.address
    assert tx.origin == keeper

    ERC20(coin).transferFrom(vault, whitelisted_pool.address, amount_to_transfer)


@external
def callback_and_swap(
    i: uint256,
    j: uint256,
    dx: uint256,
    min_dy: uint256,
) -> uint256:

    assert msg.sender == keeper

    selector: uint256 = (
        convert(
            method_id(
                "transfer_callback(address,address,address,uint256,uint256)"
            ),
            uint256
        ) << 224
    )

    return whitelisted_pool.exchange_extended(
        i,  # input coin index
        j,  # output coin index
        dx,  # amount in
        min_dy,  # minimum expected out
        False,   # use native token (eth)
        msg.sender, # sender  (doesnt matter because we set it to the vault in the callback)
        vault, # receiver
        convert(selector, bytes32)  # <-- your callback is being called here
    )
