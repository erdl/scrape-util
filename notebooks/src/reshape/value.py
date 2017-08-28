#!/usr/bin/env python3
from src.core.error_utils import errdata, error_template
import src.core.data_utils as du
import src.core.file_utils as fu

# Determines order of application
# during mulit-phase reshaping process.
ORD = 0

reshape_error = error_template('`value` based data-reshaping step')


# reshape : proj -> conf -> state -> data -> (state,data)
def reshape(project,config,state,data):
    settings = config['settings']
    actions = ['filter','generate','replace']
    if 'in-order' in settings:
        order = settings['in-order']
    else: order = [a for a in actions if a in config]
    errors = []
    for action in order:
        substate = state[action] if action in state else {}
        if action == 'filter':
            substate,data = run_filters(project,config,substate,data)
        elif action == 'generate':
            substate,data = run_generators(project,config,substate,data)
        elif action == 'replace':
            substate,data = run_replacements(project,config,substate,data)
        else: raise Exception('unknown action: ' + action)
        if substate: state[action] = substate
        else: state.pop(action,None)
    return state,data

# Filter out undesired data-points, either
# by name of data-point, or by value range.
def run_filters(project,config,state,data):
    if not data: return state,data
    settings = config['settings']
    filters = config['filter']
    # binary filters to be applied by uid.
    binary = {k: v for k,v in filters.items() if isinstance(v,bool)}
    # limiting filters to be applied by uid.
    limits = {k: v for k,v in filters.items() if
            isinstance(v,dict) and not k in data[0]._fields}
    # limiting filters to be applied by field.
    fields = {k: v for k,v in filters.items() if
            isinstance(v,dict) and k in data[0]._fields}
    # dictionary of all rows sorted by their uid.
    uidsort = sort_by_uid(settings,data)
    # collectors for rows based on removal
    keep,remove = [],[]
    # run binary filters, removing all uids
    # which have been flagged as `false`.
    for uid in binary:
        if binary[uid] is False:
            remove += uidsort.pop(uid,())
    # run limiting filters on all uids for which
    # one or more limiting filters are specified.
    for uid in limits:
        if not uid in uidsort: continue
        rows = uidsort[uid]
        rows,rems = limiting_filters(limits[uid],rows,target='value')
        uidsort[uid] = rows
        remove += rems
    # re-concolidate remaining contents of `uidsort`
    # into the `keep` list.
    for rows in uidsort.values():
        keep += rows
    # run limiting filters on all fields for which
    # one or more limiting filters are specified.
    for field,spec in fields.items():
        keep,rem = limiting_filters(spec,keep,target=field)
        remove += rem
    # TEST: ensure that no filters are causing silent removals.
    assert len(data) == (len(keep) + len(remove))
    # deal with removed rows as specified in config.
    handle_removals(project,config,'filter',remove)
    return state,keep


def limiting_filters(spec,rows,target='value'):
    if not rows: return
    keep,remove = rows,[]
    # filter out trailing decimal places in `target`.
    if 'dec' in spec:
        fltr = lambda r: round(float(r),spec['dec'])
        keep = du.map_rows(fltr,target,keep)
    # filter out rows with too large of a value in `target`.
    if 'max' in spec:
        fltr = lambda v: v <= spec['max']
        keep,rem = du.split_rows(fltr,keep,target=target)
        remove += rem
    # filter out rows with too small a value in `target`.
    if 'min' in spec:
        fltr = lambda v: v >= spec['min']
        keep,rem = du.split_rows(fltr,keep,target=target)
        remove += rem
    # remove all rows where the value of `target` is not a
    # multiple of some value.  Called 'mod' because it is
    # filtering out values which do not have a clean modulus
    # for the given value... this may need renaming.
    if 'mod' in spec:
        fltr = lambda v: int(v) % spec['mod'] == 0
        keep,rem = du.split_rows(fltr,keep,target=target)
        remove += rem
    # filter out rows where the value of `target` does not
    # start with one of the expected characters strings.
    if 'head' in spec:
        head = spec['head']
        if not isinstance(head,list): head = [head]
        fltr = lambda v: any((str(v).startswith(h) for h in head))
        keep,rem = du.split_rows(fltr,keep,target=target)
        remove += rem
    # filter out rows where the value of `target` does not
    # end with and of the expected characters strings.
    if 'tail' in spec:
        tail = spec['tail']
        if not isinstance(tail,list): tail = [tail]
        fltr = lambda v: any((str(v).endswith(t) for t in tail))
        keep,rem = du.split_rows(fltr,keep,target=target)
        remove += rem
    # TEST: ensure that no filters are causing silent removals.
    assert len(rows) == (len(keep) + len(remove))
    return keep,remove




