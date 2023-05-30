from copy import deepcopy

import boa
import pytest
from eth_account import Account as EthAccount
from eth_account._utils.structured_data.hashing import (
    hash_domain,
    hash_message,
)
from eth_account.messages import SignableMessage
from hexbytes import HexBytes


@pytest.fixture(scope="module")
def sign_permit():
    def _sign_permit(swap, owner, spender, value, deadline):

        PERMIT_STRUCT = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                    {"name": "salt", "type": "bytes32"},
                ],
                "Permit": [
                    {"name": "owner", "type": "address"},
                    {"name": "spender", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            "primaryType": "Permit",
        }

        struct = deepcopy(PERMIT_STRUCT)
        struct["domain"] = dict(
            name=swap.name(),
            version=swap.version(),
            chainId=boa.env.vm.chain_context.chain_id,
            verifyingContract=swap.address,
            salt=HexBytes(swap.salt()),
        )
        struct["message"] = dict(
            owner=owner.address,
            spender=spender,
            value=value,
            nonce=swap.nonces(owner.address),
            deadline=deadline,
        )
        signable_message = SignableMessage(
            b"\x01", hash_domain(struct), hash_message(struct)
        )
        return EthAccount.sign_message(signable_message, owner._private_key)

    return _sign_permit
