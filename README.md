portable-xrootd
===============

portable-xrootd is a tarball that contains the XRootD daemons and dependencies
that can be used to run a Pelican cache or origin, without needing to install
them as root.  In addition, there are helper scripts to set the environment
(PATH, LD_LIBRARY_PATH, etc.) for finding the libraries.

The tarballs are operating-system-specific, since they use shared libraries
from the system.  You must download the tarball appropriate for your operating
system and architecture, or build them from scratch (see
["Rebuilding"](#rebuilding)).

This project is based on work from the
[OSG Worker Node Tarballs](https://github.com/opensciencegrid/tarball-client).

Dependencies
------------
A stock install of the distribution you are using the tarball for should be
sufficient, though a minimal container image may be missing the necessary
libraries.  You will need:

- tar
- gzip
- python3
- openssl
- (if building tarballs) docker/podman

Supported distributions include:
- EL10
- EL9
- EL8

Usage
-----

### General usage

1. Download or build the tarball appropriate for your distribution and extract it.
2. cd into the extracted directory.
3. Run the `portable-xrootd/post-install` script.  The script will create
   `setup.sh`, `setup.csh`, and `tarball-run` files.
4. Configure Pelican by creating and editing `$HOME/.config/pelican.yaml`.
   (You can also use the `PELICAN_*` environment variables.)

To set up your environment, run
    source setup.sh
or
    source setup.csh
(depending on your shell).

You can also run any command with the `tarball-run` in order to run it with
the environment set up.

### pelican-with-xrootd tarball

This contains the XRootD dependencies as well and the pelican-server itself.

Example 1 (assumes `sh` shell):

```
tar -xf pelican-with-xrootd-7.22.0-1.el9.tar.gz
cd pelican-with-xrootd
./portable-xrootd/post-install
### Set up environment of running shell:
source setup.sh
### Start the cache (you should configure it first):
pelican-server cache serve
```

Example 2 (assumes `sh` shell):

```
tar -xf pelican-with-xrootd-7.22.0-1.el9.tar.gz
cd pelican-with-xrootd
./portable-xrootd/post-install
### Start the cache (you should configure it first):
./tarball-run pelican-server cache serve
```

### xrootd-for-pelican tarball

This tarball contains the XRootD dependencies for Pelican but does not include
Pelican itself.  Download a version of the Pelican server and extract it into
$PATH.

Example 1 (assumes `sh` shell):

```
tar -xf xrootd-for-pelican-5.9.1-1.el9.tar.gz
cd xrootd
./portable-xrootd/post-install
### Set up environment of running shell:
source setup.sh
### Start the cache (you should configure it first):
pelican-server cache serve
```

Example 2 (assumes `sh` shell):

```
tar -xf xrootd-for-pelican-5.9.1-1.el9.tar.gz
cd xrootd
./portable-xrootd/post-install
### Start the cache (you should configure it first):
./tarball-run pelican-server cache serve
```

### pelican-no-s3, xrootd-no-s3 tarballs

These are the same as the `pelican-with-xrootd` and `xrootd-for-pelican`
tarballs, except without the plugin needed to run origins that use S3 as
their object store, because that plugin is not available on EL8.


Rebuilding
----------

Building a tarball requires Docker or Podman.
To make tarballs for all supported distro versions for each bundle, run:

    ./make-tarball

To only build tarballs for a specific bundle, pass the bundles as arguments,
for example:

    ./make-tarball pelican-with-xrootd

To select a specific distro version, add `--dver`:

    ./make-tarball pelican-with-xrootd --dver el9
