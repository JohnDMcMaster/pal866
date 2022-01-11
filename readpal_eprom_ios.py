#!/usr/bin/env python3

"""
Determine IOs and then only read that combination
"""

from otl866 import bitbang, util
from pal866 import readpal
from otl866.util import hexdump
import json
        
def run(port=None, fnout=None, j_fn=None, tl866_verbose=False, verbose=False):
    tl = bitbang.Bitbang(port, verbose_cmd=tl866_verbose)
    rp = readpal.Readpal(tl, verbose=verbose)
    buf, j = rp.read_eprom_ios()
    if j_fn:
        open(j_fn, 'w').write(json.dumps(j, indent=4, sort_keys=True))
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
    parser.add_argument("--json", help="Also save IOs metadata")
    parser.add_argument("fnout", nargs='?')
    args = parser.parse_args()

    run(port=args.port, fnout=args.fnout, j_fn=args.json, tl866_verbose=args.tl866_verbose, verbose=args.verbose)


if __name__ == "__main__":
    main()
