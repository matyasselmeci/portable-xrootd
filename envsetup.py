'''Module to write the template setup.sh and setup.csh files

This is scripted because the contents of the setup files depend on the dver and
the basearch of the tarball they will be part of.

We need to write both a setup.csh.in and a setup.sh.in, and aside from the
syntax, their contents will be identical. With the shell_construct hash, we
get rid of a lot of the duplication.

shell_construct is a hash of hashes. The first key is the shell family, and the
second key identifies a shell construct -- a statement or fragment of a
statement. For example, the 'setenv' construct is to set an environment
variable.  In csh, it expands to 'setenv var "value"', and in sh, it expands to
'export var="value"'.  Each sub-hash must have the same keys.
Constructs that have arguments are lambdas; those that do not are strings.
'''

import os
import sys

shell_construct = {
    'csh': {
        'setenv': (lambda var, value: f'setenv {var} "{value}"\n'),
        'ifdef': (lambda var: 'if ($?%s) then\n' % var),
        'ifreadable': (lambda fname: 'if -r "%s" then\n' % fname),
        'else': 'else\n',
        'endif': 'endif\n',
        'source': (lambda fname: 'source "%s"\n' % (fname)),
    },
    'sh': {
        'setenv': (lambda var, value: f'export {var}="{value}"\n'),
        'ifdef': (lambda var: 'if [ "X" != "X${%s-}" ]; then\n' % var),
        'ifreadable': (lambda fname: 'if [ -r "%s" ]; then\n' % fname),
        'else': 'else\n',
        'endif': 'fi\n',
        'source': (lambda fname: '. "%s"\n' % (fname)),
    },
}


def write_setup_in_files(dest_dir, dver, basearch):
    '''Writes dest_dir/setup.csh.in and dest_dir/setup.sh.in according to the
    dver and basearch provided.

    '''

    local_ld_library_path = ":".join(
        [
            "$XROOTD_LOCATION/usr/lib64",
            "$XROOTD_LOCATION/usr/lib",  # search 32-bit libs too
        ]
    )

    ## Pelican currently doesn't depend on any Python packages, so let's skip this part.
    #
    # # Arch-independent python stuff always goes in usr/lib/, even on x86_64
    # if dver == 'el8':
    #     local_pythonpath = "$XROOTD_LOCATION/usr/lib/python3.6/site-packages"
    #     if basearch == 'x86_64':
    #         local_pythonpath += ":$XROOTD_LOCATION/usr/lib64/python3.6/site-packages"
    # elif dver == 'el9':
    #     local_pythonpath = "$XROOTD_LOCATION/usr/lib/python3.9/site-packages"
    #     if basearch == 'x86_64':
    #         local_pythonpath += ":$XROOTD_LOCATION/usr/lib64/python3.9/site-packages"
    # elif dver == 'el10':
    #     local_pythonpath = "$XROOTD_LOCATION/usr/lib/python3.12/site-packages"
    #     if basearch == 'x86_64':
    #         local_pythonpath += ":$XROOTD_LOCATION/usr/lib64/python3.12/site-packages"
    # else:
    #     raise Exception("Unknown dver %r" % dver)

    local_manpath = "$XROOTD_LOCATION/usr/share/man"

    for sh in 'csh', 'sh':
        dest_path = os.path.join(dest_dir, 'setup.%s.in' % sh)
        text_to_write = (
            "# Source this file if using %s or a shell derived from it\n" % sh
        )
        setup_local = "$XROOTD_LOCATION/setup-local.%s" % sh

        _setenv = shell_construct[sh]['setenv']
        _ifdef = shell_construct[sh]['ifdef']
        _else = shell_construct[sh]['else']
        _endif = shell_construct[sh]['endif']
        _ifreadable = shell_construct[sh]['ifreadable']
        _source = shell_construct[sh]['source']

        # Set XROOTD_LOCATION first because all the other variables depend on it
        text_to_write += _setenv("XROOTD_LOCATION", "@@XROOTD_LOCATION@@")

        for variable, value in [
            ("PATH", "$XROOTD_LOCATION/usr/bin:$XROOTD_LOCATION/usr/sbin:$PATH"),
        ]:
            text_to_write += _setenv(variable, value)

        for variable, value in [
            ("LD_LIBRARY_PATH", local_ld_library_path),
            # ("PYTHONPATH", local_pythonpath),
            ("MANPATH", local_manpath),
        ]:

            text_to_write += (
                _ifdef(variable)
                + "\t"
                + _setenv(variable, value + ":$" + variable)
                + _else
                + "\t"
                + _setenv(variable, value)
                + _endif
                + "\n"
            )

        text_to_write += (
            "\n"
            + "# Site-specific customizations\n"
            + _ifreadable(setup_local)
            + "\t"
            + _source(setup_local)
            + _endif
            + "\n"
        )

        with open(dest_path, "w") as fh:
            fh.write(text_to_write)


def main(argv):
    dest_dir, dver, basearch = argv[1:4]
    write_setup_in_files(dest_dir, dver, basearch)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
