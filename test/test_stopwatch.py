from home.util import Stopwatch, StopwatchError
from time import sleep


if __name__ == '__main__':
    s = Stopwatch()
    s.go()
    sleep(2)
    s.pause()
    s.go()
    sleep(1)
    print(s.get_elapsed_time())
    sleep(1)
    print(s.get_elapsed_time())
    s.pause()
    print(s.get_elapsed_time())
