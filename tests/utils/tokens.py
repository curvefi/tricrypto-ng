def mint_for_testing(token_contract, address_to_mint_for, amount):

    token_contract.eval(f"self.totalSupply += {amount}")
    token_contract.eval(f"self.balanceOf[{address_to_mint_for}] += {amount}")
