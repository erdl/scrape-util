#!/usr/bin/env python3
from src.core.data_utils import Row
from src.core.error_utils import error_template,mklog
import src.core.file_utils as fu
import src.core.pgrm_utils as pu
import time
import os.path as path
import os

static_error = error_template('`static` data-acquisition step')

# primary entrr point: project -> config -> state -> (state,data)
def acquire(project,config,state,):
    print('running `static` data-acquisition method...\n')
    # get contents of the `settings` field; defaults to empty dict.
    settings = config.get('settings',{})
    # get the list of parser specifications.
    parsers = config['parser']
    # quick dir formatter; appends '/' if needed, but passes `None`s.
    dir_fmt = lambda d: (d if d.endswith('/') else d + '/') if d else d
    # generate the default directory to find files to parse.
    src_default = settings.get('source','tmp/inputs/{}/'.format(project))
    # generate the default directory to move successfully parsed files to.
    fmt_default = settings.get('on-fmt','tmp/archive/{}/static/'.format(project))
    # generate the default directory to move unsuccessfully parsed files to.
    err_default = settings.get('on-err','tmp/errors/{}/static/'.format(project))
    # default directory to save data from parsed files individually
    raw_default = settings.get('on-raw',False)
    # an integer representing the current time; this is used by the
    # `save_raw` function to ensure that files from different sources
    # are all sorted by the same timestamp.
    time_now = int(time.time())
    data = [] # collector for successufully generated rows.
    # iteratively run all parsers.
    for spec in parsers:
        name = spec['parser'] # name of perser to use.
        print('running static file parser: {}\n'.format(name))
        parser = get_parser(name) # load specified parser.
        on_fmt = dir_fmt(spec.get('on-fmt',fmt_default)) # fmt dest or default.
        on_err = dir_fmt(spec.get('on-err',err_default)) # err dest or default.
        on_raw = dir_fmt(spec.get('on-raw',raw_default)) # raw dest or default.
        source = dir_fmt(spec.get('source',src_default)) # file src or default.
        suffix = spec.get('suffix','*') # file suffix of targets.
        files = load_files(source,suffix) # files to parse.
        # iteratively parse all files, moving them to
        # `on_fmt` if no errors occur, and `on_err` if
        # an exception is raised by `parser`.
        print('files: ',files) # DEBUG
        for fname in files:
            fpath = source + fname
            print('attempting to parse file: {}'.format(fname))
            substate = state.get(name,{})
            try:
                substate,rows = parser.parse(project,spec,substate,fpath)
                for r in rows: assert isinstance(r,Row)
                data += rows
                if substate:
                    state[name] = substate
                else: state.pop(name,None)
                if on_raw: save_raw(on_raw,fname,rows)
                move_file(source,on_fmt,fname)
                print('{} rows acquired during parsing...\n'.format(len(rows)))
            except Exception as err:
                print('error while parsing {}: '.format(fname) + str(err))
                print('moving target file to: {}\n'.format(on_err))
                mklog(project,err)
                move_file(source,on_err,fname)
    return state,data


# save a copy of the parsed data in "raw" form to a csv,
# without any aggregation, reshaping, etc.  The data is
# saved to a file with the same name as its source (if the
# source file was not a csv, the `.csv` extension is added).
def save_raw(directory,filename,rows):
    # add `.csv` if filename is not a csv.
    name = filename if filename.endswith('.csv') else filename + '.csv'
    # generate destination directory if does not exist.
    if not path.isdir(directory): os.makedirs(directory)
    # generate full filepath for destination file.
    filepath = directory + name
    # use the default csv utility to save the rows.
    fu.save_csv(filepath,rows)


# move a file at src/name to dest/name.  If
# strict is false, dest will be created if
# it does not exist.
def move_file(src,dest,name,strict=False):
    mkerr = static_error('attempting to move file: ' + name)
    src = src if src.endswith('/') else src + '/'
    dest = dest if dest.endswith('/') else dest + '/'
    if not path.isdir(src):
        error = mkerr('source directory does not exist: ' + src)
        raise Exception(error)
    if not path.isdir(dest):
        if strict:
            error = mkerr('destination directory does not exist: ' + dest)
            raise Exception(error)
        else: os.makedirs(dest)
    frompath = src + name
    intopath = dest + name
    os.rename(frompath,intopath)


# attempts to load a list of files based on
# a given parser specification.
def load_files(source,suffix):
    mkerr = static_error('loading files for parsing...')
    if not path.isdir(source):
        error = mkerr('source directory does not exist: ' + source)
        raise Exception(error)
    files = fu.list_files(source)
    matches = fu.match_filetype(files,suffix)
    return matches

# attempts to load the specified parser.
def get_parser(parser):
    mkerr = static_error('loading static file parser: ' + parser)
    modname = 'src.acquire.parsers.{}'.format(parser)
    try:
        mod = pu.get_module(modname)
    except:
        error = mkerr('failed to load parser module: ' + parser)
        raise Exception(error)
    return mod
