#!/usr/bin/env python3
import os.path as path
import time
import toml
import json
import csv
import os

# various utilities used for file io,
# including loading project configuration,
# state, etc...

# generate a list of all project directories.
# ignores directories with a `.` in their name.
def get_projects():
    directory = 'tmp/projects/'
    if not path.isdir(directory):
        raise Exception('expected project folder: ' + directory)
    dirlist = list_dirs(directory)
    projects = [d for d in dirlist if not '.' in d]
    return projects


# load the configuration file for a given project.
def get_config(project):
    directory = 'tmp/projects/{}/'.format(project)
    core = load_file(directory,'config')
    config = expand(directory,core)
    return config


# load existent state files if any.
def get_state(project):
    directory = 'tmp/projects/{}/state-files/'.format(project)
    if not path.isdir(directory):
        return {}
    files = list_files(directory)
    state = {}
    for f in files:
        parse = get_parser(f,strict=False)
        if not parse: continue
        name = '.'.join(f.split('.')[:-1])
        with open(directory + f) as fp:
            data = parse(fp)
        state[name] = data
    return state


# save all elements of the current state object.
def save_state(project,state):
    print(state)
    directory = 'tmp/projects/{}/state-files/'.format(project)
    if not path.isdir(directory):
        os.makedirs(directory)
    for key in state:
        val = state[key]
        print(val)
        if not val: continue
        fname = '{}.toml'.format(key)
        with open(directory + fname,'w') as fp:
            toml.dump(val,fp)


# recursively expand all `-file` fields
# within some existing dict of data.
def expand(directory,data):
    collector = {}
    # iteratively expand all `-file` fields.
    for key in data:
        if not key.endswith('-file'):
            collector[key] = data[key]
            continue
        new = '-'.join(key.split('-')[:-1])
        exp = load_file(directory,data[key])
        collector[new] = exp
    # recursively expand all dict subfields.
    for key in collector:
        val = collector[key]
        if isinstance(val,dict):
            exp = expand(directory,val)
            collector[key] = exp
    return collector


# load a target file.
def load_file(directory,target):
    files = list_files(directory)
    match = [f for f in files if f.startswith(target)]
    if not match:
        raise Exception('no file matching: ' + target)
    filename = match.pop()
    parse = get_parser(filename)
    with open(directory + filename) as fp:
        data = parse(fp)
    return data


# load a parser for some config file.
def get_parser(filename,strict=True):
    if filename.endswith('toml'):
        parse = lambda fp: toml.load(fp)
    elif filename.endswith('json'):
        parse = lambda fp: json.load(fp)
    elif not strict: return None
    else: raise Exception('unknown filetype: ' + filename)
    return parse


# list all files in a directory.
def list_files(directory):
    dirlist = os.listdir(directory)
    fltr = lambda f: path.isfile(directory + f)
    return list(filter(fltr,dirlist))


# list all directories in a directory.
def list_dirs(directory):
    dirlist = os.listdir(directory)
    fltr = lambda f: path.isdir(directory + f)
    return list(filter(fltr,dirlist))


# return all elements from a list of files
# which match the specified filetype
def match_filetype(files,filetype):
    if filetype == '*': return files
    filetype = filetype.lower()
    matches = []
    for name in files:
        ext = name.split('.').pop().lower()
        if ext == filetype:
            matches.append(name)
    return matches


# archiving shortcut for steps which archive rows,
# e.g.; when removed during value-based filtering.
def save_archive(project,step,rows):
    fname = str(step) + '-' + str(int(time.time()))
    fpath = 'tmp/archive/{}/'.format(project)
    if not path.isdir(fpath):
        os.makedirs(fpath)
    filepath = fpath + fname + '.csv'
    save_csv(filepath,rows,append=True)


# saves all rows to the file specified by `filepath`.
# automatically infers headers from the `_fields` method
# of the `namedtuple` object.  can be optionally set to
# `append` mode, which appends the data & skips writing
# header names if the target csv already exists.
def save_csv(filepath,rows,append=False):
    if not rows: return
    # get the field names of our data.
    fields = rows[0]._fields
    # if append is true and the file already exists, set
    # mode to `append`, else set mode to `write`.
    mode = 'a' if append and path.isfile(filepath) else 'w'
    # make sure the user is appraised of a file being written.
    print('writing {} rows to {}'.format(len(rows),filepath))
    # open the file with the appropraite mode.
    with open(filepath,mode) as fp:
        # let the `csv` module handle formatting.
        writer = csv.writer(fp)
        # if we are writing to a new file, we should
        # write the field names as our first row.
        if mode == 'w':
            writer.writerow(fields)
        # iteratively write all rows to our file.
        for row in rows:
            writer.writerow(row)
