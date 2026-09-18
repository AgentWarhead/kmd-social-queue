# -*- coding: utf-8 -*-
"""Graph API calls from this laptop, for the scheduling and read-back tools.

The system user token lives only in the Windows user environment as META_GRAPH_TOKEN. It is read from
the registry so a shell opened before it was set still finds it, and it is never printed or logged.
"""
import json
import urllib.parse
import urllib.request

API = 'https://graph.facebook.com/v21.0'


def token():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
            return winreg.QueryValueEx(k, 'META_GRAPH_TOKEN')[0]
    except Exception:
        import os
        t = os.environ.get('META_GRAPH_TOKEN')
        if not t:
            raise SystemExit('META_GRAPH_TOKEN is not set')
        return t


def _read(req):
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode('utf-8') or '{}')
        raise RuntimeError((body.get('error') or {}).get('message', str(e)))


def get(path, tok=None, **params):
    params['access_token'] = tok or token()
    return _read(urllib.request.Request('%s/%s?%s' % (API, path, urllib.parse.urlencode(params))))


def post(path, tok, **params):
    params['access_token'] = tok
    return _read(urllib.request.Request('%s/%s' % (API, path), data=urllib.parse.urlencode(params).encode(), method='POST'))


def post_file(path, tok, field, filename, data, **params):
    params['access_token'] = tok
    b = '----kmdq' + str(abs(hash(filename)))
    body = b''.join(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (b, k, v)).encode() for k, v in params.items())
    body += ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: image/jpeg\r\n\r\n' % (b, field, filename)).encode()
    body += data + ('\r\n--%s--\r\n' % b).encode()
    return _read(urllib.request.Request('%s/%s' % (API, path), data=body, method='POST',
                                        headers={'Content-Type': 'multipart/form-data; boundary=%s' % b}))


def page_token(page_id):
    for p in get('me/accounts', fields='id,access_token', limit=100).get('data', []):
        if p['id'] == page_id:
            return p['access_token']
    raise SystemExit('page %s is not reachable with this token' % page_id)
