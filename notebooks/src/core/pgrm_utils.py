#!/usr/bin/env python3
from importlib import import_module

# miscellaneous utilities for common
# operations, eg; importing modules.

def get_module(modname):
    fmt = lambda m: m.lower().replace('-','_')
    mod = import_module(fmt(modname))
    return mod

