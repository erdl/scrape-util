#!/usr/bin/env python3
from src.core.data_utils import Row, get_uid_generator, check_config, make_time_specs
from src.core.error_utils import error_template
import requests
import datetime

# an experimental shortcut to nicer errors :)
webctrl_error = error_template('`webctrl` data-acquisition step')

# Primary entry point for webctrl scrape.
# Returns data & updated state.
def acquire(project,config,state,start_time,end_time):
    settings = config['settings']
    # check that config is valid, parse sensor
    # parameters, and generate time specifications
    # for all active sensors.
    params,times = setup(project,config,state)
    # generate a wrapper around `exec_query` with
    # user-supplied configurations pre-applied.
    query = new_query(config['settings'],start_time,end_time)
    # initialize collectors for formatted
    # data and the new `nonce` values.
    nonce,buffs,data = {},{},[]
    # iteratively scrape all sensors.
    for uid,spec in params.items():
        # break out the webctrl-path and identity values from `spec`.
        path,*ident = (spec[k] for k in ('path','node','name','unit'))
        # pull start-time and maximum step from `times`. 
        start,step = times[uid]['init'],times[uid]['step']
        # get the buffer if it exists (default to empty list).
        buff = times[uid].get('buff',[])
        # query webctrl at `path` from `start` to `start` + `step`.
        result = query(path)
        # make a generator for the `Row` type based
        # on the supplied identity variables.
        mkrow = lambda t,v: Row(*ident,float(t//1000),float(v))
        # pass row generator and raw query-result to parser.
        rows = parse_rows(mkrow,result)
        # in the event of an empty query, set `start` value
        # as the new nonce, so we start from same place next time.
        if not rows:
            nonce[uid] = start
            continue
        # filter out any data points already in buff.
        for time in buff:
            fltr = lambda r: r.timestamp != time
            rows = list(filter(fltr,rows))
        # filter rows by timestamp.
        fltr = lambda r: r.timestamp
        stamps = [fltr(r) for r in rows] # get all timestamps.
        data += rows # add our rows to `data`.
    # add newly generate `nonce` to `state`, overwriting
    # old value if it exists.
    if settings.get('rolling-buffer',False):
        state = set_buffer(settings,state,buffs)
    return state,data


# parse rows from raw webctrl data, removing erroneous data
# and duplicates (the webctrl bulk-trend server periodically
# returns duplicate values for a given timestamp...).
def parse_rows(mkrow,data):
    # extract timestamp & value, passing them to supplied row generator,
    # and filter out erroneous values (indicated by `'?'` in webctrl data).
    raw_rows = [mkrow(r['t'],r['a']) for r in data if not '?' in r.values()]
    rows,times,dups = [],[],[] # instantiate collectors.
    # iterate over rows, sorting out duplicates by timestamp.
    for row in raw_rows:
        t = row.timestamp
        if not t in times:
            times.append(t)
            rows.append(row)
        else: dups.append(row)
    # TODO: optionally save duplicates to archive.
    return rows


# do general housekeeping before data-acquisition
# begins.  Specifically, ensure that `config` is valid,
# and that we have all necessary data in `state`.
def setup(project,config,state):
    proto_config = {'sensor':list ,'settings': {
        'server':str,'login':{'name':str,'pass':str} } }
    msg = 'checking configuration values for project: ' + project
    mkerr = webctrl_error(msg)
    check_config('webctrl',proto_config,config,mkerr=mkerr)
    # if `config` checks out, we can assess `state`
    # and add/update any missing missing values.
    nonce = state.get('nonce',{})
    params,times = setup_parameters(project,config,nonce)
    if config['settings'].get('rolling-buffer',False):
        times = get_buffer(config['settings'],state,times)
    return params,times

# accepts a dict of time specs in the form:
# {uid: {init: ..., step: ...}, ...}, adding a
# 'buff' field to each spec.  The `buff` field
# consists of a list of timestamps for which data
# has already been recorded for the given uid.
# this serves as a sanity-check when dealing with
# unreliable webctrl instances, as they have been
# known to serve data with periodic gaps.
def get_buffer(settings,state,times):
    # get the previous buffer from state.
    prev = state.get('buff',{})
    # load the buffer size.
    size = settings['rolling-buffer']
    # if user simply set `rolling-buffer` to true, then
    # we simply use the default size value.
    if isinstance(size,bool):
        size = 604800 # defaults to one-week buffer
    # iteratively add a `buff` field to all time specs.
    for uid,spec in times.items():
        init = spec['init'] - size
        step = spec['step'] + size
        buff = [t for t in prev.get(uid,[]) if t >= init]
        times[uid].update({'init':init,'step':step,'buff':buff})
    return times


# trim down the collected buffer, and attach
# it to the `state` variable.
def set_buffer(settings,state,buffs):
    # get the size of the rolling buffer.
    size = settings['rolling-buffer']
    # if user set rolling buffer flag w/ bool,
    # set size to its default value: one week.
    if isinstance(size,bool):
        size = 604800
    # filter to reduce a buffer to within `size` of its
    # most recent timestamp.
    fltr = lambda b: [t for t in b if t >= (max(b)-size)]
    # set the `buff` section of `state`.
    state['buff'] = {k: fltr(v) for k,v in buffs.items()}
    return state


# initialize sensor and time parameters from
# configuration and nonce values.  Returns two
# dicts, both organized by uid.  One containing
# sensor specifications, and the other containing
# `init` and `step` times for scraping the sensor.
def setup_parameters(project,config,nonce):
    settings,sensors = config['settings'],config['sensor']
    mkuid = get_uid_generator() # get a uid generator instance.
    params = {} # collector for parsed sensor parameters.
    # iteratively parse each sensor's configuration, generating
    # its uid and filling in default values as needed.
    for sensor in sensors:
        # skip sensors with optional `actv` field set to `false`.
        if not sensor.get('actv',True): continue
        # initialize `spec` with allowable defaults.
        spec = {'node':project,'unit':'undefined'}
        # populate spec with values from sensor.
        spec.update(sensor)
        # compile values for `node`, `name`, and `unit`.
        identity = (spec[k] for k in ('node','name','unit'))
        # pass identity to the `uid` generator.
        snid = mkuid(tuple(identity))
        # save `spec` to `params` with the sensor's `uid` as its key.
        params[snid] = spec
    # use tooling in `data-utils` to generate time specs.
    # returns a dict of form: `{'uid': {'init': .., 'step': ...},...}`
    times = make_time_specs(params,settings,nonce)
    return params,times


# Generate a pre-configured query callable
# s.t. we don't all die of excess boilerplate.
def new_query(settings,start_time,end_time):
    start_time = datetime.datetime.strptime(start_time, '%m/%d/%Y').strftime('%Y-%m-%d')
    end_time = datetime.datetime.strptime(end_time, '%m/%d/%Y').strftime('%Y-%m-%d')
    uri = settings['server']
    auth = ( settings['login']['name'], settings['login']['pass'] )
    # return a lambda fn that executes a query given
    # the args: query-string, start-time, end-time.
    lam = lambda q : exec_query(uri,q,auth,start_time,end_time)
    return lam

# Actually execute the query of the webctrl server.
def exec_query(uri,sensor,auth,start_time,end_time):
    print("querying: {}".format(sensor))
    params = {'id':sensor,'start':start_time,'end':end_time,'format':'json'}
    req = requests.post(uri,params=params,auth=tuple(auth))
    if req.status_code != 200:
        print(req.text)
        raise Exception("Query Failed w/ Status Code {}".format(req.status_code))
    return req.json()[0]['s']
