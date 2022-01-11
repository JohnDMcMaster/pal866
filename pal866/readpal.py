from otl866 import bitbang, util
from otl866 import aclient
import binascii
import json
import time

class Package:
    def __init__(self, tl, verbose=False):
        """
        N/C pins:
        1 VPP
        22 CEn
        24 OEn
        31 PGMn
        """

        self.verbose = verbose
        self.tl = tl
        self.npins = 32
        self.P_VCC = 32
        self.P_GND = 16
        self.addr_pins = [12, 11, 10, 9, 8, 7, 6, 5, 27, 26, 23, 25, 4, 28, 29, 3, 2, 30]
        self.data_pins = [13, 14, 15, 17, 18, 19, 20, 21]

        """
        27C020 like => DIP32
        ZIF32 pin 1 indexed to ezzif 40 pin 0 indexed
        Ex: DIP32 1 => DIP40 0
        Ex: DIP32 32 => DIP40 39
        """
        to_zif_ = [1,  2,  3,  4,  5,  6,  7,  8,  9,  10, 11, 12, 13, 14, 15, 16, \
                        25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
        self.pin_pack2zif = dict([(i + 1, x - 1) for i, x in enumerate(to_zif_)])
        assert self.pin_pack2zif[32] == 39

    def setup_pins(self):
        self.verbose and print("reset")
        self.tl.vdd_en(False)
        self.tl.gnd_pins(0)
        self.tl.io_tri()

        gnd = self.pins_to_zif([self.P_GND])
        self.verbose and print("  reset gnd: 0x%010X" % gnd)
        self.tl.gnd_pins(gnd)

        vcc = self.pins_to_zif([self.P_VCC])
        self.verbose and print("  reset vcc: 0x%010X" % vcc)
        self.tl.vdd_pins(vcc)
        self.tl.vdd_volt(aclient.VDD_51)

        # Set all pins low
        self.tl.io_w(0)
        # self.tl.io_w(pin20s_to_ez([P_CLK, P_OEn]))
        self.tl.vdd_en()
        self.set_io_dir()

    def pins_to_zif(self, l):
        """Convert list of pins to ZIF mask"""
        return sum([1 << self.pin_pack2zif[x] for x in l])

    def input_pins(self):
        return self.data_pins

    def output_pins(self):
        return self.addr_pins

    def set_io_dir(self):
        # All high impedance by default
        tristate = 0xFFFFFFFFFF
        for pin in self.output_pins():
            tzif = self.pin_pack2zif[pin]
            mask = 1 << tzif
            self.verbose and print("  Z %u => %u => 0x%010X" % (pin, tzif, mask))
            tristate ^= mask
        self.verbose and print("  reset tristate: 0x%010X" % tristate)
        self.tl.io_tri(tristate)

        # print("I_LINES: %s" % (self.addr_pins,))
        # print("O_LINES: %s" % (self.data_pins,))

    """
    def calculate_io(self, opins=[]):
        self.addr_pins = list(self.addr_pins_base)
        self.data_pins = list(self.data_pins_base)
        for pin in self.IO_LINES:
            if pin in opins:
                self.data_pins.append(pin)
            else:
                self.addr_pins.append(pin)
        self.addr_pins = sorted(self.addr_pins)
        self.data_pins = sorted(self.data_pins)
        self.verbose and print("i/o I: ", self.addr_pins)
        self.verbose and print("i/o O: ", self.data_pins)
    """

"""
LSB first
"""
class DataBus:
    def __init__(self, pack, data_pins, addr_pins, verbose=False):
        self.verbose = verbose
        self.data_pins = data_pins
        self.addr_pins = addr_pins
        self.pack = pack
        print("Bus data: %s" % (self.data_pins,))
        print("Bus addr: %s" % (self.addr_pins,))

    def words(self):
        return 1 << len(self.addr_pins)

    def pin_data_mask(self, pin):
        """Return the data mask for given pin"""
        return 1 << self.data_pins.index(pin)

    def pin_addr_mask(self, pin):
        """Return the address mask for given pin"""
        return 1 << self.addr_pins.index(pin)

    def pins_for_addr(self, addr):
        """
        Return pins that should be set high
        """
    
        ret = []
        for biti, pin in enumerate(self.addr_pins):
            if addr & (1 << biti):
                ret.append(pin)
    
        return ret
        
    def ez2data(self, zif_val):
        '''
        Given socket state as integer mask, return the current data byte on data bus
        '''
        # LSB to MSB
        ret = 0
        for biti, pinp in enumerate(self.data_pins):
            # print("check d", zif_val, biti, pin20)
            if (1 << self.pack.pin_pack2zif[pinp]) & zif_val:
                ret |= 1 << biti
    
        # print("ez2data: 0x%010X => 0x%02X" % (zif_val, ret))
        return ret

    def addr(self, val):
        """Set addr on bus"""
        self.pack.tl.io_w(self.pack.pins_to_zif(self.pins_for_addr(val)))

    def read(self):
        """Read val from bus"""
        return self.ez2data(self.pack.tl.io_r())


    def read_all(self, verbose=True):
        ret = bytearray()
        verbose and print("Reading %u words" % self.words())
        for addr in range(self.words()):
            if addr % (self.words() // 100) == 0:
                verbose and print("%0.1f%%" % (addr / self.words() * 100.0,))
            self.addr(addr)
            ret.append(self.read())
        return ret

class Readpal:
    def __init__(self, tl, verbose=False):
        self.verbose = verbose
        self.tl = tl
        self.pack = Package(self.tl, verbose=self.verbose)
        self.db = DataBus(self.pack,
                          addr_pins=self.pack.addr_pins,
                          data_pins=self.pack.data_pins,
                          verbose=self.verbose)
    
    def read_eprom(self):
        """
        Simple address sweep
        Dreadfully slow
        Around 23 minutes for full read
        A normal EPROM programmer can do it in < 1 min
        """
        # return bytearray(256 * 1024)
        ret = bytearray()
        print("Reading %u words" % self.db.words())
        self.pack.setup_pins()
        for addr in range(self.db.words()):
            if addr % (self.db.words() // 100) == 0:
                print("%0.1f%%" % (addr / self.db.words() * 100.0,))
                #if addr:
                #    return ret
            self.db.addr(addr)
            # TODO: consider multiple read here to detect unstable latch values
            ret.append(self.db.read())
        return ret

    def detect_ios(self, verbose=True):
        """
        Tristate I/O pins and see how they respond to pullup resistors
        http://dreamjam.co.uk/emuviews/files/adapter-v2-cap.png


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
        
        samples = 16
        ret = {
            "samples": samples,
            # By PAL pin number
            "pins": {},
            }

        self.pack.setup_pins()

        pin_table = [
            # DIP20 pin, EPROM pin, EPROM PU/PD pin
            (12, 13, 23),
            (13, 14, 25),
            (14, 15, 4),
            (15, 17, 28),
            (16, 18, 29),
            (17, 19, 3),
            (18, 20, 2),
            (19, 21, 30),
            ]
        ret["pin_table"] = pin_table

        for _data_pini, pins in enumerate(pin_table):
            # Toggle PU/PD address pin while keeping everything else constant
            # If its an input we should be able to track value

            pal_pin, eprom_d_pin, eprom_pupd_pin = pins
            amask = self.db.pin_addr_mask(eprom_pupd_pin)
            dmask = self.db.pin_data_mask(eprom_d_pin)


            # PD
            pds = 0
            for i in range(samples):
                addr = 0
                self.db.addr(addr)
                data = self.db.read()
                if data & dmask:
                    pds += 1

            # PU
            pus = 0
            for i in range(samples):
                addr = amask
                self.db.addr(addr)
                data = self.db.read()
                if data & dmask:
                    pus += 1
            
            verbose and print("PAL pin %u (EPROM D %u, EPROM PU/PD %u)" % (pal_pin, eprom_d_pin, eprom_pupd_pin))
            verbose and print("  pds: %u / %u" % (pds, samples))
            verbose and print("  pus: %u / %u" % (pus, samples))

            # If value tracks PU/PD its not being driven => an input
            if pds == 0 and pus == samples:
                status = "i"
            # Constant value => a stable output
            elif pus == pds and (pus == 0 or pus == 16):
                status = "o"
            # Something else, probably a latch
            else:
                status = "l"
            verbose and print("  status: %s" % (status,))

            ret["pins"][pal_pin] = {
                "status": status,
                "pus": pus,
                "pds": pds,
                }
        
        if verbose:
            s = ""
            for _data_pini, pins in enumerate(pin_table):
                pal_pin, _eprom_d_pin, _eprom_pupd_pin = pins
                s += ret["pins"][pal_pin]["status"]
            print("status:", s)

        return ret

    def read_eprom_ios(self):
        """
        Determine IOs and then only read that combination
        """
        j = self.detect_ios()

        for pinj in j["pins"].values():
            # Only handle trivial cases
            assert pinj["status"] in "io"

        """
        Create a new address map
        Base off of existing and then strip out unused bits

        Two choices to drive address lines on confirmed inputs:
        -Directly via pin
        -Indirectly via PU/PD
        """

        pal_addr_pins = list(self.db.addr_pins)
        pal_data_pins = list(self.db.data_pins)
        for _data_pini, pins in enumerate(j["pin_table"]):
            pal_pin, eprom_d_pin, eprom_pupd_pin = pins
            status = j["pins"][pal_pin]["status"]
            # Input => eliminate unused output pin
            if status == "i":
                pal_data_pins.remove(eprom_d_pin)
                # Optionally could remove the eprom_pupd_pin and add the eprom_d_pin to the address bus
                # something like
                # pal_addr_pins.replace(eprom_pupd_pin, eprom_d_pin)
            # Remove unused PU/PD pins
            elif status == "o":
                pal_addr_pins.remove(eprom_pupd_pin)

        # recalcualte new data bus
        palpack = Package(self.tl, verbose=self.verbose)
        palpack.data_pins = pal_data_pins
        palpack.addr_pins = pal_addr_pins
        paldb = DataBus(palpack,
                          addr_pins=pal_addr_pins,
                          data_pins=pal_data_pins,
                          verbose=self.verbose)
        palpack.setup_pins()
        buf = paldb.read_all()
        return buf, j