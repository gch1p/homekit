import time


def poll_tick(freq):
    t = time.time()
    while True:
        t += freq
        yield max(t - time.time(), 0)
