import os
import re
import boto3
import base64
from urllib import request
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

import config
import as_http

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


def verify_headers(headers, request_target, method="post"):
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
        actor = as_http.get(sig_parts['keyId'])
        key = serialization.load_pem_public_key(
            actor['publicKey']['publicKeyPem'].encode()
        )
    except Exception as ex:
        raise InvalidSignature('failed getting remote pubkey') from ex
    
    # verify
    key.verify(
        base64.b64decode(sig_parts['signature']),
        message.encode(),
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    # The code above is somewhat simplified and missing some checks
    # that I would advise implementing in a serious production
    # application. For example:
    # 
    # * The request contains a Date header. Compare it with current
    #   date and time within a reasonable time window to prevent
    #   replay attacks.
    # * It is advisable that requests with payloads in the body also
    #   send a Digest header, and that header be signed along in the
    #   signature. If it’s present, it should be checked as another
    #   special case within the comparison string: Instead of taking
    #   the digest value from the received header, recompute it from
    #   the received body.
    # 
    # from https://blog.joinmastodon.org/2018/07/how-to-make-friends-and-verify-requests/
