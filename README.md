portable-xrootd
===============

portable-xrootd is a tarball that contains the XRootD daemons and dependencies
that can be used to run a Pelican cache or origin, without needing to install
them as root.  In addition, there are helper scripts to set the environment
(PATH, LD_LIBRARY_PATH, etc.) for finding the libraries.

The tarballs are operating-system-specific, since they use shared libraries
from the system.  You must download the tarball appropriate for your operating
system and architecture.

This project is based on work from the [OSG Worker Node Tarballs]
(https://github.com/opensciencegrid/tarball-client).

Dependencies
------------
A stock install of the distribution you are using the tarball for should be
sufficient, though a minimal container image may be missing the necessary
libraries.  You will need:

- tar
- gzip
- python3
- openssl


Usage
-----

### General usage

1. Download the tarball appropriate for your distribution and extract it.
2. cd into the extracted directory.
3. Run the `post-install/post-install` script.  The script will create
   `setup.sh`, `setup.csh`, and `tarball-run` files.

To set up your environment, run
    . setup.sh
or
    . setup.csh
(depending on your shell).
You can also run any command with the `tarball-run` in order to run it with
the environment set up.

### pelican-with-xrootd tarball

This contains the XRootD dependencies as well and the pelican-server itself.
Example:

```
tar -xf pelican-with-xrootd-7.22.0-1.el9.tar.gz
cd pelican-with-xrootd
./post-install/post-install
### Configure Pelican via PELICAN_* environment variables or $HOME/.config/pelican.yaml
./tarball-run pelican-server cache serve
```

### xrootd-for-pelican tarball

This tarball contains the XRootD dependencies for Pelican but does not include
Pelican itself.  Download a version of the Pelican server and extract it into
$PATH.
```
tar -xf xrootd-for-pelican-5.9.1-1.el9.tar.gz
cd xrootd
./post-install/post-install
### Configure Pelican via PELICAN_* environment variables or $HOME/.config/pelican.yaml
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
