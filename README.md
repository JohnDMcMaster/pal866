# pal866
PAL brute forcing using closed loop feedback w/ open-tl866

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

This should give equivilent output to say something like this
  * http://dreamjam.co.uk/emuviews/readpal.php
  * https://github.com/pascalorama/paldumper

