#!/usr/bin/env python3

"""
Use readpal to do basic EPROM style read
Slow, about 23 minutes
Demo app, although useful if we can optimize speed
"""

from otl866 import bitbang, util
from pal866 import readpal
from otl866.util import hexdump

        
def run(port=None, fnout=None, tl866_verbose=False, verbose=False):
    tl = bitbang.Bitbang(port, verbose_cmd=tl866_verbose)
    rp = readpal.Readpal(tl, verbose=verbose)
    buf = rp.read_eprom()
    if fnout:
        open(fnout, "wb").write(buf)
    else:
        hexdump(buf)

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Read a PAL device as a 27C020 EPROM into a .bin file')
    parser.add_argument('--port',
                        default=util.default_port(),
                        help='Device serial port')
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--tl866-verbose", action="store_true")
    parser.add_argument("fnout", nargs='?')
    args = parser.parse_args()

    run(port=args.port, fnout=args.fnout, tl866_verbose=args.tl866_verbose, verbose=args.verbose)


if __name__ == "__main__":
    main()
