import os
import re
import json
import markdown

import config
import dynamo
import apub.http
import apub.signatures


def cloudwatch_to_body(message):
    """Turn a CloudWatch Alarm message into a legible body.
    """
    try:
        msgd = json.loads(message)
    except json.decoder.JSONDecodeError:
        return f'<p>{message}</p>'
    return f'''<p>CloudWatch Alarm: {msgd['AlarmName']} <br>
Account: {msgd['AWSAccountId']} in {msgd['Region']} <br>
At: {msgd['StateChangeTime']} <br>
In State: {msgd['NewStateValue']} from {msgd['OldStateValue']} <br>
Reason: {msgd['NewStateReason']}</p>'''


def sns_to_post(record):
    message_id = record['Sns']['MessageId']
    message_timestamp = record['Sns']['Timestamp']

    message = record['Sns']['Message']
    if message.startswith('{') and 'arn:aws:cloudwatch' in message:
        message_body = cloudwatch_to_body(message)
    else:
        # let's linkify things properly
        message_md = re.sub(r'(https?://\S+)', r'[\1](\1)', message)
        message_body = markdown.markdown(message_md)
    
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
            apub.http.post(dest['inbox'], post)

