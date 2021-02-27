# pal866
PAL brute forcing using closed loop feedback w/ open-tl866

The following parts are currently of interest:

| Part        | Supported   |  Notes |
| ----------- | ----------- | -------|
| PAL16L8     | Yes         | Need to post process |
| PAL16R8     | Partial     | CLK related bug |
| PALCE20V8H  | No          | Future |
| PA7140T     | No          | Future |


## Setup

Install open-tl866 bitbang firmware

## PAL16L8

Insert chip in normal socket position (notch as close to lever as possible)

Run:

```
python3 pal16xx.py --part PAL16L8 out.jl
```

This should take about 6 seconds

Now convert to "EPROM" format so it can be fed into existing post processing tools:

```
python3 jl2eprom.py out.jl out.bin
```

This should give you a 1 KB .bin file

This should give equivilent output to say something like this
  * http://dreamjam.co.uk/emuviews/readpal.php
  * https://github.com/pascalorama/paldumper

TODO: this tool expects 2 KB input? Do we need to pad?
