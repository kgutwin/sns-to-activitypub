import os
import json

import config
import dynamo
import as_http
import signatures


def sns_to_post(record):
    message_id = record['Sns']['MessageId']
    message_timestamp = record['Sns']['Timestamp']
    message_body = f'<p>{record["Sns"]["Message"]}</p>'
    
    return {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f'{config.BASEURL}/create/{message_id}',
        "type": "Create",
        "actor": config.ACTOR,
        "object": {
            "id": f'{config.BASEURL}/{message_id}',
            "type": "Note",
            "published": message_timestamp,
            "attributedTo": config.ACTOR,
            "content": message_body,
        }
    }


TOPICS = {
    os.environ['INFO_TOPIC_ARN']: 'info',
    os.environ['ALERT_TOPIC_ARN']: 'alert',
}


def handler(event, context):
    print(json.dumps(event))
    for record in event['Records']:
        post = sns_to_post(record)
        print(json.dumps(post))

        # deliver the post depending on the source topic
        topic = TOPICS[record['Sns']['TopicArn']]
        if topic == 'info':
            post['object']['to'] = config.ACTOR_FOLLOWERS

        for dest in dynamo.list():
            if topic == 'alert':
                post['object']['to'] = dest['actor_id']
                post['object']['tag'] = [{
                    'type': 'Mention',
                    'name': f'@{dest["username"]}',
                    'href': dest['actor_id']
                }]
            as_http.post(dest['inbox'], post)

