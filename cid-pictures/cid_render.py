#!/usr/bin/env python3
"""Open a synthetic message with a cid: picture through a locally built backend.

The backend is the tree's own target/debug/omamail, run as `omamail call` with
HOME/XDG in a throwaway directory. The message reaches it through the cache
(cache.resourcePut), so no mail provider and no network are involved.
usage: cid_render.py <tree> <out.json>
"""
import base64, json, os, pathlib, subprocess, sys, tempfile
tree = pathlib.Path(sys.argv[1]).resolve(); out = pathlib.Path(sys.argv[2])
binary = tree / 'target/debug/omamail'
png = base64.b64encode((pathlib.Path(__file__).parent / 'assets/screenshot.png').read_bytes()).decode()
lines = [png[i:i + 76] for i in range(0, len(png), 76)]
raw = ('From: Ada Lovelace <ada@example.org>\r\nTo: Me <me@example.com>\r\nSubject: Q3 dashboard\r\n'
       'MIME-Version: 1.0\r\nContent-Type: multipart/related; boundary=rel\r\n\r\n'
       '--rel\r\nContent-Type: text/html; charset=utf-8\r\n\r\n'
       '<p>Hi,</p><p>Here is the dashboard from this morning:</p>'
       '<p><img src="cid:image001.png@01DB0000.ABCDEF00" alt="dashboard screenshot" width="420" height="180"></p>'
       '<p>Numbers are up again.</p><p>Ada</p>\r\n'
       '--rel\r\nContent-Type: image/png; name="image001.png"\r\nContent-ID: <image001.png@01DB0000.ABCDEF00>\r\n'
       'Content-Disposition: inline; filename="image001.png"\r\nContent-Transfer-Encoding: base64\r\n\r\n'
       + '\r\n'.join(lines) + '\r\n--rel--\r\n')
account = 'synthetic@example.org'
with tempfile.TemporaryDirectory(prefix='omamail-cid-') as d:
    d = pathlib.Path(d); os.chmod(d, 0o700)
    cfg = d / 'config/omamail'; cfg.mkdir(parents=True); os.chmod(d / 'config', 0o700); os.chmod(cfg, 0o700)
    (cfg / 'accounts.json').write_text(json.dumps({'version': 1, 'activeId': account, 'accounts': [{'email': account}]}))
    os.chmod(cfg / 'accounts.json', 0o600)
    env = {'HOME': str(d), 'XDG_CONFIG_HOME': str(d / 'config'), 'XDG_CACHE_HOME': str(d / 'cache'),
           'XDG_DATA_HOME': str(d / 'data'), 'XDG_STATE_HOME': str(d / 'state'), 'PATH': '/usr/bin'}
    def call(method, params):
        r = subprocess.run([str(binary), 'call', method, '--json'], input=json.dumps(params), capture_output=True, text=True, env=env)
        envelope = json.loads(r.stdout)
        assert envelope.get('ok'), (method, envelope, r.stderr)
        return envelope['result']
    payload = call('message.parse', {'raw': base64.urlsafe_b64encode(raw.encode()).decode().rstrip('=')})
    call('cache.resourcePut', {'accountId': account, 'id': '1:INBOX', 'resource': {'id': '1:INBOX', 'payload': payload}})
    opened = call('reader.open', {'accountId': account, 'id': '1:INBOX', 'requestId': 'evidence', 'now': 0, 'cacheOnly': True,
                                  'options': {'allowRemoteImages': False, 'withReader': True, 'withPlainText': True}})
    version = subprocess.run([str(binary), '--version'], capture_output=True, text=True, env=env).stdout.strip()
out.write_text(json.dumps({'backend': version, 'nativeRender': opened['nativeRender']}))
doc = json.dumps(opened['nativeRender']['document'])
print(version, '| cid: in document:', 'cid:' in doc, '| data:image/png in document:', 'data:image/png' in doc)
