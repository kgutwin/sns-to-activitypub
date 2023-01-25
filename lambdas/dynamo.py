import os
import boto3

dyn = boto3.client('dynamodb')


def put(item):
    formatted_item = {
        k: {'S': v} for k, v in item.items()
    }
    return dyn.put_item(
        TableName=os.environ['TABLE_NAME'],
        Item=formatted_item
    )


def list():
    response = dyn.scan(TableName=os.environ['TABLE_NAME'])
    for item in response['Items']:
        yield {
            k: v['S'] for k, v in item.items()
        }


def delete(id):
    dyn.delete_item(
        TableName=os.environ['TABLE_NAME'],
        Key={'id': {'S': id}}
    )
