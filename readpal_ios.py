#!/usr/bin/env python3

"""
Switch weak pullup / pulldown resistors on address lines
Correlated changes to data bus to determine if pins are actively driven
Will work for simple chips:
-Combintorial logic only
-No tristate logic
"""

from otl866 import bitbang, util
from pal866 import readpal
import json
        
def run(port=None, fnout=None, tl866_verbose=False, verbose=False):
    tl = bitbang.Bitbang(port, verbose_cmd=tl866_verbose)
    rp = readpal.Readpal(tl, verbose=verbose)
    j = rp.detect_ios()
    if fnout:
        open(fnout, 'w').write(json.dumps(j, indent=4, sort_keys=True))

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Determine PAL I/O by probing tristates')
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
