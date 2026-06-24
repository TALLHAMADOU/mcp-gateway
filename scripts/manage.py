#!/usr/bin/env python3
"""Manage helper for MCP Gateway (dev):
- generate api/admin keys and optionally write .env
- add a connector locally to servers.yaml (atomic)

Usage examples:
  # generate keys and write .env
  scripts/manage.py gen-keys --env-file .env

  # add a remote connector locally
  scripts/manage.py add-connector --id my-remote --type remote --url https://example.com/mcp

This script is intended for development convenience. In production, use Vault and the admin API.
"""
import argparse
import secrets
import os
import yaml
import tempfile
import urllib.parse
import socket
import ipaddress

ROOT = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(ROOT, 'servers.yaml')


def gen_key(prefix='sk_', length=32):
    return prefix + secrets.token_urlsafe(length)


def write_env(env_file: str, mcp_key: str, admin_key: str | None = None):
    lines = [f"MCP_GATEWAY_KEY={mcp_key}\n"]
    if admin_key:
        lines.append(f"ADMIN_KEY={admin_key}\n")
    with open(env_file, 'w') as f:
        f.writelines(lines)
    print(f"Wrote env to {env_file}")


def _is_upstream_allowed(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        infos = socket.getaddrinfo(host, None)
        for fam, _, _, _, sockaddr in infos:
            ip = sockaddr[0]
            addr = ipaddress.ip_address(ip)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_unspecified:
                return False
        return True
    except Exception:
        return False


def add_connector_local(connector: dict):
    # validation
    if 'id' not in connector:
        raise SystemExit('connector must include id')
    if connector.get('type') == 'remote' and 'url' in connector:
        if not str(connector['url']).startswith('https://'):
            raise SystemExit('remote connector url must start with https://')
        if not _is_upstream_allowed(connector['url']):
            raise SystemExit('remote connector url resolves to a private/forbidden address')
    # read config
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            cfg = yaml.safe_load(f) or {}
    connectors = cfg.setdefault('connectors', [])
    if any(c.get('id') == connector['id'] for c in connectors):
        raise SystemExit('connector with given id already exists')
    connectors.append(connector)
    # atomic write
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(CONFIG_PATH) or '.')
    try:
        with os.fdopen(tmp_fd, 'w') as tmp:
            yaml.safe_dump(cfg, tmp)
        os.replace(tmp_path, CONFIG_PATH)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
    print(f"Added connector {connector['id']} to {CONFIG_PATH}")


def main():
    p = argparse.ArgumentParser(prog='manage.py')
    sub = p.add_subparsers(dest='cmd')

    g = sub.add_parser('gen-keys')
    g.add_argument('--env-file', default=None, help='Write keys to this .env file')
    g.add_argument('--admin', action='store_true', help='Also generate ADMIN_KEY')

    a = sub.add_parser('add-connector')
    a.add_argument('--id', required=True)
    a.add_argument('--type', required=True, choices=['remote', 'builtin', 'local'])
    a.add_argument('--url', help='remote connector URL (for type=remote)')
    a.add_argument('--handler', help='handler name (for builtin)')
    a.add_argument('--meta', help='extra yaml metadata (key1=val1,key2=val2)')
    a.add_argument('--skip-ssrf', action='store_true', help='Skip SSRF / private-host validation (dev only)')

    args = p.parse_args()

    if args.cmd == 'gen-keys':
        m = gen_key()
        akey = gen_key('sk_admin_') if args.admin else None
        if args.env_file:
            write_env(args.env_file, m, akey)
        else:
            print('MCP_GATEWAY_KEY=' + m)
            if akey:
                print('ADMIN_KEY=' + akey)
        return

    if args.cmd == 'add-connector':
        connector = {'id': args.id, 'type': args.type}
        if args.url:
            connector['url'] = args.url
        skip_ssrf = getattr(args, 'skip_ssrf', False)
        if args.handler:
            connector['handler'] = args.handler
        if args.meta:
            meta = {}
            for kv in args.meta.split(','):
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    meta[k.strip()] = v.strip()
            connector.update(meta)
        if skip_ssrf:
            # bypass SSRF checks (development convenience)
            def _add_no_check(conn):
                cfg = {}
                if os.path.exists(CONFIG_PATH):
                    with open(CONFIG_PATH, 'r') as f:
                        cfg = yaml.safe_load(f) or {}
                cfg.setdefault('connectors', []).append(conn)
                tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(CONFIG_PATH) or '.')
                try:
                    with os.fdopen(tmp_fd, 'w') as tmp:
                        yaml.safe_dump(cfg, tmp)
                    os.replace(tmp_path, CONFIG_PATH)
                finally:
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass
                print(f"Added connector {conn['id']} to {CONFIG_PATH} (ssrf check skipped)")
            _add_no_check(connector)
        else:
            add_connector_local(connector)
        return
        return

    p.print_help()


if __name__ == '__main__':
    main()
