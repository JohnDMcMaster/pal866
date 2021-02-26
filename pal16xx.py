#!/usr/bin/env python3

"""
Focus on PAL16R8 for now
20-Pin Medium PAL Family Block Diagram
Collects data to be crunched into equations / JED

Assumes:
-Any input can effect any output
-Any output may or may not have a FF

With this in mind any PAL16XX device can be explored
Then output should be post processed with a more device specific script 
"""

from otl866 import bitbang, util
from otl866 import aclient
import binascii
import json
import time

# ZIF20 pin 1 indexed to ezzif 40 pin 0 indexed
dip20_to_zif_ = [1,  2,  3,  4,  5,  6,  7,  8,  9,  10, \
                31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
dip20_to_zif = dict([(i + 1, x - 1) for i, x in enumerate(dip20_to_zif_)])


"""
Each state
-Parent state(s)
-Non-self child states for each possible input both clocked and unlocked 
"""
"""
class State:
    def __init__(self):
        # (input, output, isclk) to state
        self.parents = {}
        # (input, output, isclk) to state
        self.children = {}

def add_closed_states(closed, tests):
    ret = set()
    for (addr, word_comb, word_clk) in tests:
        closed.add((addr, word_comb, False))
        closed.add((addr, word_clk, True))
    return ret

def add_open_states(open, tests):
    for (addr, word_comb, word_clk) in tests:
        pass
"""

class PAL16XXReader:
    def __init__(self, tl, part):
        assert part in ("PAL16L8", "PAL16R4", "PAL16R6", "PAL16R8")
        self.part = part

        if self.part == "PAL16L8":
            self.P_CLK = None
            self.P_OEn = None
            self.A_LINES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11]
        else:
            self.P_CLK = 1
            self.P_OEn = 11
            # 15 bit address => A14 max
            # 27C128
            self.A_LINES = [2, 3, 4, 5, 6, 7, 8, 9]
        self.WORDS = 1 << len(self.A_LINES)
        
        # LSB to MSB
        self.D_LINES = [12, 13, 14, 15, 16, 17, 18, 19]
        self.P_VCC = 20
        self.P_GND = 10

        self.tl = tl
        self.reset()

    def dip20s_to_zif(self, pins20):
        return sum([1 << dip20_to_zif[x] for x in pins20])

    def addr_to_pin20s(self, addr):
        """
        Return pins that should be set high
        """
    
        ret = []
        for biti, pin in enumerate(self.A_LINES):
            if addr & (1 << biti):
                ret.append(pin)
    
        return ret
        
    def ez2data(self, zif_val):
        '''
        Given socket state as integer mask, return the current data byte on data bus
        '''
        # LSB to MSB
        ret = 0
        for biti, pin20 in enumerate(self.D_LINES):
            # print("check d", zif_val, biti, pin20)
            if (1 << dip20_to_zif[pin20]) & zif_val:
                ret |= 1 << biti
    
        # print("ez2data: 0x%010X => 0x%02X" % (zif_val, ret))
        return ret
    
    def inputs_p20(self):
        ret = self.A_LINES
        if self.P_CLK is not None:
            ret += [self.P_CLK]
        if self.P_OEn is not None:
            ret += [self.P_OEn]
        return ret

    def reset(self):
        self.tl.vdd_en(False)
        self.tl.gnd_pins(0)

        # All high impedance by default
        tristate = 0xFFFFFFFFFF
        for pin in self.inputs_p20():
            tristate ^= 1 << dip20_to_zif[pin]
        self.tl.io_tri(tristate)

        # Set voltages
        self.tl.gnd_pins(self.dip20s_to_zif([self.P_GND]))
        self.tl.vdd_pins(self.dip20s_to_zif([self.P_VCC]))
        self.tl.vdd_volt(aclient.VDD_51)
        # Set all pins low
        self.tl.io_w(0)
        # self.tl.io_w(pin20s_to_ez([P_CLK, P_OEn]))
        self.tl.vdd_en()

    def quick_reset(self):
        """
        # Cut power, ground rail
        self.tl.vdd_pins(0)
        self.tl.vdd_en(False)
        self.tl.io_w(0)
        self.tl.io_tri(0)
        self.tl.gnd_pins(0xFFFFFFFFFF)
        time.sleep(0.1)
        self.tl.io_tri(0xFFFFFFFFFF)
        self.tl.gnd_pins(0)
        self.reset()
        """
        # Cut power, ground rail briefly
        self.tl.vdd_pins(0)
        self.tl.gnd_pins(self.dip20s_to_zif([self.P_VCC, self.P_GND]))
        self.tl.gnd_pins(self.dip20s_to_zif([self.P_GND]))
        self.tl.vdd_pins(self.dip20s_to_zif([self.P_VCC]))

    def sweep_combclk(self, clk):
        """
        Read every address and return the resulting data
        Static value + dynamic value
        "Registers are triggered on the high going edge"
        """
        ret = []
        for addr in range(self.WORDS):
        # for addr in [0xCA]:
            print("Addr 0x%04X / 0x%04X" % (addr, self.WORDS))
            # print("pass 1")
            # Clock low, OEn low
            self.tl.io_w(self.dip20s_to_zif(self.addr_to_pin20s(addr)))
            word_comb = self.ez2data(self.tl.io_r())
            print("   comb: 0x%02X" % word_comb)
            if clk:
                assert self.P_CLK is not None
                # print("pass 2")
                # Clock high, OEn low
                self.tl.io_w(self.dip20s_to_zif([self.P_CLK] + self.addr_to_pin20s(addr)))
                word_clk = self.ez2data(self.tl.io_r())
                print("   clk: 0x%02X" % word_clk)
            else:
                word_clk = None
            ret.append((addr, word_comb, word_clk))
        return ret
    
    def wr_clk(self, addr, clk=False):
        # clk = not clk
        if clk:
            self.tl.io_w(self.dip20s_to_zif([self.P_CLK] + self.addr_to_pin20s(addr)))
        else:
            self.tl.io_w(self.dip20s_to_zif(self.addr_to_pin20s(addr)))
        return self.ez2data(self.tl.io_r())

    def state_reset(self, parents):
        """Reset if FFs are in target state"""
        iref, oref = parents[-1]
        now = self.wr_clk(iref)
        print("  state_reset(): wanted 0x%02X => 0x%02X, got 0x%02X" % (iref, oref, now))
        if now == oref:
            return

        print("    state_reset() running")
        self.quick_reset()


        # Now walk state to get back to original
        for stepi, (iref, oref) in enumerate(parents):
            # Power on
            if stepi == 0:
                out = self.wr_clk(iref, False)
            else:
                out = self.wr_clk(iref, True)
            print("    state_reset(): %u 0x%02X => 0x%02X, got 0x%02X" % (stepi, iref, oref, out))
            if oref != out:
                print(parents)
                print(stepi, iref, oref)
                raise Exception("Failed to recreate state")

    def recursive_solver(self, found_states=set(), parents=[]):
        # (input, output)
        ret = []
        self.reset()

        if not parents:
            # Baseline power on at address 0
            parents.append((0, self.wr_clk(0, False)))

        print("Sweeping, %u found states" % len(found_states))
        print("Parents (%u)" % len(parents))
        for parent in parents:
            print("  ", parent)
        pending_recurse = {}
        if 0 and len(parents) == 1:
            itr = [0xA7]
        else:
            itr = range(self.WORDS)
        for addr in itr:
            print("Addr 0x%02X" % (addr,))
            self.state_reset(parents)
            word_comb = self.wr_clk(addr, False)
            word_clkp = self.wr_clk(addr, True)
            # Falling clock edge shouldn't change logic
            word_clkn = self.wr_clk(addr, False)
            print("  addr 0x%02X: comb 0x%02X, clkp 0x%02X, clkn 0x%02X, change %u" % (addr, word_comb, word_clkp, word_clkn, word_comb != word_clkp))
            if word_clkp != word_clkn:
                print("")
                print("")
                print("")
                print("Fail")
                while True:
                    print("")
                    time.sleep(1)
                    word_comb = self.wr_clk(addr, False)
                    time.sleep(1)
                    word_clkp = self.wr_clk(addr, True)
                    time.sleep(1)
                    # Falling clock edge shouldn't change logic
                    word_clkn = self.wr_clk(addr, False)
                    print("  addr 0x%02X: comb 0x%02X, clkp 0x%02X, clkn 0x%02X, change %u" % (addr, word_comb, word_clkp, word_clkn, word_comb != word_clkp))

                raise Exception("Bad clock transition")
            ret.append((addr, word_comb, word_clkp))
            if word_clkp not in found_states:
                found_states.add(word_clkp)
                pending_recurse[word_clkp] = addr

        print("Checking %u pending recursions" % len(pending_recurse))
        for iteri, (word_clk, addr) in enumerate(pending_recurse.items()):
            print("")
            print("Recursing on %u / %u (0x%02X, 0x%02X)" % (iteri + 1, len(pending_recurse), addr, word_clk))
            child_parents = parents + [(addr, word_clk)]
            ret += self.recursive_solver(found_states=found_states, parents=child_parents)
            print("Returned, depth now %u" % len(parents))

        return ret

    def is_clkless(self, words):
        """
        Registers are directly on the output
        See if anything changed
        """
        for (_addr, word_comb, word_clk) in words:
            if word_comb != word_clk:
                return False
        return True

    def run(self, fnout=None):
        try:
            self.tl.led(1)
            # When clockless just brute force all inputs
            if self.P_CLK is None:
                out = self.sweep_combclk(False)
            # Otherwise explore FF states
            else:
                out = self.recursive_solver()
            """
            # All states reached so far
            closed_list = set()
            add_closed_states(baseline, closed_list)
            open_list = add_open_states(closed_list, baseline)
            """
            if fnout:
                def write_out(f, output):
                    for out in output:
                        f.write(json.dumps(out, sort_keys=True) + "\n")
                f = open(fnout, "w")
                jheader = {
                    "part": self.part,
                    "words": self.WORDS,
                    "pins": {
                        "CLK": self.P_CLK,
                        "OEn": self.P_OEn,
                        "A": self.A_LINES,
                        "D": self.D_LINES,
                        "VCC": self.P_VCC,
                        "GND": self.P_GND,
                    }
                }
                write_out(f, [jheader] + out)
        finally:
            self.tl.init()
            self.tl.led(0)
    
    
def run(port=None, part=None, fnout=None, verbose=False):
    tl = bitbang.Bitbang(port, verbose=verbose)
    reader = PAL16XXReader(tl, part=part)
    reader.run(fnout=fnout)

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Read PAL device')
    parser.add_argument('--port',
                        default=util.default_port(),
                        help='Device serial port')
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument('--part', required=True)
    parser.add_argument("fnout", nargs='?')
    args = parser.parse_args()

    run(port=args.port, part=args.part, fnout=args.fnout, verbose=args.verbose)


if __name__ == "__main__":
    main()
