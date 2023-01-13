import boa


def _commit_accept_params(swap, admin, params):

    with boa.env.prank(admin):
        swap.commit_new_parameters(**params)
        boa.env.time_travel(3 * 86400 + 1)
        swap.apply_new_parameters()


def test_revert_apply_params_before_deadline(swap, factory_admin):

    pass


def def_test_change_mid_fee(swap, factory_admin):

    current_fee_params = swap.internal._unpack(
        swap._storage.packed_fee_params.get()
    )

    return (
        current_fee_params[0] - 1,  # _new_mid_fee
        current_fee_params[1] - 1,  # _new_out_fee
        current_fee_params[2] - 1,  # _new_fee_gamma
    )
