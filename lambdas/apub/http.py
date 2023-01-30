import json
import time
import base64
import hashlib
from datetime import datetime
from urllib import request, parse
from urllib.error import HTTPError

from apub import signatures, utils


def get(url):
    url = utils.trim_frag(url)
    req = request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'sns-to-activitypub/1',
    })
    try:
        response = request.urlopen(req)
        return json.load(response)
    except HTTPError as ex:
        print(ex.headers)
        print(ex.read())
        raise


GET_CACHE = {}

def get_cached(url, max_age=60.0):
    """Get, but with extra cache flavor"""
    url = utils.trim_frag(url)
    if url in GET_CACHE:
        if time.time() < GET_CACHE[url]['requested'] + max_age:
            return GET_CACHE[url]['json']

    response = get(url)
    GET_CACHE[url] = {
        'json': response,
        'requested': time.time()
    }
    return response


def post(url, body):
    print('POST to', url)
    print(json.dumps(body))

    parsed_url = parse.urlparse(url)
    data = json.dumps(body).encode()
    sha = hashlib.sha256(data)
    
    headers = {
        'User-Agent': 'sns-to-activitypub/1',
        'Accept': 'application/json',
        'Content-Type': 'application/activity+json',
        'Digest': f'SHA-256={base64.b64encode(sha.digest()).decode()}',
        'Date': datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT'),
        'Host': parsed_url.hostname,
    }
    headers = signatures.create_signature_header(headers, parsed_url.path)
    print(headers)

    req = request.Request(url, data=data, headers=headers)
    response = request.urlopen(req)
    print(response.status, response.reason)
    if response.status == 200:
        r = json.load(response)
        print('Response:')
        print(json.dumps(r))
        return r
    else:
        return {}
