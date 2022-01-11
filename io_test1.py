#!/usr/bin/env python3

"""
Try to figure out I/O direction
Assert bus and see how it interacts w/ tristates
Assuming a purely comb PAL16L8
"""

from otl866 import bitbang, util
from otl866 import aclient
import binascii
import json
import time

"""
ZIF20 pin 1 indexed to ezzif 40 pin 0 indexed
Ex: DIP20 1 => DIP40 0
Ex: DIP20 20 => DIP40 39
"""
dip20_to_zif_ = [1,  2,  3,  4,  5,  6,  7,  8,  9,  10, \
                31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
dip20_to_zif = dict([(i + 1, x - 1) for i, x in enumerate(dip20_to_zif_)])
assert dip20_to_zif[20] == 39

class PAL16XXReader:
    def __init__(self, tl, part, input_pins=[], verbose=False):
        self.verbose = verbose
        assert part in ("PAL16L8",)
        self.part = part

        self.P_CLK = None
        self.P_OEn = None
        # Input to PAL, output to us
        self.I_LINES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11]
        # 13-18 are I/O
        self.O_LINES = [12, 19]
        self.IO_LINES = [13, 14, 15, 16, 17, 18]

        self.I_LINES_base = sorted(self.I_LINES)
        self.O_LINES_base = sorted(self.O_LINES)
        self.I_LINES = self.I_LINES_base
        self.O_LINES = self.O_LINES_base
        print("I_LINES: %s" % (self.I_LINES,))
        print("O_LINES: %s" % (self.O_LINES,))
        print("IO_LINES: %s" % (self.IO_LINES,))
        
        self.P_VCC = 20
        self.P_GND = 10

        self.tl = tl

    def dip20s_to_zif(self, pins20):
        return sum([1 << dip20_to_zif[x] for x in pins20])

    def addr_to_pin20s(self, addr):
        """
        Return pins that should be set high
        """
    
        ret = []
        for biti, pin in enumerate(self.I_LINES):
            if addr & (1 << biti):
                ret.append(pin)
    
        return ret
        
    def ez2data(self, zif_val):
        '''
        Given socket state as integer mask, return the current data byte on data bus
        '''
        # LSB to MSB
        ret = 0
        for biti, pin20 in enumerate(self.O_LINES):
            # print("check d", zif_val, biti, pin20)
            if (1 << dip20_to_zif[pin20]) & zif_val:
                ret |= 1 << biti
    
        # print("ez2data: 0x%010X => 0x%02X" % (zif_val, ret))
        return ret
    
    def inputs_p20(self):
        ret = self.I_LINES
        if self.P_CLK is not None:
            ret += [self.P_CLK]
        if self.P_OEn is not None:
            ret += [self.P_OEn]
        return ret

    def outputs_p20(self):
        ret = self.O_LINES
        return ret

    def set_io_dir(self):
        # All high impedance by default
        tristate = 0xFFFFFFFFFF
        for pin in self.outputs_p20():
            tzif = dip20_to_zif[pin]
            mask = 1 << tzif
            self.verbose and print("  Z %u => %u => 0x%010X" % (pin, tzif, mask))
            tristate ^= mask
        self.verbose and print("  reset tristate: 0x%010X" % tristate)
        self.tl.io_tri(tristate)

        # print("I_LINES: %s" % (self.I_LINES,))
        # print("O_LINES: %s" % (self.O_LINES,))

    def reset(self):
        self.verbose and print("reset")
        self.tl.vdd_en(False)
        self.tl.gnd_pins(0)
        self.tl.io_tri(0xFFFFFFFFFF)

        # Set voltages
        gnd = self.dip20s_to_zif([self.P_GND])
        self.verbose and print("  reset gnd: 0x%010X" % gnd)
        self.tl.gnd_pins(gnd)
        vcc = self.dip20s_to_zif([self.P_VCC])
        self.verbose and print("  reset vcc: 0x%010X" % vcc)
        self.tl.vdd_pins(vcc)
        self.tl.vdd_volt(aclient.VDD_51)
        # Set all pins low
        self.tl.io_w(0)
        # self.tl.io_w(pin20s_to_ez([P_CLK, P_OEn]))
        self.tl.vdd_en()
        self.set_io_dir()

    def calculate_io(self, opins=[]):
        self.I_LINES = list(self.I_LINES_base)
        self.O_LINES = list(self.O_LINES_base)
        for pin in self.IO_LINES:
            if pin in opins:
                self.O_LINES.append(pin)
            else:
                self.I_LINES.append(pin)
        self.I_LINES = sorted(self.I_LINES)
        self.O_LINES = sorted(self.O_LINES)
        self.verbose and print("i/o I: ", self.I_LINES)
        self.verbose and print("i/o O: ", self.O_LINES)

    def iomap(self):
        """
        Return a string in pin order
        I: input
        O: output
        Z: tristate (RFU)
        P: power
        G: ground
        C: clock
        0/1: fixed value
        """
        ret = list("?" * 20)
        ret[self.P_VCC - 1] = "P"
        ret[self.P_GND - 1] = "G"
        for pin in self.I_LINES:
            ret[pin - 1] = "I"
        for pin in self.O_LINES:
            ret[pin - 1] = "O"
        if self.P_CLK is not None:
            ret[self.P_CLK - 1] = "C"
        if self.P_OEn is not None:
            ret[self.P_OEn - 1] = "0"
        assert "?" not in ret
        return "".join(ret)

    def wr_clk(self, addr, clk=False):
        # clk = not clk
        if clk:
            self.tl.io_w(self.dip20s_to_zif([self.P_CLK] + self.addr_to_pin20s(addr)))
        else:
            self.tl.io_w(self.dip20s_to_zif(self.addr_to_pin20s(addr)))
        return self.ez2data(self.tl.io_r())

    def words(self):
        return 1 << len(self.I_LINES)

    def probe_tristate_u33(self):
        print("Probe tristate")

        """
        2022-01-10
        Results:
        -w/o chip biasing does occur
        -w/ chip 13-16 always True, 17-18 always false
        -13-15 input => pullups?
            could this be exploited to guess inputs based on outputs that never change?
        -Improved debugging in bitbang


        no loops
        13 to 18 are I/O
        goal: automatically extract this
        "13": "i",
        "14": "i",
        "15": "i",
        "16": "o",
        "17": "o",
        "18": "o",



        "1": "i",
        "2": "i",
        "3": "i",
        "4": "i",
        "5": "i",
        "6": "i",
        "7": "i",
        "8": "i",
        "9": "i",
        "11": "i",
        "12": "o",
        "13": "i",
        "14": "i",
        "15": "i",
        "16": "o",
        "17": "o",
        "18": "o",
        "19": "o"
        """
       
        """
        Let's try 13
        Force 0 value, read pin state
            All pins input as 0
        Force 1 value, read pin state
            All pins input as 0 except this pin
        Compare result
        """

        for pin_tested in (13, 14, 15, 16, 17, 18):

            def pin_driven():
                self.calculate_io(opins=[pin_tested])
                self.set_io_dir()
    
            def pin_undriven():
                self.calculate_io(opins=[])
                self.set_io_dir()
    
            def zif_bit_set(zif_val):
                return bool((1 << dip20_to_zif[pin_tested]) & zif_val)
    
            print("")
            print("")
            print("Pin", pin_tested)
            self.verbose and print("Setting up tristates")
            # Everything as input on chip => output here
            pin_driven()
            self.reset()
    
            verbose = False
    
            # All pins 0
            print("")
            print("L")
            self.tl.io_w(self.dip20s_to_zif([]))
            for i in range(16):
                verbose and print("")
                verbose and print("")
                pin_driven()
                verbose and self.tl.print_debug()
                verbose and print("")
                pin_undriven()
                verbose and self.tl.print_debug()
                verbose and print("")
                zif_val = self.tl.io_r()
                print("   got: 0x%010X => %s" % (zif_val, zif_bit_set(zif_val)))
                # time.sleep(100)
    
            # Pin 13 high
            print("")
            print("H")
            self.tl.io_w(self.dip20s_to_zif([pin_tested]))
            for i in range(16):
                pin_driven()
                pin_undriven()
                zif_val = self.tl.io_r()
                print("   got: 0x%010X => %s" % (zif_val, zif_bit_set(zif_val)))

    
    def run(self, fnout=None):
        try:
            self.tl.led(1)
            self.probe_tristate_u33()
        finally:
            self.tl.init()
            self.tl.led(0)
    
    
def run(port=None, part=None, fnout=None, input_pins=[], tl866_verbose=False, verbose=False):
    tl = bitbang.Bitbang(port, verbose_cmd=tl866_verbose)
    reader = PAL16XXReader(tl, part=part, input_pins=input_pins, verbose=verbose)
    reader.run(fnout=fnout)

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Read PAL device')
    parser.add_argument('--port',
                        default=util.default_port(),
                        help='Device serial port')
    parser.add_argument("--input-pins", default=None, help="Comma separated list of I/Os as inputs")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--tl866-verbose", action="store_true")
    parser.add_argument('--part', required=True)
    parser.add_argument("fnout", nargs='?')
    args = parser.parse_args()

    input_pins = None
    if args.input_pins is not None:
        input_pins = [int(x) for x in args.input_pins.split(",")]
    run(port=args.port, part=args.part, fnout=args.fnout, input_pins=input_pins, tl866_verbose=args.tl866_verbose, verbose=args.verbose)


if __name__ == "__main__":
    main()
