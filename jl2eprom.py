#!/usr/bin/env python3

import binascii
import json
import time

def run(fnin, fnout=None, verbose=False):
    if fnout is None:
        fnout = fnin.replace(".jl", ".bin")
        assert fnout != fnin, "Couldn't auto-name output file"
    
    fin = open(fnin, "r")
    meta = json.loads(fin.readline())
    # Possibly could give a --force option
    assert meta["part"] == "PAL16L8", "Only non-registered parts supported"
    assert len(meta["pins"]["D"]) == 8
    buff = bytearray(meta["data_words"])
    for l in fin:
        addr, word_comb, word_ff = json.loads(l)
        assert word_ff is None
        buff[addr] = word_comb
    open(fnout, "wb").write(buff)

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Read PAL device')
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("fnin")
    parser.add_argument("fnout", nargs='?')
    args = parser.parse_args()

    run(fnin=args.fnin, fnout=args.fnout, verbose=args.verbose)


if __name__ == "__main__":
    main()
