#!/usr/bin/env python3
import time
import csv
import os
import os.path as path

# exception raising shortcut, because of all the damn exceptions!
def error_template(sec):
    error_message = lambda sec,ctx,prob: '''\n
    An Error Has Occurred:\n
    Section -- {}\n
    Context -- {}\n
    Problem -- {}\n
    '''.format(sec,ctx,prob)
    template = lambda ctx: lambda prob: error_message(sec,ctx,prob)
    return template


# Generate and update a simple and readable log file.
def mklog(project,text):
    # surround error text in time & project specifiers.
    hdr  = 'logtime............{}'.format(int(time.time()))
    proj = 'project............{}'.format(project)
    ftr  = '...................endlog\n'
    # check appropriate error directory
    # and generate it if necessary.
    errdir = dirset(project)
    fpath  = errdir + 'errlog.txt'
    # generate (or append to) error log.
    with open(fpath,'a') as fp:
        write = lambda txt: print(txt,file=fp)
        write(hdr)
        write(proj)
        write(text)
        write(ftr)

# write a csv of improperly formatted
# data to an appropriate errors file.
def errdata(project,data,txt='fmterr'):
    if not data: return
    # check appropriate error directory
    # and generate it if necessary.
    errdir = dirset(project)
    # generate filename of form `txt-time.csv`.
    fpath = errdir + txt + '-'+ str(int(time.time())) + '.csv'
    # extract field names from data.
    fields = data[0]._fields
    # write data to csv.
    with open(fpath,'w') as fp:
        print('writing {} malformed rows to: {}'.format(len(data),fpath))
        writer = csv.writer(fp)
        writer.writerow(fields)
        for d in data: writer.writerow(d)

# Setup error directories if necessary.
def dirset(project):
    errdir = 'tmp/errors/{}/'.format(project)
    if not path.isdir(errdir):
        os.makedirs(errdir)
    return errdir
