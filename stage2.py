import glob
import os
import shlex
import subprocess
from typing import Any

import common
from common import (
    Error,
    Pathable,
    errormsg,
)


def delete_wh_files_from_tarball(tarball: Pathable) -> None:
    """
    Delete the ".wh" files from a tarball layer which are files that get created
    to signify that something has been deleted in that layer.
    """
    quoted_tarball = shlex.quote(str(tarball))
    subprocess.run(
        f"tar -tf {quoted_tarball} | grep -E '(^|/)[.]wh[.]' | xargs -r tar -f {quoted_tarball} --delete",
        shell=True,
        check=True,
    )


def extract_layer_tarball(stage_dir_abs: Pathable, layer_tarball: Pathable):
    """
    Extracts the layer tarball into the staging directory.
    """
    try:
        subprocess.run(
            ["tar", "-xf", str(layer_tarball), "-C", str(stage_dir_abs)], check=True
        )
    except (OSError, subprocess.CalledProcessError) as err:
        raise Error(f"Failed to extract layer tarball: {err}")


def patch_installed_packages(stage_dir_abs, patch_dirs):
    """Apply all patches in patch_dir to the files in stage_dir_abs

    Assumptions:
    - stage_dir_abs exists and has packages installed into it
    - patch files are to be applied in sorted order (by filename; directory
      name does not matter)
    - patch files are -p1
    - patch files end with .patch

    Return success or failure as a bool
    """

    patch_dirs_abs = [os.path.abspath(x) for x in patch_dirs]

    oldwd = os.getcwd()
    try:
        os.chdir(stage_dir_abs)
        patch_files = []
        for patch_dir_abs in patch_dirs_abs:
            patch_files += glob.glob(os.path.join(patch_dir_abs, "*.patch"))
        patch_files.sort(key=os.path.basename)
        for patch_file in patch_files:
            common.statusmsg("Applying patch %r" % patch_file)
            err = subprocess.call(['patch', '-p1', '--force', '--input', patch_file])
            if err:
                raise Error("patch file %r failed to apply" % patch_file)
    finally:
        os.chdir(oldwd)


def tar_stage_dir(stage_dir_abs, tarball):
    """tar up the stage_dir
    Assume: valid stage2 dir
    """
    tarball_abs = os.path.abspath(tarball)
    stage_dir_parent = os.path.dirname(stage_dir_abs)
    stage_dir_base = os.path.basename(stage_dir_abs)

    cmd = [
        "tar",
        "-C",
        stage_dir_parent,
        "--exclude=layer.tar",
        "-czf",
        tarball_abs,
        stage_dir_base,
    ]

    err = subprocess.call(cmd)
    if err:
        raise Error(
            f"unable to create tarball ({tarball_abs!r}) from stage 2 dir ({stage_dir_abs!r})"
        )


def fix_permissions(stage_dir_abs):
    return subprocess.call(['chmod', '-R', 'u+rwX', stage_dir_abs])


def get_rpm_nvrs_from_tarball(
    tarball: Pathable,
) -> dict[str, tuple[str, str, str]]:
    """
    Reads the package list inside the given tarball and returns the NVRs of the
    RPMs.  The NVRs are a tuple in a dict keyed by name, e.g.
    nvrs["xrootd"] = ("xrootd", "5.9.1", "1.osg24")
    """
    try:
        result = subprocess.run(
            ["tar", "--to-stdout", "-xf", tarball, "portable-xrootd/versions.txt"],
            stdout=subprocess.PIPE,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as err:
        raise Error(f"Unable to get versions from {tarball}") from err
    nvrs = {}
    for line in result.stdout.decode().splitlines():
        line = line.strip()
        try:
            name, version, release = line.rsplit("-", 2)
        except ValueError:
            continue
        nvrs[name] = (name, version, release)

    return nvrs


def make_stage2_tarball(
    tarball_name: str,
    *,
    layer_tarball_path: Pathable,
    stage_dir: Pathable,
    patch_dirs: list[str],
    dver: str,
):
    def statusmsg(msg: Any):
        common.statusmsg(f"[{dver}]: {msg}")

    statusmsg(f"Making stage2 tarball in {stage_dir}")

    stage_dir_abs = os.path.abspath(stage_dir)

    try:
        statusmsg("Deleting .wh. files from layer tarball")
        delete_wh_files_from_tarball(layer_tarball_path)

        statusmsg("Extracting layer tarball")
        extract_layer_tarball(
            stage_dir_abs=stage_dir_abs,
            layer_tarball=os.path.abspath(layer_tarball_path),
        )

        if patch_dirs:
            if isinstance(patch_dirs, str):
                patch_dirs = [patch_dirs]

            statusmsg("Patching packages using %r" % patch_dirs)
            patch_installed_packages(stage_dir_abs=stage_dir_abs, patch_dirs=patch_dirs)

        statusmsg("Fixing permissions")
        fix_permissions(stage_dir_abs)

        statusmsg("Creating tarball %r" % tarball_name)
        tar_stage_dir(stage_dir_abs, tarball_name)

        return True
    except Error as err:
        errormsg(str(err))
