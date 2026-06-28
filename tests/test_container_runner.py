import os
import pytest


def _setup(tmp_path):
    src = tmp_path / 'in.docx'
    src.write_text('x')
    outdir = tmp_path / 'out'
    outdir.mkdir()
    return src, outdir


def test_run_passes_hardening_and_returns_output(tmp_path, monkeypatch):
    docker = pytest.importorskip('docker')
    from src.handlers import container_runner
    src, outdir = _setup(tmp_path)
    produced = outdir / 'in.pdf'

    class FakeContainers:
        def run(self, image, cmd, **kw):
            # the locked-down flags must be present
            assert kw['network_disabled'] is True
            assert kw['cap_drop'] == ['ALL']
            assert kw['user'] == 'nobody'
            assert 'no-new-privileges' in kw['security_opt']
            # the requested format must reach soffice (regression: was ignored)
            assert '--convert-to' in cmd and cmd[cmd.index('--convert-to') + 1] == 'pdf'
            produced.write_bytes(b'%PDF-1.4')
            return b'converted'

    monkeypatch.setattr(docker, 'from_env', lambda: type('C', (), {'containers': FakeContainers()})())
    out = container_runner.run_libreoffice_container(str(src), str(outdir), to='pdf')
    assert out == str(produced) and os.path.isfile(out)


def test_run_raises_when_no_output_produced(tmp_path, monkeypatch):
    docker = pytest.importorskip('docker')
    from src.handlers import container_runner
    src, outdir = _setup(tmp_path)

    class FakeContainers:
        def run(self, image, cmd, **kw):
            return b'boom'  # nothing written

    monkeypatch.setattr(docker, 'from_env', lambda: type('C', (), {'containers': FakeContainers()})())
    with pytest.raises(RuntimeError):
        container_runner.run_libreoffice_container(str(src), str(outdir))


def test_run_maps_image_not_found(tmp_path, monkeypatch):
    docker = pytest.importorskip('docker')
    from src.handlers import container_runner
    src, outdir = _setup(tmp_path)

    class FakeContainers:
        def run(self, *a, **k):
            raise docker.errors.ImageNotFound('missing')

    monkeypatch.setattr(docker, 'from_env', lambda: type('C', (), {'containers': FakeContainers()})())
    with pytest.raises(RuntimeError):
        container_runner.run_libreoffice_container(str(src), str(outdir))
