"""CI hardening: exercise real workflow commands with Docker subprocess stubs."""
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ['qt_app', 'vlc', 'app_dirs', 'db_migrations', 'fonts', 'rust', 'theme_bridge', 'qml_files', 'qml_shell']


def report():
    return dict(ok=True, frozen=True, checks=dict.fromkeys(CHECKS, True))


@pytest.fixture
def probe_env(tmp_path):
    bindir = tmp_path / 'bin'; bindir.mkdir()
    output = tmp_path / 'out'; output.mkdir()
    image = tmp_path / 'fixture.AppImage'; image.write_bytes(b'synthetic executable fixture')
    docker = bindir / 'docker'
    docker.write_text('''#!/usr/bin/env python3
import os,sys,json,pathlib
out=pathlib.Path(os.environ['FAKE_OUTPUT'])
(out/'docker-args.json').write_text(json.dumps(sys.argv[1:]))
rc=int(os.environ.get('FAKE_DOCKER_EXIT','0'))
if rc: sys.exit(rc)
(out/'smoke.json').write_text(os.environ.get('FAKE_REPORT','{}'))
(out/'smoke.log').write_text('DOREMI_SMOKE_OK\\n')
''')
    docker.chmod(0o755)
    env = dict(os.environ, PATH=str(bindir)+os.pathsep+os.environ['PATH'],
               FAKE_OUTPUT=str(output), FAKE_REPORT=json.dumps(report()),
               GITHUB_WORKSPACE=str(tmp_path), APPIMAGE_FILE=image.name, RUNNER_TEMP=str(tmp_path))
    return env, output, image, bindir


def workflow_step(name):
    workflow = yaml.safe_load((ROOT/'.github/workflows/linux-appimage.yml').read_text())
    return next(s for s in next(iter(workflow['jobs'].values()))['steps'] if s.get('name','').startswith(name))


@pytest.mark.parametrize('name', ['Clean-env test', 'Extra distro probe'])
def test_workflow_propagates_docker_failure_and_never_emits_pass(probe_env, name):
    env, output, image, _ = probe_env
    env['FAKE_DOCKER_EXIT'] = '42'
    step = workflow_step(name)
    result = subprocess.run(['bash', '-e', '-c', step['run']], env=env, cwd=ROOT, text=True, capture_output=True)
    assert result.returncode != 0, result.stdout + result.stderr
    assert '=PASS' not in result.stdout
    if name.startswith('Extra'):
        assert step.get('continue-on-error') is True
        assert '=FAIL' in result.stdout + result.stderr
    else:
        assert not step.get('continue-on-error', False)


def run_probe(env, output, image):
    return subprocess.run(['bash', str(ROOT/'packaging/appimage/probe-clean-env.sh'),
        str(image), '22.04', str(output)], env=env, text=True, capture_output=True)


def test_probe_keeps_original_readonly_and_validates_success(probe_env):
    env, output, image, _ = probe_env
    before = image.read_bytes(), image.stat().st_mode
    result = run_probe(env, output, image)
    assert result.returncode == 0, result.stderr
    args = json.loads((output/'docker-args.json').read_text())
    assert any(str(image)+':/mnt/Doremi.AppImage:ro' == a for a in args)
    assert image.read_bytes() == before[0] and image.stat().st_mode == before[1]
    assert 'CLEAN_ENV_2204=PASS' in result.stdout


@pytest.mark.parametrize('mutation', ['ok_false', 'missing_check', 'false_check', 'truthy_check', 'not_frozen', 'invalid_json'])
def test_probe_rejects_incomplete_or_failed_smoke_report(probe_env, mutation):
    env, output, image, _ = probe_env
    data = report()
    if mutation == 'ok_false': data['ok'] = False
    if mutation == 'missing_check': del data['checks']['vlc']
    if mutation == 'false_check': data['checks']['qml_shell'] = False
    if mutation == 'truthy_check': data['checks']['vlc'] = 'true'
    if mutation == 'not_frozen': data['frozen'] = False
    env['FAKE_REPORT'] = 'broken' if mutation == 'invalid_json' else json.dumps(data)
    result = run_probe(env, output, image)
    assert result.returncode != 0
    assert '=PASS' not in result.stdout


def test_probe_propagates_tee_failure(probe_env):
    env, output, image, bindir = probe_env
    tee = bindir / 'tee'; tee.write_text('#!/bin/bash\ncat >/dev/null\nexit 9\n'); tee.chmod(0o755)
    result = run_probe(env, output, image)
    assert result.returncode == 9
    assert '=PASS' not in result.stdout


def test_probe_has_no_stale_json_fallback(probe_env):
    env, output, image, bindir = probe_env
    (output/'smoke.json').write_text(json.dumps(report()))
    (output/'smoke.log').write_text('DOREMI_SMOKE_OK\n')
    (bindir/'docker').write_text('#!/bin/bash\nexit 0\n')
    result = run_probe(env, output, image)
    assert result.returncode != 0 and '=PASS' not in result.stdout
