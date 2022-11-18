import boa


def boa_sleep(sleep_time):
    boa.env.vm.patch.timestamp += sleep_time
    boa.env.vm.patch.block_number += sleep_time // 12
