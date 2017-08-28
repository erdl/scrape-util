#!/usr/bin/env python3
from src.core.utils import Row
import csv

# This is an example implementation of a
# parser for the `static` data-acquisition
# method.  This parser reads a csv which
# already implements the common fields:
# | 'node' | 'sensor' | 'unit' | 'timestamp' | 'value' |
# Actual implementations will likely be much
# more complex, but this script does have the
# happy effect of being able to easily read
# the default output of the `csv` export method,
# assuming no data-reshaping has occurred.

# list of required configuration fields.
REQUIRE = []

# primary entry point.
def parse(config,state,filepath):
    # get the raw rows from the csv file.
    raw  = readcsv(filepath)
    # parse raw rows into expected format.
    rows = rowparse(raw)
    return rows


# read a csv file.
def readcsv(filepath):
    with open(filepath) as fp:
        reader = csv.reader(fp)
        rows = [ r for r in reader ]
    return rows

# parse the raw rows from csv.
def rowparse(raw):
    headers = [ h.lower() for h in raw.pop(0) ]
    if not headers == list(Row._fields):
        raise Exception('csv headers not in expected form.')
    rows = [ Row(*r) for r in raw ]
    return rows
