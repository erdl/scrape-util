#!/usr/bin/env python3
from src.core.data_utils import Row
import csv


REQUIRE = []


# primary entry point of this parser.
def parse(project,config,state,filepath):
    rawdata = read_csv(filepath)
    rows = reformat_data(config,rawdata)
    return state,rows

# reformat the data into `Row` objects.
def reformat_data(config,raw):
    if not raw: return
    for r in raw: print(len(r))
    fields = ['url','survey','question','option','timestamp']
    if raw[0] == fields:
        raw = raw[1:]
        if not raw: return
    toint = lambda r: [elem for elem in map(int,r)]
    torow = lambda r: Row(r[0],r[1],r[2],r[4],r[3])
    mkrow = lambda r: torow(toint(r))
    rows = [mkrow(r) for r in raw]
    return rows

# because who doesn't like reading CSVs?
def read_csv(filename):
    with open(filename) as fp:
        reader = csv.reader(fp)
        rows = [r for r in reader if r]
    return rows
