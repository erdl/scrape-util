#!/bin/bash

DIR="path-to-utility"

# reorient to DIR
cd $DIR

# ensure that any auto-generated files won't
# break user-space reads/writes.
umask 001

echo -e 'attempting to launch scrape-util...\n'

# attempt to invoke scrape-util
./scrape-util -w

echo -e '\ngoodbye!'
