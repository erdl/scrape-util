#!/usr/bin/env python3
import src.core.data_utils as du
import src.core.error_utils as eu
import requests
import time
import datetime

egauge_error = eu.error_template("`egauge` data-acquisition step")


# primary entry point for scrape of egauges.
# Returns any acquired data & updated nonce.
def acquire(project, config, state, start_time, end_time):
    starts,stops = setup_times(project,config,state, start_time, end_time)
    gauges = config['gauges']
    nonce = {k:v for k,v in starts.items()}
    data = []
    fltr = lambda r : r.timestamp
    for gid in gauges:
        print('querying egauge: {}...'.format(gid))
        raw = query(gauges[gid],starts[gid],stops[gid])
        if not raw: continue
        rows = fmt_query(gid,raw)
        if not rows: continue
        fltr = lambda r: r.timestamp
        nonce[gid] = max(rows,key=fltr).timestamp
        data += rows
    print('egauge queries complete...\n')
    if 'filter' in config:
        data = run_filters(config['filter'],data)
    state['nonce'] = nonce
    return state,data


# a limited data filtering functionality, because method
# acquired a bulk dump of egauge data, and it may be useful
# to pre-imtively remove unwanted values.
def run_filters(filters,data):
    mkerr = egauge_error("filtering acquired data-points")
    rows = [r for r in data]
    for spec in filters:
        mode = spec.pop("mode")
        ismatch,nomatch = du.match_rows(spec,rows)
        if mode == "positive":
            rows = ismatch
        elif mode == "negative":
            rows = nomatch
        else:
            error = mkerr("unrecognized filter mode: " + str(mode))
            raise Exception(error)
    return rows


# initialzie start and stop times for all gauges.
def setup_times(project,config,state,start_time,end_time):
    settings = config.get('settings',{})
    nonce = state.get('nonce',{})
    gauges = config['gauges']
    now = time.time()
    init = settings.get('init-time',now-86400)
    step = settings.get('step-time',31536000)
    mkstop = lambda s: min((s+step,now))
    start,stop = {},{}
    start_time = int(time.mktime(datetime.datetime.strptime(start_time, "%m/%d/%Y").timetuple()))
    end_time = int(time.mktime(datetime.datetime.strptime(end_time, "%m/%d/%Y").timetuple()))
    for gid in gauges:
        start[gid] = start_time
        stop[gid] = end_time
    return start,stop


# Query a specified egauge.
# Returns a dictionary of all columns w/ headers as keys.
def query(gauge,start,stop):
    uri = 'http://egauge{}.egaug.es/cgi-bin/egauge-show?c&C&m'
    params = {'t': int(start), 'f': int(stop)}
    r = requests.get(uri.format(gauge),params=params)
    if not r.status_code == 200:
        print('\n------------- warning -------------')
        print('  query failed with status code: ',r.status_code)
        print('  check gauge if this problem persists')
        print('-----------------------------------\n')
        return {}
    # break up the recieved csv into two-dimensional list structure.
    rows = [[y for y in x.split(',')] for x in r.text.splitlines()]
    if not rows: return {}
    headers = [h.replace('"','') for h in rows.pop(0)]
    columns = list(zip(*rows))
    if not columns: return {}
    # reshape columns into form { header : [ values ] }
    return {h: list(map(float,columns[i])) for i,h in enumerate(headers)}

# Convert into row format.
# Returns list of named tuples.
def fmt_query(gauge_id,data):
    # separate times from readings.
    dtimes = data['Date & Time']
    values = {k: data[k] for k in data if k != 'Date & Time'}
    formatted = []
    # break out readings into form standard form:
    # ( node, sensor, unit, timestamp, value )
    for sn in values:
        name,unit = parse_sntxt(sn)
        mkrow = du.row_generator(gauge_id,name,unit)
        formatted += [mkrow(t,v) for t,v in zip(dtimes,values[sn])]
    return formatted

# Split the egauge supplied sensor/column name
# into separate units and sensor id.
# Expects egauge column headers to be
# of the form `SensorName [unit]`.
def parse_sntxt(sensor):
    try:
        unit = sensor.split('[').pop().replace(']','').replace(' ','')
        name = sensor.split(' [').pop(0).lower()
    except Exception as err:
        print('failed to parse: {}'.format(sensor))
        print('parse error: {}'.format(err))
        # if parse fails, lower case column name is used as
        # sensor id, and unit is listed as "undefined".
        unit = 'undefined'
        name = sensor.lower()
    return name,unit
