"""Run LibreOffice headless inside a short-lived, locked-down container.

Opt-in isolation for the office `convert` tool: set ``OFFICE_USE_CONTAINER=1``
so conversions run in a throwaway container with no network, all Linux
capabilities dropped, a non-root user, memory/pid limits and no privilege
escalation — instead of invoking ``soffice`` directly on the host.

Env:
  OFFICE_CONTAINER_IMAGE   image providing `soffice` (default: libreoffice:latest)
  OFFICE_CONTAINER_MEM     container memory limit  (default: 512m)
"""
import os


def run_libreoffice_container(src_path: str, output_dir: str, to: str = 'pdf',
                              image: str = None, timeout: int = 180) -> str:
    # `docker` is heavy and optional — import lazily so loading this module
    # (and the office handler) never fails when it isn't installed.
    import docker

    image = image or os.environ.get('OFFICE_CONTAINER_IMAGE', 'libreoffice:latest')
    src_abs = os.path.abspath(src_path)
    src_dir = os.path.dirname(src_abs)
    src_name = os.path.basename(src_abs)
    output_abs = os.path.abspath(output_dir)

    # The conversion target governs both the soffice flag and the output name.
    ext = (to or 'pdf').split(':', 1)[0]
    out_path = os.path.join(output_abs, os.path.splitext(src_name)[0] + '.' + ext)

    client = docker.from_env()
    try:
        logs = client.containers.run(
            image,
            ['soffice', '--headless', '--convert-to', to,
             '--outdir', '/output', f'/input/{src_name}'],
            volumes={
                src_dir: {'bind': '/input', 'mode': 'ro'},
                output_abs: {'bind': '/output', 'mode': 'rw'},
            },
            network_disabled=True,          # no network access
            remove=True,                    # throwaway container
            user='nobody',                  # non-root
            cap_drop=['ALL'],               # no Linux capabilities
            security_opt=['no-new-privileges'],
            mem_limit=os.environ.get('OFFICE_CONTAINER_MEM', '512m'),
            pids_limit=256,
            stdout=True, stderr=True, detach=False,
        )
    except docker.errors.ImageNotFound:
        raise RuntimeError(f'LibreOffice container image {image} not found')
    except docker.errors.APIError as e:
        raise RuntimeError(f'Docker API error: {e}')
    except Exception as e:
        raise RuntimeError(f'Error running container: {e}')

    # The container exiting 0 doesn't guarantee a file: verify it landed.
    if not os.path.isfile(out_path):
        if isinstance(logs, bytes):
            logs = logs.decode(errors='replace')
        raise RuntimeError(f'conversion produced no output: {logs}')
    return out_path
