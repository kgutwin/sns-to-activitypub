import os

DOMAIN = os.environ['DOMAIN_NAME']
BASEURL = f'https://{DOMAIN}'

ACCOUNT_ID = 'sns'
ACCOUNT = f'{ACCOUNT_ID}@{DOMAIN}'

ACTOR_PATH = f'/users/{ACCOUNT_ID}'
ACTOR = BASEURL + ACTOR_PATH
ACTOR_INBOX = f'{ACTOR}/inbox'
ACTOR_INBOX_PATH = f'{ACTOR_PATH}/inbox'
ACTOR_FOLLOWERS = f'{ACTOR}/followers'

if 'FOLLOWER_ALLOW_LIST' in os.environ:
    FOLLOWERS = os.environ['FOLLOWER_ALLOW_LIST'].split(',')
