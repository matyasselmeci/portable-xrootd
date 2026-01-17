import json
import os
import shutil
import subprocess
import tarfile
import tempfile

from common import Error, Pathable


class Docker:
    def __init__(self, executable=""):
        if not executable:
            self.executable = shutil.which("docker") or shutil.which("podman")
        else:
            self.executable = executable
        if not self.executable:
            raise Error("Docker executable not found")

    def do(self, *args, **kwargs):
        assert isinstance(self.executable, str)
        return subprocess.run([self.executable] + list(args), **kwargs)


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
            docker.do(["save", image], stdout=imagefh, check=True)

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
