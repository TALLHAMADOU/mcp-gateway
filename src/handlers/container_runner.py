import docker
import os
import tempfile
from typing import Tuple

# Simple helper to run LibreOffice inside a short-lived container with no network
# and minimal privileges. This is opt-in (only used if OFFICE_USE_CONTAINER=1).
# The function assumes the host paths exist and are mounted read-only for input
# and read-write for output.

def run_libreoffice_container(src_path: str, output_dir: str, image: str = None, timeout: int = 180) -> str:
    image = image or os.environ.get('OFFICE_CONTAINER_IMAGE', 'libreoffice:latest')
    client = docker.from_env()
    # mount src parent and output dir
    src_abs = os.path.abspath(src_path)
    src_dir = os.path.dirname(src_abs)
    src_name = os.path.basename(src_abs)
    output_abs = os.path.abspath(output_dir)
    mounts = {
        src_dir: {'bind': '/input', 'mode': 'ro'},
        output_abs: {'bind': '/output', 'mode': 'rw'},
    }
    cmd = ['soffice', '--headless', '--convert-to', os.environ.get('OFFICE_CONTAINER_CONVERT_TO', 'pdf'), '--outdir', '/output', f'/input/{src_name}']
    try:
        # run and wait (network disabled, drop capabilities)
        logs = client.containers.run(
            image,
            cmd,
            volumes=mounts,
            network_disabled=True,
            remove=True,
            user='nobody',
            stdout=True,
            stderr=True,
            detach=False,
            cap_drop=['ALL'],
            # make sure container can't access host network
        )
        # logs may be bytes
        if isinstance(logs, bytes):
            logs = logs.decode(errors='replace')
        # build output path guess
        ext = os.environ.get('OFFICE_CONTAINER_CONVERT_TO', 'pdf').split(':', 1)[0]
        out_name = os.path.splitext(src_name)[0] + '.' + ext
        return os.path.join(output_abs, out_name)
    except docker.errors.ImageNotFound:
        raise RuntimeError(f'LibreOffice container image {image} not found')
    except docker.errors.APIError as e:
        raise RuntimeError(f'Docker API error: {e}')
    except Exception as e:
        raise RuntimeError(f'Error running container: {e}')
