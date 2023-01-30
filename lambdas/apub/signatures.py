import os
import re
import json
import boto3
import base64
import hashlib
from datetime import datetime
from urllib import request, parse
from urllib.error import HTTPError
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

import config
from apub import http
from apig_http import responses

kms = boto3.client('kms')


def get_public_key():
    response = kms.get_public_key(KeyId=os.environ['KEY_ID'])
    key = serialization.load_der_public_key(response['PublicKey'])
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


def create_signature_header(headers, target, method="post"):
    signed_headers = ['(request-target)']
    to_be_signed = [
        f"(request-target): {method} {target}",
    ]

    for seek in ['Host', 'Date', 'Digest']:
        if seek in headers:
            signed_headers.append(seek.lower())
            to_be_signed.append(f'{seek.lower()}: {headers[seek]}')
            
    to_be_signed = "\n".join(to_be_signed)

    response = kms.sign(
        KeyId=os.environ['KEY_ID'],
        Message=to_be_signed.encode(),
        MessageType='RAW',
        SigningAlgorithm='RSASSA_PKCS1_V1_5_SHA_256'
    )
    signature = base64.b64encode(response['Signature']).decode()

    new_headers = headers.copy()
    new_headers['Signature'] = (
        f'keyId="{config.ACTOR}#main-key",'
        f'headers="{" ".join(signed_headers)}",'
        f'signature="{signature}"'
    )
    return new_headers


def verify_headers(headers, request_target, method="post", digest=None):
    if 'signature' not in headers:
        raise InvalidSignature('missing signature header')

    # parse the header
    sig_parts = {
        k: v.strip('"')
        for k, v in re.findall(r'([a-zA-Z]+)=("[^"]*"|[^",]*)',
                               headers['signature'])
    }

    if 'keyId' not in sig_parts or 'headers' not in sig_parts:
        raise InvalidSignature('missing keyId or headers in signature header')

    # construct the putative message
    message_parts = []
    for signed_header_name in sig_parts['headers'].split():
        if signed_header_name == '(request-target)':
            message_parts.append(
                f'(request-target): {method} {request_target}'
            )
        elif signed_header_name == 'digest' and digest:
            message_parts.append(f'digest: {digest}')
        elif signed_header_name == 'date':
            # verify the date is recent
            try:
                sent_date = datetime.strptime(headers['date'],
                                              '%a, %d %b %Y %H:%M:%S GMT')
                delta = datetime.utcnow() - sent_date
                if delta.total_seconds() > (15 * 60):
                    raise InvalidSignature('message is too old')
                if delta.total_seconds() < -5:
                    raise InvalidSignature('message came from the future')
            except ValueError:
                raise InvalidSignature('unrecognized date format - expecting'
                                       ' "Thu, 01 Jan 1970 00:00:00 GMT"')
            message_parts.append(f'date: {headers[signed_header_name]}')
        else:
            try:
                message_parts.append(
                    f'{signed_header_name}: {headers[signed_header_name]}'
                )
            except KeyError:
                raise InvalidSignature('missing header ' + signed_header_name)
            
    message = "\n".join(message_parts)
    print(repr(message))
    
    # retrieve the public key
    try:
        actor = http.get(sig_parts['keyId'])
        key = serialization.load_pem_public_key(
            actor['publicKey']['publicKeyPem'].encode()
        )
    except HTTPError as ex:
        if ex.code == 410:
            # Gone - we're probably processing a delete
            # it would be nice to verify that, but sadly we can't.
            return parse.urldefrag(sig_parts['keyId']).url
        raise InvalidSignature('failed getting remote pubkey') from ex
    except Exception as ex:
        raise InvalidSignature('failed getting remote pubkey') from ex
    
    # verify
    key.verify(
        base64.b64decode(sig_parts['signature']),
        message.encode(),
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    # return actor
    return parse.urldefrag(sig_parts['keyId']).url

def wrapped_verify_headers(func):
    def _verify(event, context):
        try:
            sha = hashlib.sha256(event.get('body', b''))
            event['actor'] = verify_headers(
                event['headers'],
                event['requestContext']['http']['path'],
                method=event['requestContext']['http']['method'].lower(),
                digest=base64.b64encode(sha.digest()).decode()
            )
        except InvalidSignature as ex:
            traceback.print_exc()
            return responses.HttpResponse('Invalid HTTP signature', 403)

        return func(event, context)
    return _verify
