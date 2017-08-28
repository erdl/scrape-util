#!/usr/bin/env python3
from importlib import import_module
import src.core.file_utils as file_utils
import src.core.error_utils as error_utils


# primary entry point for runtime.
# accepts two optional args: project-name,
# and a bool indicated wether or not to run
# pgrm wrapped in a try/catch with logging.
def run(proj,start_time, end_time,wrap=False):
    projects = file_utils.get_projects()
    torun = projects if proj == 'all' else proj
    if not isinstance(torun,list): torun = [torun]
    for project in torun:
        if not project in projects:
            err = 'could not find project folder matching: '
            raise Exception(err + str(project))
    # alias the appropriate run function as `runit`.
    runit = lambda p: run_wrapped(p, start_time, end_time) if wrap else run_project(p, start_time, end_time)
    print('running {} projects...\n'.format(len(torun)))
    # iteratively run all projects.
    for project in torun:
        runit(project)


# wrapper around `run_project` which catches
# and logs any errors that arise during the
# running of the project.
def run_wrapped(project, start_time, end_time):
    try:
        run_project(project, start_time, end_time)
    except Exception as err:
        print('exception in {}:'.format(project))
        print(str(err) + '\n')
        error_utils.mklog(project,err)


# runs a single project, handling all necessary
# initialization & cleanup.  can be called externally
# with a string matching some existent project folder.
def run_project(project, start_time, end_time):
    # load the configuration file.
    config = file_utils.get_config(project)
    if not is_active(config):
        print('skipping project: {} (inactive)\n'.format(project))
        return
    else: print('running project: {}\n'.format(project))
    # load the state file(s).
    state = file_utils.get_state(project)
    # check configuration for required fields.
    check_config(project,config)
    # acquire data & updated state values.
    state,data = acquire_data(project,config['acquire'],state, start_time, end_time)
    # add any generated rows.
    # reshape the data into the desired form.
    state,data = reshape_data(project,config,state,data)
    # push data to one or more destinations.
    state = export_data(project,config,state,data)
    # save/update the state file(s).
    file_utils.save_state(project,state)
    print('finished project: {}\n'.format(project))



# Check config file for existence
# of any required fields.
def check_config(project,config):
    msg = 'no {} section defined for {}.'
    require = ['acquire','export']
    for req in require:
        if not req in config:
            raise Exception(msg.format(req,project))


# Acquire the data via specifid method.
# Returns data and a new state value.
def acquire_data(project,config,state, start_time, end_time):
    data = []
    for method in config:
        if not is_active(config[method]):
            print('skipping acquire method: ',method)
            print('(flagged as inactive)\n')
            continue
        substate = state.get(method,{})
        subconf = config[method] if isinstance(config[method],dict) else {}
        scraper = get_util('acquire',method)
        substate,rows = scraper.acquire(project,config[method],substate, start_time, end_time)
        data += rows
        if substate: state[method] = substate
        else: state.pop(method,None)
    print('{} rows generated during `acquire` step.'.format(len(data)))
    return state,data

# Reshape the data via specified mapping(s).
def reshape_data(project,config,state,data):
    if not data: return state,data
    if 'reshape' in config:
        config = config['reshape']
    else: return state,data
    rutils = {}
    rord = []
    # assemble list of active reshape mappings.
    for kind in config:
        if not is_active(config[kind]): continue
        rutils[kind] = get_util('reshape',kind)
        rord.append(kind)
    # sort reshape utilites by their ORD variable.
    skey = lambda k: rutils[k].ORD
    rord = sorted(rord,key=skey)
    # run all reshape utilities across data.
    for rs in rord:
        substate = state.get(rs,{})
        subconf = config[rs] if isinstance(config[rs],dict) else {}
        substate,data = rutils[rs].reshape(project,subconf,substate,data)
        if substate: state[rs] = substate
        else: state.pop(rs,None)
    return state,data


# Save the data via specified channel(s).
def export_data(project,config,state,data):
    if not data:
        print('no values to export.')
        return state
    config = config['export']
    # iteratively run configured exports.
    for kind in config:
        if not is_active(config[kind]): continue
        substate = state.get(kind,{})
        subconf = config[kind] if isinstance(config[kind],dict) else {}
        # load & run specified export utility.
        exutil = get_util('export',kind)
        substate = exutil.export(project,subconf,substate,data)
        if substate: state[kind] = substate
        else: state.pop(kind,None)
    return state

# Generic 'utility' getter.
# Attempts to take a category & kind,
# and return a library object.
def get_util(category,kind):
    modname = 'src.{}.{}'.format(category,kind).lower()
    try: mod = import_module(modname)
    except: raise Exception('no utility at: {}'.format(modname))
    return mod

# Check a dictionary for the 'is-active'
# flag, returning true unless 'is-active'
# exists and is set to false.
def is_active(subject):
    # Check if subject is empty or False.
    if not subject: return False
    # Check if subject is simply `True`.
    if isinstance(subject,bool):
        return True
    # check if subject has an `is-active` flag.
    if 'is-active' in subject:
        if not subject['is-active']:
            return False
    # check if subject has a `settings` field.
    if 'settings' in subject:
        if not is_active(subject['settings']):
            return False
    return True
