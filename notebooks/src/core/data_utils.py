#!/usr/bin/env python3
import src.core.file_utils as file_utils
import src.core.error_utils as error_utils
from collections import namedtuple
import time
import toml
import os.path as path
import os
import sys
import csv

# Default data type to be returned by all data-acquisition
# scripts.  Key requirement for interoperability between
# various steps/components ( esp. acquisition & reshaping ).
Row = namedtuple('row',['node','name','unit','timestamp','value'])

# error template for errors relating to `data_utils`
data_error = error_utils.error_template('`data_utils`')

def fmt_string(target):
    target = str(target).strip()
    elements = [e for e in target.split(' ') if e]
    formatted = '-'.join(elements).lower()
    return formatted

def row_generator(node,name,unit):
    node = fmt_string(node)
    name = fmt_string(name)
    unit = fmt_string(unit)
    gen = lambda t,v: Row(node,name,unit,float(t),float(v))
    return gen

def custom_row_generator(fields):
    custom = namedtuple('row',fields)
    generator = lambda vals: custom(*vals)
    return generator


# get a uid generator based on an ordered mapping of fields.
def get_uid_generator(key=None):
    default = ['node','name','unit']
    if not key: key = default
    fields = Row._fields
    fmt = lambda l: '-'.join(l).lower()
    indexes = []
    for item in key:
        indexes.append(fields.index(item))
    mkuid = lambda row: fmt((row[i] for i in indexes))
    return mkuid

# check a configuration file against a prototype
# of its expected fields and types.  `ident` must be
# the enclosing field name of the configuration value,
# `proto` and `data` represent the expected and actual
# data respectively.  `mkerr` may optionally be supplied
# as an error message template with `section` and `context`
# previously supplied.
def check_config(ident,proto,config,mkerr=None):
    # if no template is suppleid for error messages,
    # use the `data_utils` default template with a generic
    # context description.
    if not mkerr:
        context = 'checking configuration value for expected structure'
        mkerr = data_error(context)
    # ensure that we are using a single-step template.
    assert isinstance(mkerr('testing...'),str)
    # start the recursive field check.
    field_check(mkerr,ident,proto,config)


# recursively check the contents of a given config value
# against a prototype of its expected fields and types.
def field_check(mkerr,ident,proto,data,stack=[]):
    # create a trace string for clarity during recursion.
    trace = lambda: '.'.join([ident,*stack])
    for field in proto:
        # check for the existence of field.
        if not field in data:
            msg = "expected to find field `{}` in `{}`"
            error = mkerr(msg.format(field,trace()))
            raise Exception(error)
        # check for proper typing of field.
        # the `dict if isinstance(proto[field],dict)` line
        # allows us to descriminate between a type declaration
        # of `dict` and an actual decitonary.
        expect = dict if isinstance(proto[field],dict) else proto[field]
        actual = type(data[field])
        if expect != actual:
            msg = "expected field `{}` in `{}` to be `{}` but it is `{}`"
            error = mkerr(msg.format(field,trace(),expect,actual))
            raise Exception(error)
        # if prototype field is an actual dictionary, do a recursive check.
        if isinstance(proto[field],dict):
            field_check(mkerr,ident,proto[field],data[field],stack=[*stack,field])


# create a new row object, replacing the value of one or more fields
# based on a dict of the form { fieldname : newval }.
def update_row(mapping,row,constructor=Row):
    fields = constructor._fields
    asdict = {f:row[i] for i,f in enumerate(fields)}
    for field in mapping:
        if not field in asdict:
            raise Exception('unrecognized field: ' + field)
    asdict.update(mapping)
    newrow = constructor(*(asdict[f] for f in fields))
    return newrow


# sort rows into matching and non-matching list
# based upon a dict of form { field: matchstring }.
def match_rows(spec,rows,rowtype=Row):
    fields = rowtype._fields
    targets = [r for r in rows]
    removed = []
    for field in spec:
        if not field in fields:
            raise Exception('unrecognized field in matcher: ' + field)
        target = spec[field]
        index = fields.index(field)
        fltr = make_row_matcher(target,index)
        targets,removals = split_rows(fltr,targets)
        removed += removals
    return targets,removed

# generate a row filter based upon a match-string and
# an index.  Ex: the args `(0,"*foo")` would generate
# a filter that returns true for any row whose first
# element ends with `foo`.
def make_row_matcher(target,index):
    match = target.replace('*','')
    sw = lambda s,m: s.lower().startswith(m.lower())
    ew = lambda s,m: s.lower().endswith(m.lower())
    if not '*' in target:
        fltr = lambda r: match.lower() == r[index].lower()
    elif sw(target,'*') and ew(target,'*'):
        fltr = lambda r: match.lower() in r[index].lower()
    elif sw(target,'*'):
        fltr = lambda r: ew(r[index],match)
    elif ew(target,'*'):
        fltr = lambda r: sw(r[index],match)
    else:
        raise Exception('invalid match string: ' + target)
    return fltr


# map a function across a specific field of
# a list of rows.
def map_rows(fn,target,rows,constructor=Row):
    fields = constructor._fields
    if not target in fields:
        raise Exception('unrecognized field: ' + target)
    index = fields.index(target)
    mapped = []
    for row in rows:
        vals = list(row)
        vals[index] = fn(vals[index])
        mapped.append(constructor(*vals))
    return mapped


# split rows by a pass/fail function.
def split_rows(fn,rows,target=None,rowtype=Row):
    if target:
        fields = rowtype._fields
        if not target in fields:
            raise Exception('unrecognized field: ' + target)
        index = fields.index(target)
        fltr = lambda r: fn(r[index])
    else: fltr = fn
    passed,failed = [],[]
    for row in rows:
        if fltr(row): passed.append(row)
        else: failed.append(row)
    return passed,failed


# generic nonce updater/generator.  This is an experimental
# attempt to provide a single standardized handler for nonce
# values.  Consider this an unstable API feature.
# requires, at a minimum, a `targets` dict of the form
# `{ 'some-uid': {}, ... }`.
def make_time_specs(targets,settings={},nonce={}):
    # integer representing the current time.
    now = int(time.time())
    # get init time for nonces; default is two weeks into the past.
    init = settings.get('init-time',now - 1209600)
    # get maximum step time; default is two weeks.
    step = settings.get('step-time',1209600)
    # generate a dict specifying init time and maximum viable step
    # length for a given uid.  the maximum step length must be individually
    # calculated, as some `nonce` values may be more recent than `now` - `step`.
    mkspec = lambda i,s: { 'init': i, 'step': min((now,i + s)) - i }
    times = {} # collector for the final values to be returned.
    # iteratively generate time-spec for each uid in `targets`.
    for uid,spec in targets.items():
        # handle common pattern of dict/table being set to `true` or
        # `"default"` to indicate that default values should be inferred.
        spec = spec if isinstance(spec,dict) else {}
        # use target-specific `step` if exists, else default.
        tstep = spec.get('step',step)
        # use nonce value for `init` if exists, else use
        # target-specific val if exists, else default.
        tinit = nonce.get(uid,spec.get('init',init))
        # insert the time-spec under the given uid.
        times[uid] = mkspec(int(tinit),int(tstep))
    # quick sanity check.
    assert len(targets) == len(times)
    # pass back the time values.  implementation is responsible
    # for updating the actual nonce after scrape attempt.
    return times


