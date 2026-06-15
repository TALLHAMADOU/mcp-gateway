import os
import zipfile
import pytest
from fastapi.testclient import TestClient
from src.main import app

KEY = os.environ['MCP_GATEWAY_KEY']
AUTH = {'Authorization': f'Bearer {KEY}'}
client = TestClient(app)


# --- auth on the new office/bureautique routers -----------------------------

def test_office_requires_auth():
    assert client.get('/v1/office/health').status_code == 401
    assert client.get('/v1/google-workspace/health').status_code == 401
    assert client.get('/v1/ms-graph/health').status_code == 401


def test_office_health_ok():
    r = client.get('/v1/office/health', headers=AUTH)
    assert r.status_code == 200
    assert r.json()['handler'] == 'office'


# --- cloud handlers report "not configured" instead of crashing -------------

def test_gworkspace_health_unconfigured():
    r = client.get('/v1/google-workspace/health', headers=AUTH)
    assert r.status_code == 200
    assert r.json()['configured'] is False


def test_gworkspace_call_without_token_is_400():
    r = client.get('/v1/google-workspace/drive/files', headers=AUTH)
    assert r.status_code == 400


def test_ms_graph_call_without_token_is_400():
    r = client.get('/v1/ms-graph/onedrive/root', headers=AUTH)
    assert r.status_code == 400


# --- local generation: no credentials needed, verify real OOXML files -------

def test_create_docx_is_valid_zip():
    pytest.importorskip('docx')
    r = client.post('/v1/office/docx', headers=AUTH, json={
        'filename': 'test_unit', 'elements': [
            {'type': 'heading', 'text': 'Hello', 'level': 1},
            {'type': 'paragraph', 'text': 'world'},
            {'type': 'bullet', 'text': 'item'},
        ]})
    assert r.status_code == 200
    path = r.json()['path']
    assert path.endswith('.docx') and zipfile.is_zipfile(path)


def test_create_xlsx_is_valid_zip():
    pytest.importorskip('openpyxl')
    r = client.post('/v1/office/xlsx', headers=AUTH, json={
        'filename': 'test_unit',
        'sheets': [{'name': 'S1', 'rows': [['a', 'b'], [1, 2]]}]})
    assert r.status_code == 200
    assert zipfile.is_zipfile(r.json()['path'])


def test_create_pptx_is_valid_zip():
    pytest.importorskip('pptx')
    r = client.post('/v1/office/pptx', headers=AUTH, json={
        'filename': 'test_unit',
        'slides': [{'title': 'Slide', 'bullets': ['one', 'two']}]})
    assert r.status_code == 200
    assert zipfile.is_zipfile(r.json()['path'])
