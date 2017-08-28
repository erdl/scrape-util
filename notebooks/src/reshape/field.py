#!/usr/bin/env python3
from src.core.error_utils import error_template
import src.core.data_utils as du
from collections import namedtuple
import time

# Defines order of
# execution in reshape runtime.
ORD = 2

field_error = error_template('`field` based data-reshaping step')

# primary entry point.
def reshape(project,config,state,data):
    mkerr = field_error('attempting to run declared sub-steps')
    settings = config.get('settings',{})
    default = ["modify","generate"]
    declared = [k for k in config if not k == 'settings']
    for step in declared:
        if not step in default:
            error = mkerr('unrecognized sub-step section: ' + step)
            raise Exception(error)
    order = settings.get('in-order',default)
    rows = [r for r in data]
    for step in order:
        if not step in declared: continue
        if step == 'modify':
            state,rows = run_modifications(project,config,state,rows)
        elif step == 'generate':
            state,rows = run_generators(project,config,state,rows)
        else:
            error = mkerr('unrecognized sub-step name: ' + step)
            raise Exception(error)
    return state,rows

# Map one or more fields to some other set of fields.
def run_modifications(project,config,state,data):
    # TODO: add an `on-modify` handler for options `discard` & `archive`
    fieldmap = config['modify']
    mkerr = field_error('field name & order reassignment')
    if not data: return state,data
    fieldmap = { k.lower() : fieldmap[k] for k in fieldmap }
    dfields  = data[0]._fields
    for field in fieldmap:
        if field not in dfields:
            error = mkerr('unrecognized field: ' + field)
            raise Exception(error)
    types = {'int':int,'float':float,'str':str,'bool':bool,'none':lambda v:v}
    indexmap = []
    namemap  = []
    typemap  = []
    for di,df in enumerate(dfields):
        if not df in fieldmap: continue
        mf = fieldmap[df]['title']
        mi = fieldmap[df]['index']
        mt = fieldmap[df].get('type','none')
        if not mt in types:
            error = mkerr('unrecognized type: ' + str(mt))
            raise Exception(error)
        indexmap.append((mi,di))
        namemap.append((mi,mf))
        typemap.append((mi,mt))
    sbi = lambda i: i[0]
    foi = lambda l: [x[1] for x in l]
    indexmap = foi(sorted(indexmap,key=sbi))
    namemap  = foi(sorted(namemap,key=sbi))
    typemap  = foi(sorted(typemap,key=sbi))
    fmtrow   = namedtuple('fmtrow', namemap)
    fmtdata  = []
    for d in data:
        row = []
        for i in indexmap:
            row.append(d[i])
        for i,t in enumerate(typemap):
            row[i] = types[t](row[i])
        fmtdata.append(fmtrow(*row))
    return state,fmtdata


# run all specified `generate` steps.
def run_generators(project,config,state,data):
    if not data: return state,data
    generators = config['generate']
    settings = config.get('settings',{})
    mkerr = field_error('generating new fields')
    rows = [r for r in data]
    for gen in generators:
        value = gen['value']
        if value == 'current-time':
            state,rows = generate_current_time(project,gen,state,rows)
        elif value == 'literal':
            state,rows = generate_literal(project,gen,state,rows)
        else:
            error = mkerr('unrecognized `value` argument: ' + value)
            raise Exception(error)
    return state,rows

# add a field with some arbitrary value for all rows.
def generate_literal(project,config,state,rows):
    if not rows: return
    mkerr = field_error('generating field: `literal`')
    title = config['title']
    index = config.get('index','append')
    value = config['ident']
    if isinstance(index,str):
        if index == "append":
            fmt = lambda v,r: list(r) + [v]
        else:
            error = mkerr('unexpected value for `index`: ' + index)
            raise Exception(error)
    elif isinstance(index,int):
        fmt = lambda v,r: list((*r[0:index],v,*r[index:]))
    else:
        error = mkerr('unexpected value for `index`: ' + str(index))
        raise Exception(error)
    fields = rows[0]._fields
    newfields = fmt(title,fields)
    mkrow = du.custom_row_generator(newfields)
    modify = lambda r: mkrow(fmt(value,r))
    newrows = []
    for row in rows:
        newrow = modify(row)
        newrows.append(newrow)
    return state,newrows

# add a generated field containing the current time.
def generate_current_time(project,config,state,rows):
    if not rows: return
    mkerr = field_error('generating field: `current-time`')
    title = config['title']
    index = config.get('index',"append")
    dec = config.get('round',6)
    now = round(time.time(),dec) if dec > 0 else int(time.time())
    if isinstance(index,str):
        if index == "append":
            fmt = lambda v,r: list(r) + [v]
        else:
            error = mkerr('unexpected value for `index`: ' + index)
            raise Exception(error)
    elif isinstance(index,int):
        fmt = lambda v,r: list((*r[0:index],v,*r[index:]))
    else:
        error = mkerr('unexpected value for `index`: ' + str(index))
        raise Exception(error)
    fields = rows[0]._fields
    newfields = fmt(title,fields)
    mkrow = du.custom_row_generator(newfields)
    modify = lambda r: mkrow(fmt(now,r))
    newrows = []
    for row in rows:
        newrow = modify(row)
        newrows.append(newrow)
    return state,newrows

