# scrape-util

## About

This application aims to provide a unified and simple method of
moving and reshaping sensor data.  It is being developed for
use in environmental research labs, but its attempts to make minimal
assumptions about application.  The core of the project focuses around
human-readable configuration files which allow the end user
to describe a wide range of data acquisition, reshaping, and
uploading/storage actions.

Internally, this application consists of a series of small functional-style
components which make it easy to provide powerful configuration options,
and allow for the quick and simple addition of new features as the need
arises.


## Basic Usage

This section walks though a minimal example of using the application,
including an explanation of the configuration file format used throughout
this program. This section is not necessary for comprehension, but it is
highly recommended.

-----

The quickest way to get started using this application is to run
through an example project.  You can have any number of projects,
each with their own configuration options and persistent
state.  Upon startup, the program looks in [`tmp/`](./tmp/)
for project configurations.  The bare minimum project conists
of a single file; `tmp/projects/project-name/config.toml`, where
`project-name` is the name of the specified project.  

If we want to start a project called `room-sensors`, we just
create a directory named `room-sensors` in our projects folder,
and place our configuration file inside it.  The configuration
file has two required sections, `acquire` and `export`.  This
tells the program where to get the data from, and where to put it.

Any number of sources and destinations can be defined.  An empty, but
technically valid, project configuration would just look like this:

```toml
[acquire]
# ...

[export]
# ...
```

Of course, this isn't very useful.  Lets see an example where we poll
the `egauge` power-monitor API, and save its output to a `csv` file:

```toml
[acquire.egauge]
gauges = { some-gauge = 12345 }

[export]
csv = true

```

The `toml` configuration format is very flexible in terms of how we
represent heirarchical data-structures.  If you plan to make extensive
use of this project, I would suggest reading the official `toml`
[specification](https://github.com/toml-lang/toml).  In short, `toml`
files represent tables of key-value pairs.  the `.` syntax in
the section header represents a nested table.  We could just as
easily write the `acquire` section of the above example in a few
other ways:

```toml
[acquire]
egauge = { gauges = { some-gauge = 12345 } }
```

```toml
[acquire.egauge.gauges]
some-gauge = 12345
```

In addition to the functionality of the `toml` spec, this program implements
one additional feature in configuration files.  Any key ending in `-file`
is assumed to point to the name of another file which should be used
to fill in the value(s) of that key.  We could represent the original
example in two separate files like so:

Contents of `config.toml`:
```toml
[acquire]
egauge-file = "gauge-config"

[export]
csv = true
```

Contents of `gauge-config.toml`:
```toml
[gauges]
some-gauge = 12345
```

Notice that we omit the file extension when declaring the `-file` key's
value.  This is because all configurations can be interchangeably loaded
from `toml` or `json` files.  The `toml` format is generally pereferable
for hand-written files, but programmatically-generated configurations may
be more suited for `json` encoding.

This program is broken into isolated modules which are independently
defined.  All modules in the `acquire` category add data-points to
the pipeline in a single generalized format.  Similarly, all sub-modules
in the `export` section take data from the pipeline and transform it into
some kind of output.  Between these two steps, we have the optional `reshape`
category of modules, which apply modifications to the data.

The `reshape` category is roughly divided into two sub-categories;
`value` and `field`.  Value-level reshaping encompasses all modifications
the the internal state of data-points, such as rounding-down floating-point
data, swapping/replacing categorical data, and so-on.  Field-level reshaping
encompases modifications of the structure of data, such as reordering of
fields, removal of fields, or 

## Advanced Usage 

TODO
