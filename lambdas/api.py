import os
import json
import boto3
import base64
import traceback

import config
import apub.utils
import apub.signatures

from apig_http import router
from apig_http.responses import HttpResponse

sqs = boto3.client('sqs')


@router.register('/.well-known/webfinger')
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


@router.register(config.ACTOR_PATH)
def actor_doc(event, context):
    pub_key = apub.signatures.get_public_key()
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
    

@router.register(config.ACTOR_INBOX_PATH, 'POST')
@apub.signatures.wrapped_verify_headers
def actor_inbox(event, context):
    # double-check that the event's actor is the same as the one
    # sending the message
    body = json.loads(event['body'])
    if apub.utils.trim_frag(body.get('id', '')) != event['actor']:
        print(apub.utils.trim_frag(body.get('id', '')), event['actor'])
        return HttpResponse('Mismatched key', 403)
    
    # send it on to the incoming handler for processing
    sqs.send_message(
        QueueUrl=os.environ['INCOMING_QUEUE'],
        MessageBody=event['body']
    )

    return HttpResponse('', 204)


def handler(event, context):
    print(json.dumps(event))

    response = router.handle(event, context)
    print(json.dumps(response.to_http()))
    return response.to_http()
