#!/usr/bin/env python
import configparser
import os
import shutil
import subprocess
import sys
import tempfile
from optparse import OptionParser
from pathlib import Path
from typing import Optional

# make sure we can find our imports
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


import docker
import stage2
from common import (
    VALID_DVERS,
    Error,
    errormsg,
    sanitize_image_tag,
    statusmsg,
    to_str,
)

BUNDLES_FILE = 'bundles.ini'


def check_tools():
    ret = True
    for tool in ["docker", "tar"]:
        if not shutil.which(tool):
            errormsg("Required executable '%s' not found" % tool)
            ret = False
    return ret


def make_tarball(
    *,
    bundlecfg: configparser.RawConfigParser,
    bundle: str,
    dver: str,
    image_name: str,
    patch_dirs,
    prog_dir,
    stage_dir: Path,
    relnum="0",
    extra_repos=None,
    version=None,
):
    """Run all the steps to make a non-root tarball.
    Returns (success (bool), tarball_path (relative), tarball_size (in bytes))

    """
    extra_repos = extra_repos or []

    flags = [f"--enablerepo={repo}" for repo in extra_repos]

    doc = docker.Docker()
    dockerfile = docker.render_dockerfile(
        bundlecfg=bundlecfg,
        bundle=bundle,
        dver=dver,
        flags=flags,
    )
    try:
        doc.build(dockerfile, image_name)
    except (OSError, subprocess.CalledProcessError) as err:
        errormsg(f"Failed to build Docker image: {err}")
        return (False, None, 0)

    stage_dir.mkdir(parents=True, exist_ok=True)
    layer_tarball_path = stage_dir / "layer.tar"
    try:
        docker.extract_top_layer(image_name, layer_tarball_path)
    except Error as err:
        errormsg(f"Failed to extract top layer: {err}")
        return (False, None, 0)

    if not version:
        try:
            rpm_nvrs = stage2.get_rpm_nvrs_from_tarball(layer_tarball_path)
            version = rpm_nvrs[bundlecfg[bundle]["versionrpm"]][1]
        except KeyError:
            version = "unknown"

    tarball_name = bundlecfg[bundle]["tarballname"] % {
        "version": version,
        "relnum": relnum,
    }

    statusmsg("Making stage 2 tarball")
    if not stage2.make_stage2_tarball(
        tarball_name,
        layer_tarball_path=layer_tarball_path,
        stage_dir=stage_dir,
        patch_dirs=patch_dirs,
        dver=dver,
    ):
        errormsg(
            f"Making stage 2 tarball unsuccessful. "
            f"Files have been left in '{stage_dir}'. "
            f"Image has been left as '{image_name}'."
        )
        return (False, None, 0)
    tarball_size = os.stat(tarball_name)[6]

    try:
        doc.do("rmi", image_name)
    except subprocess.CalledProcessError as err:
        errormsg(f"Warning: Failed to clean up image {image_name}: {err}")

    return (True, tarball_name, tarball_size)


def parse_cmdline_args(argv):
    parser = OptionParser(
        """
    %prog [options] --bundle=<bundle> --dver=<dver>
or: %prog [options] --bundle=<bundle> --all
"""
    )
    parser.add_option(
        "-v",
        "--version",
        default=None,
        help="Version of the tarball; will be taken from the versionrpm of the bundle if not specified",
    )
    parser.add_option(
        "-r", "--relnum", default="1", help="Release number. Default is %default."
    )
    parser.add_option(
        "-d",
        "--dver",
        help="Build tarball for this distro version. Must be one of ("
        + ", ".join(VALID_DVERS)
        + ")",
    )
    parser.add_option(
        "-a",
        "--all",
        default=False,
        action="store_true",
        help="Build tarballs for all distro versions.",
    )
    parser.add_option(
        "--bundle",
        dest="bundles",
        action="append",
        default=[],
        help=f"Names of bundles (from {BUNDLES_FILE}) to make tarballs for",
    )
    parser.add_option(
        "--extra-repos",
        dest="extra_repos",
        action="append",
        help="Extra yum repos to use",
    )

    options, args = parser.parse_args(argv[1:])

    if options.dver and options.dver not in VALID_DVERS:
        parser.error("--dver must be in " + ", ".join(VALID_DVERS))
    if not options.all and not options.dver:
        parser.error("Either --all or --dver must be specified.")

    return (options, args)


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv or sys.argv
    # prog_name = os.path.basename(argv[0])
    prog_dir = os.path.dirname(argv[0])

    options, args = parse_cmdline_args(argv)

    statusmsg("Checking required tools")
    if not check_tools():
        return 127

    bundlecfg = configparser.RawConfigParser()
    bundlecfg.read(os.path.join(prog_dir, BUNDLES_FILE))

    if options.bundles:
        bundles = options.bundles
    else:
        if bundlecfg.has_option('GLOBAL', 'default_bundles'):
            bundles = bundlecfg.get('GLOBAL', 'default_bundles').split(' ')
        else:
            errormsg("Option not found: section GLOBAL, key default_bundles")
            return 2

    if not bundles:
        errormsg("No bundles.  Exiting")
        return 1

    failed_paramsets = []
    written_tarballs = []
    for bundle in bundles:
        if options.all:
            dvers = bundlecfg.get(bundle, 'dvers').split()
        else:
            dvers = [options.dver]

        for dver in dvers:
            stage_dir_parent = tempfile.mkdtemp(prefix=f'stagedir-{dver}-')
            stage_dir = Path(stage_dir_parent) / bundlecfg.get(bundle, 'dirname')

            image_name = (
                sanitize_image_tag(bundle)
                + ":"
                + sanitize_image_tag(
                    os.path.basename(stage_dir_parent)[len('stagedir-') :]
                )
            )

            patch_dirs: list[str] = []
            if bundlecfg.has_option(bundle, 'patchdirs'):
                patch_dirs = [
                    os.path.join(prog_dir, x)
                    for x in (
                        bundlecfg.get(bundle, 'patchdirs') % {'dver': dver}
                    ).split()
                ]

            (success, tarball_path, tarball_size) = make_tarball(
                bundlecfg=bundlecfg,
                bundle=bundle,
                dver=dver,
                image_name=image_name,
                patch_dirs=patch_dirs,
                prog_dir=prog_dir,
                stage_dir=stage_dir,
                relnum=options.relnum,
                extra_repos=options.extra_repos,
                version=options.version,
            )

            if success:
                tarball_filecount = "?"
                try:
                    with os.popen("tar tzf %s | wc -l" % tarball_path) as ph:
                        tarball_filecount = int(to_str(ph.read()))
                except (OSError, ValueError) as e:
                    print("error getting file count: %s" % e)
                written_tarballs.append([tarball_path, tarball_size, tarball_filecount])
                print(
                    "Tarball created as {0}, size {1:,} bytes, {2:,} files".format(
                        tarball_path, tarball_size, tarball_filecount
                    )
                )
            else:
                failed_paramsets.append([bundle, dver])
                continue

            statusmsg("Removing temp dirs")
            shutil.rmtree(stage_dir_parent, ignore_errors=True)
        # end for dver in dvers
    # end for bundle in options.bundles

    if written_tarballs:
        statusmsg("The following tarballs were written:")
        for tarball in written_tarballs:
            print(
                f"     path: {tarball[0]:<50} size: {tarball[1]:>12,} bytes {tarball[2]:>6,} files"
            )
    if failed_paramsets:
        errormsg("The following sets of parameters failed:")
        for paramset in failed_paramsets:
            print("    bundle: %-20s dver: %3s" % (paramset[0], paramset[1]))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