# Generate one or more new sets of data-points
# by adding and subtracting `value` fields.
def run_generators(project,config,state,data):
    generators = config['generate']
    # check generators for required fields, and
    # supply any needed default values.
    generators = check_generators(project,generators)
    # get any partially collected data from previous iteration.
    partials = state.pop('partials',{})
    # get a uid generator.
    mkuid = du.get_uid_generator()
    # initialize collectors for partials & generated rows.
    newpartials,newrows = {},[]
    for gen in generators: # iteratively run all generators.
        node,name,unit = gen['node'],gen['name'],gen['unit']
        # generate a type-checked row generator.
        mkrow = du.row_generator(node,name,unit)
        gid = mkuid(mkrow(0,0)) # get the uid of the generated rows.
        acount = len(gen['add']) # expected data-point count for `add`.
        scount = len(gen['sub']) # expected data-point count for `sub`.
        sort = {} # { timestamp: {action: { uid: value } } }
        for row in data: # iterate over data to find & sort matches.
            uid = mkuid(row) # get the row uid.
            if uid in gen['add']:
                action = 'add'
            elif uid in gen['sub']:
                action = 'sub'
            else: continue
            tid = str(int(row.timestamp)) # generate time id.
            if not tid in sort: # initialize new time point if needed.
                sort[tid] = {'add': {}, 'sub': {}}
            sort[tid][action][uid] = row.value
        if gid in partials: # get any partials if they exist.
            for tid in sort:
                if not tid in partials[gid]: continue
                pa = partials[gid][tid].get('add',{})
                ps = partials[gid][tid].get('sub',{})
                sort[tid]['add'].update(pa)
                sort[tid]['sub'].update(ps)
        # iterate though the fully populated sorting,
        # generating calculated data-points.
        for tid in sort:
            ac = len(sort[tid]['add']) # `add` count.
            sc = len(sort[tid]['sub']) # `sub` count.
            # If one or more data-points are still missing,
            # save the collected data to `newpartials`.
            if not ac == acount or not sc == scount:
                if not gid in newpartials:
                    newpartials[gid] = {}
                newpartials[gid][tid] = sort[tid]
                continue
            # calculate value of new row/data-point.
            val = sum(sort[tid]['add'].values())
            val -= sum(sort[tid]['sub'].values())
            row = mkrow(tid,val) # pass time & value to generator.
            newrows.append(row)
    # save partials to `sate` if appropriate.
    if newpartials:
        state['partials'] = newpartials
        state['partials-file'] = 'partial-calcs'
    data += newrows
    return state,data



def check_generators(project,generators):
    default = lambda: {'node':project,'unit':'undefined','sub':[]}
    required = ['name','add']
    checked = []
    for gen in generators:
        for req in required:
            if not req in gen:
                raise Exception('generator missing required field: '+req)
        new = default()
        new.update(gen)
        checked.append(new)
    return checked

# run identity-level replacements (e.g.; name="foo" to
# name="bar").
def run_replacements(project,config,state,data):
    if not data: return state,data # handle no-rows case.
    # generate a basic error message template for this section.
    mkerr = reshape_error("running value-based replacement operations")
    # generate the dict of replacements from the `replace` spec.
    replacements = {du.fmt_string(k): v for k,v in config['replace'].items()}
    settings = config.get('settings',{}) # get handle to `settings`.
    uidsort = sort_by_uid(settings,data) # sort rows by their uids.
    target = settings.get('to-replace',[]) # get target spec if it exists.
    # if only one target is declared, ensure it is still in list form.
    target = target if isinstance(target,list) else [target]
    remapped = [] # collector for successfully remapped rows.
    # iteratively run replacements on all rows.
    for uid,umap in replacements.items():
        if not umap: continue # skip empty mappings & mappings set to `false`.
        # if only one target is declared, ensure it is still in list form.
        if not isinstance(umap,dict) and not isinstance(umap,list):
            umap = [umap]
        # if target(s) are in list form, them to their dict form.
        if isinstance(umap,list):
            # list-form mappings must be of same size as `target`.
            if not target or len(umap) != len(target):
                error = mkerr('''arguments should be of equal size:
                    `to-replace`: {}\n     `{}`: {}'''.format(target,uid,umap))
                raise Exception(error)
            # expand umap into the form: `{'field': value}`.
            umap = {f:v for f,v in zip(target,umap)}
        # get all rows that match `uid`.
        rows = uidsort.pop(uid,[])
        # generate a handy-dandy row converter.
        remap = lambda row: du.update_row(umap,row)
        # remap rows to their new form.
        newrows = list(map(remap,rows))
        # add remapped rows to the collector.
        remapped += newrows
    # if any rows remain in uidsort, pass off to handler.
    if uidsort:
        unmapped = []
        for rows in uidsort.values():
            unmapped += rows
        handle_removals(project,config,'replace',unmapped)
    return state,remapped



def sort_by_uid(settings,rows):
    key = settings.get('uid-key',None)
    mkuid = du.get_uid_generator(key)
    uidsort = {}
    for row in rows:
        uid = mkuid(row)
        if not uid in uidsort:
            uidsort[uid] = []
        uidsort[uid].append(row)
    return uidsort


def sort_by_timestamp(rows):
    timesort = {}
    for row in rows:
        tid = str(int(row.timestamp))
        if not tid in timesort:
            timesort[tid] = []
        timesort[tid].append(row)
    return timesort

def handle_removals(project,config,step,rows):
    if not rows: return
    key = 'on-{}'.format(step)
    if not key in config['settings']: return
    action = config['settings'][key]
    if action == 'discard': return
    elif action == 'archive':
        fu.save_archive(project,step,rows)
    elif action == 'error':
        errdata(project,rows,txt = step + 'err')
    else:
        raise Exception('unrecognized action: ' + action)
