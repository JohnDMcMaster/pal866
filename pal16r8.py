#!/usr/bin/env python3

"""
Focus on PAL16R8 for now
20-Pin Medium PAL Family Block Diagram
"""

from otl866 import bitbang, util
from otl866 import aclient
import binascii

# ZIF20 pin 1 indexed to ezzif 40 pin 0 indexed
dip20_to_zif_ = [1,  2,  3,  4,  5,  6,  7,  8,  9,  10, \
                31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
dip20_to_zif = dict([(i + 1, x - 1) for i, x in enumerate(dip20_to_zif_)])

# 15 bit address => A14 max
# 27C128
A_LINES = [2, 3, 4, 5, 6, 7, 8, 9]
# LSB to MSB
D_LINES = [12, 13, 14, 15, 16, 17, 18, 19]
P_CLK = 1
P_OEn = 11
P_VCC = 20
P_GND = 10

WORDS = 1 << len(A_LINES)

def dip20s_to_zif(pins20):
    return sum([1 << dip20_to_zif[x] for x in pins20])


def addr_to_pin20s(addr):
    """
    Return pins that should be set high
    """

    ret = []
    for biti, pin in enumerate(A_LINES):
        if addr & (1 << biti):
            ret.append(pin)

    return ret


def ez2data(zif_val):
    '''
    Given socket state as integer mask, return the current data byte on data bus
    '''
    # LSB to MSB
    ret = 0
    for biti, pin20 in enumerate(D_LINES):
        # print("check d", zif_val, biti, pin20)
        if (1 << dip20_to_zif[pin20]) & zif_val:
            ret |= 1 << biti

    return ret

class PAL16R8SReader:
    def __init__(self, tl):
        self.tl = tl
        self.reset()

    def reset(self):
        # All high impedance by default
        tristate = 0xFFFFFFFFFF
        for pin in A_LINES + [P_CLK, P_OEn]:
            tristate ^= 1 << dip20_to_zif[pin]
        self.tl.io_tri(tristate)

        # Set voltages
        self.tl.gnd_pins(dip20s_to_zif([P_GND]))
        self.tl.vdd_pins(dip20s_to_zif([P_VCC]))
        self.tl.vdd_volt(aclient.VDD_51)
        # Set all pins low
        self.tl.io_w(0)
        # self.tl.io_w(pin20s_to_ez([P_CLK, P_OEn]))
        self.tl.vdd_en()


    def sweep_combclk(self):
        """
        Read every address and return the resulting data
        Static value + dynamic value
        "Registers are triggered on the high going edge"
        """
        ret = {}
        for addr in range(WORDS):
        # for addr in [0xCA]:
            print("Addr 0x%02X" % addr)
            # print("pass 1")
            # Clock low, OEn low
            self.tl.io_w(dip20s_to_zif(addr_to_pin20s(addr)))
            word_comb = ez2data(self.tl.io_r())
            print("   comb: 0x%02X" % word_comb)
            # print("pass 2")
            # Clock high, OEn low
            self.tl.io_w(dip20s_to_zif([P_CLK] + addr_to_pin20s(addr)))
            word_clk = ez2data(self.tl.io_r())
            print("   clk: 0x%02X" % word_clk)
            ret[addr] = (word_comb, word_clk)
        return ret
    
    def is_clkless(self, words):
        """
        Registers are directly on the output
        See if anything changed
        """
        for _addr, (word_comb, word_clk) in words.items():
            if word_comb != word_clk:
                return False
        return True

    def run(self):
        try:
            self.tl.led(1)
            baseline = self.sweep_combclk()
            print("Clockless: %u" % self.is_clkless(baseline))
        finally:
            self.tl.init()
            self.tl.led(0)
    
    
def run(port, verbose=False):
    tl = bitbang.Bitbang(port, verbose=verbose)
    reader = PAL16R8SReader(tl)
    reader.run()

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Read PAL device')
    parser.add_argument('--port',
                        default=util.default_port(),
                        help='Device serial port')
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    run(args.port, verbose=args.verbose)


if __name__ == "__main__":
    main()
