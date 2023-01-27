import os
import uuid
import base64
import pytest
import hashlib
from unittest import mock
from datetime import datetime
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

import config
from apub import signatures


class MockKmsBotoClient:
    def __init__(self):
        self.key_id = str(uuid.uuid4())
        self.private_key = rsa.generate_private_key(65537, 2048)

    @property
    def pubkey_pem(self):
        return self.private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
    def get_public_key(self, KeyId=None):
        assert KeyId == self.key_id
        public_bytes = self.private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.PKCS1
        )
        return {
            'PublicKey': public_bytes
        }

    def sign(self, KeyId=None, Message=None, MessageType=None,
             SigningAlgorithm=None):
        assert KeyId == self.key_id
        assert isinstance(Message, bytes)
        assert MessageType == 'RAW'
        assert SigningAlgorithm == 'RSASSA_PKCS1_V1_5_SHA_256'
        
        return {
            'Signature': self.private_key.sign(
                Message,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        }


@pytest.fixture(scope='module')
def mock_kms():
    mkbc = MockKmsBotoClient()
    patches = [
        mock.patch('apub.signatures.kms', mkbc),
        mock.patch.dict(os.environ, {'KEY_ID': mkbc.key_id}),
        mock.patch('config.ACTOR', "https://sns-to-ap.local/users/test"),
    ]
    for p in patches:
        p.start()

    yield mkbc

    for p in patches:
        p.stop()


def test_get_public_key(mock_kms):
    response = signatures.get_public_key()
    assert response.startswith('-----BEGIN PUBLIC KEY-----\nMIIBI')


def test_create_signature_header(mock_kms):
    sha = hashlib.sha256(b'hello world')
    headers = {
        'Host': 'mastodon.local',
        'Date': 'Wed, 04 Oct 2023 21:41:53 GMT',
        'Digest': f'SHA-256={base64.b64encode(sha.digest()).decode()}'
    }
    expected_msg = f"""(request-target): post /test
host: mastodon.local
date: Wed, 04 Oct 2023 21:41:53 GMT
digest: SHA-256={base64.b64encode(sha.digest()).decode()}"""

    expected_sig = base64.b64encode(
        mock_kms.sign(
            KeyId=mock_kms.key_id,
            Message=expected_msg.encode(),
            MessageType='RAW',
            SigningAlgorithm='RSASSA_PKCS1_V1_5_SHA_256'
        )['Signature']
    ).decode()
    new_headers = signatures.create_signature_header(headers, '/test')
    sig = new_headers['Signature']
    assert 'keyId="https://sns-to-ap.local/users/test#main-key"' in sig
    assert 'headers="(request-target) host date digest"' in sig
    assert f'signature="{expected_sig}"' in sig
    

def test_verify_headers(mock_kms):
    # first make sure that we raise appropriate exceptions for bad inputs
    # missing signature header
    with pytest.raises(signatures.InvalidSignature):
        signatures.verify_headers({}, '/test')

    # missing keyId or headers in signature header
    with pytest.raises(signatures.InvalidSignature):
        signatures.verify_headers({
            'signature': 'foo=bar'
        }, '/test')

    # missing header digest
    with pytest.raises(signatures.InvalidSignature):
        signatures.verify_headers({
            'signature': 'headers="(request-target) digest"'
        }, '/test')
    
    # mock the apub.http.get method to return the pubkey from mock KMS
    def mock_actor(dummy):
        return {'publicKey': {'publicKeyPem': mock_kms.pubkey_pem}}
    with mock.patch('apub.http.get', mock_actor):
        now_str = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        message = f"""(request-target): post /test
host: sns-to-ap.local
date: {now_str}
digest: aGVsbG8=""".encode()
        sig = mock_kms.sign(
            KeyId=mock_kms.key_id,
            Message=message,
            MessageType='RAW',
            SigningAlgorithm='RSASSA_PKCS1_V1_5_SHA_256'
        )['Signature']
        headers = {
            'signature': (
                f'keyId="https://sns-to-ap.local/users/test#main-key",'
                f'headers="(request-target) host date digest",'
                f'signature="{base64.b64encode(sig).decode()}"'
            ),
            'host': 'sns-to-ap.local',
            'digest': 'aGVsbG8=',
            'date': now_str,
        }
        actor = signatures.verify_headers(headers, '/test')
        assert actor == 'https://sns-to-ap.local/users/test'


def test_wrapped_verify_headers():
    mock_verify_headers = mock.Mock()
    mock_verify_headers.return_value = 'https://mastodon.local/users/mock'

    with mock.patch('apub.signatures.verify_headers', mock_verify_headers):
        @signatures.wrapped_verify_headers
        def inner(event, context):
            return 'all good'

        ev = {
            'body': b'test body',
            'headers': {'foo': 'bar'},
            'requestContext': {'http': {'path': '/test', 'method': 'POST'}}
        }
        
        inner(ev, None)

        mock_verify_headers.assert_called_with(
            {'foo': 'bar'},
            '/test',
            method='post',
            digest='Y++zFe1xzH5aH8ICQ0uzrsIJHng4cH4UigF/rrt0ZP4='
        )

        assert ev['actor'] == 'https://mastodon.local/users/mock'
