import json
import traceback
from urllib.error import HTTPError

import config
import dynamo
import apub.http


def handle_one(record):
    print('---------', record['messageId'])
    print(json.dumps(record))
    body = json.loads(record['body'])

    assert body['@context'] == 'https://www.w3.org/ns/activitystreams'

    if body['type'] == 'Follow':
        assert body['object'] == config.ACTOR

        # retrieve the follower's actor data
        actor = apub.http.get(body['actor'])
        username = actor.get('preferredUsername', actor['id'].split('/')[-1])
        domain = actor['id'].split('/')[2]
        joined_name = f'{username}@{domain}'
        
        result = 'Reject'
        if joined_name in config.FOLLOWERS:
            result = 'Accept'

        print('Incoming follow request from', joined_name, ':', result)

        # record the follower's info in dynamo
        if result == 'Accept':
            dynamo.put({
                'id': body['id'],
                'actor_id': actor['id'],
                'inbox': actor['inbox'],
                'username': actor.get('preferredUsername',
                                      actor['id'].split('/')[-1])
            })
        
        # respond back to the actor's inbox
        apub.http.post(actor['inbox'], {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f'{config.BASEURL}/{record["messageId"]}',
            "type": result,
            "actor": config.ACTOR,
            "object": body["id"],
        })

    elif body['type'] == 'Undo' and body['object']['type'] == 'Follow':
        # Handle Unfollow request
        assert body['object']['object'] == config.ACTOR

        dynamo.delete(body['object']['id'])
    

def handler(event, context):
    r = {'batchItemFailures': []}
    for record in event['Records']:
        try:
            handle_one(record)
        except Exception as ex:
            traceback.print_exc()
            if isinstance(ex, HTTPError):
                print(ex.headers)
                print(ex.read())
            if int(record['attributes']['ApproximateReceiveCount']) < 3:
                r['batchItemFailures'].append({
                    'itemIdentifier': record['messageId']
                })
    return r
