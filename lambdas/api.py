import os
import json
import boto3
import base64
import traceback

import config
import as_http
import signatures

sqs = boto3.client('sqs')


class HttpResponse:
    def __init__(self, body='', status_code=200):
        self.headers = {}
        self.status_code = status_code
        
        if isinstance(body, dict):
            self.body = json.dumps(body)
            self.headers['Content-Type'] = 'application/jrd+json'
        else:
            self.body = body
        
    def to_http(self):
        return {
            'statusCode': self.status_code,
            'statusDescription': {
                200: 'OK',
                204: 'No Content',
                401: 'Unauthorized',
                404: 'Not Found',
                500: 'Server error',
            }.get(self.status_code, 'Unsure'),
            'body': self.body,
            'headers': self.headers,
        }

    
def webfinger(event, context):
    qsp = event['queryStringParameters']
    if qsp.get('resource') == f'acct:{config.ACCOUNT}':
        return HttpResponse({
            'subject': 'acct:' + config.ACCOUNT,
            'links': [{
                'rel': 'self',
                'type': 'application/activity+json',
                'href': config.ACTOR
            }]
        })
    
    return HttpResponse('Not Found', 404)


def actor_doc(event, context):
    pub_key = signatures.get_public_key()
    return HttpResponse({
        "@context": [
            "https://www.w3.org/ns/activitystreams",
            "https://w3id.org/security/v1",
        ],
        "id": config.ACTOR,
        "type": "Service",
        "followers": config.ACTOR_FOLLOWERS,
        "preferredUsername": config.ACCOUNT_ID,
        "inbox": config.ACTOR_INBOX,
        "manuallyApprovesFollowers": True,
        "discoverable": False,
        "publicKey": {
            "id": f'{config.ACTOR}#main-key',
            "owner": config.ACTOR,
            "publicKeyPem": pub_key,
        }
    })
    

def actor_inbox(event, context):
    try:
        signatures.verify_headers(event['headers'], config.ACTOR_INBOX_PATH)
    except signatures.InvalidSignature as ex:
        traceback.print_exc()
        return HttpResponse('', 401)

    # send it on to the incoming handler for processing
    sqs.send_message(
        QueueUrl=os.environ['INCOMING_QUEUE'],
        MessageBody=event['body']
    )

    return HttpResponse('', 204)


ROUTES = {
    '/.well-known/webfinger': {'GET': webfinger},
    config.ACTOR_PATH: {'GET': actor_doc},
    config.ACTOR_INBOX_PATH: {'POST': actor_inbox},
}


def handler(event, context):
    print(json.dumps(event))
    path = event['requestContext']['http']['path']
    method = event['requestContext']['http']['method']
    print(f'{method} {path}')
    
    try:
        if path in ROUTES:
            if method in ROUTES[path]:
                response = ROUTES[path][method](event, context)
        else:
            response = HttpResponse('Not Found', 404)
            
    except Exception as ex:
        traceback.print_exc()
        response = HttpResponse('Server error', 500)

    print(json.dumps(response.to_http()))
    return response.to_http()
