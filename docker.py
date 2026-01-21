import json
import os
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any, Mapping

from common import Error, Pathable

VALUES_DVER = {
    "el8": {
        "fromimage": "docker.io/library/almalinux:8",
        "fromstagename": "alma8core",
        "basename": "osgel8base",
    },
    "el9": {
        "fromimage": "docker.io/library/almalinux:9",
        "fromstagename": "alma9core",
        "basename": "osgel9base",
    },
}

DOCKERFILE_TEMPLATE = r"""
FROM {fromimage} AS {fromstagename}
COPY {stage1file} /stage1.lst
COPY stage1/paths-to-delete.txt /paths-to-delete.txt
RUN grep '^[@A-Za-z0-9]' /stage1.lst | xargs yum install --allowerasing --setopt install_weak_deps=false -y

FROM {fromstagename} AS {basename}
RUN yum install -y epel-release 'dnf-command(config-manager)' \
    https://repo.osg-htc.org/osg/25-main/osg-25-main-{dver}-release-latest.rpm \
    && crb enable

FROM {basename} AS {bundle}-{dver}
RUN \
    yum install -y {packages} \
    && yum clean all \
    && rpm -qa | sort > /rpm-versions.txt \
    && xargs -d '\n' -a /paths-to-delete.txt rm -rf
"""


class Docker:
    def __init__(self, executable=""):
        if not executable:
            self.executable = shutil.which("docker") or shutil.which("podman")
        else:
            self.executable = executable
        if not self.executable:
            raise Error("Docker executable not found")

    def build(self, dockerfile: str, tag: str):
        self.do(
            "build",
            ".",
            "-f",
            "-",
            "-t",
            tag,
            check=True,
            input=dockerfile.encode(),
        )

    def do(self, *args, **kwargs):
        assert isinstance(self.executable, str)
        return subprocess.run([self.executable] + list(args), **kwargs)


def render_dockerfile(
    bundlecfg: Mapping[str, Mapping[str, Any]], bundle: str, dver: str
):
    values = dict()
    values.update(VALUES_DVER[dver])
    values["bundle"] = bundle
    values["dver"] = dver
    values["stage1file"] = os.path.join(
        "stage1", bundlecfg[bundle]["stage1file"] % {"dver": dver}
    )
    values["packages"] = " ".join(bundlecfg[bundle]["packages"].split())
    return DOCKERFILE_TEMPLATE.format(**values)


def extract_top_layer(image: str, destpath: Pathable) -> None:
    """
    Takes the name of an image as an input and extracts the topmost layer
    of the image, saving it to destpath.  A layer of an image is an
    (uncompressed) tarball that will need to be extracted to get the files
    inside.

    Arguments:
        image: The name of the image to extract the topmost layer from.
        destpath: The path to save the extracted layer to.

    Returns:
        None
    """
    docker = Docker()
    tempdir = tempfile.gettempdir()
    if tempdir == "/tmp":
        tempdir = "/var/tmp"  # /var/tmp is bigger

    with tempfile.TemporaryDirectory(prefix="portabletmp", dir=tempdir) as workdir:
        image_path = os.path.join(workdir, "image.tar")

        # Export the image.
        with open(image_path, 'wb') as imagefh:
            docker.do("save", image, stdout=imagefh, check=True)

        # Open the resulting tar file.
        with tarfile.open(image_path, 'r') as tarh:

            # Extract manifest.json, which contains the name of each layer,
            # sorted newest first.
            manifest_member = tarh.getmember("manifest.json")
            manifest_fh = tarh.extractfile(manifest_member)
            if not manifest_fh:
                raise Error("Could not extract manifest.json from image")

            # Parse manifest.json
            manifest = json.load(manifest_fh)
            try:
                # Get the name (in the tarball) of the topmost layer
                topmost_layer_name = manifest[0]["Layers"][-1]
            except (KeyError, IndexError) as err:
                raise Error(f"Could not get tompost_layer from manifest.json: {err}")

            # Extract the topmost layer from the tarball and save it to destpath.
            with open(destpath, 'wb') as destfh:
                layer_member = tarh.getmember(topmost_layer_name)
                layer_fh = tarh.extractfile(layer_member)
                if not layer_fh:
                    raise Error(f"Could not extract {topmost_layer_name} from image")
                shutil.copyfileobj(layer_fh, destfh)


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
