# Amazon SNS to ActivityPub Bridge

This small serverless application is intended to make notifications
from your AWS environment to your Fediverse feed simple! All you need
is an existing Route 53 Hosted Zone which is capable of successfully
passing an ACM DNS-based authorization check.

## Notification concept

The template offers two SNS topics for different urgency levels of
messages.

* The **Info** topic will post messages to followers' timelines
  without sending them any notifications. This is most appropriate for
  ambient-style alerting, those messages not typically requiring any
  immediate action.
* The **Alert** topic will send Direct Messages to followers,
  typically triggering a client notification. This is most appropriate
  for alarms or other messages requiring immediate attention.

## Quickstart

You must have the AWS SAM CLI installed. It's easiest to use the
guided mode of SAM Deploy to complete the configuration.

```
sam deploy --guided
```

For the template parameters:

* **DomainName**: Provide a fully qualified domain name that resides
  under your existing Route 53 hosted zone.
* **HostedZoneId**: The zone ID of your Route 53 hosted zone.
* **FollowerAllowList**: Specify one or more comma-separated fully
  qualified Fediverse usernames of the form `username@domain.tld`.
  Only users listed in this list will be allowed to follow the bot.
* **InfoTopicARN** and **AlertTopicARN**: If you have existing SNS
  topics for your info and alert messages, provide their ARNs here.
  Otherwise, the template will create new topics for you.
  
Once the template has deployed, open your favorite Mastodon client and
search for the user "sns@_DomainName_" where _DomainName_ is the name
provided in the template parameters. You should spot the user and be
able to follow it, if you are one of the users in the
**FollowerAllowList**.

Finally, post a message to one of the SNS topics and watch it be
delivered to you within a few seconds!

## TODO

* The HTTP Signature checks are currently skeletal; digest, time, and
  source checks are nonexistent. This is not a critical issue but
  could cause bad actors to potentially forge messages.
  
* The bot user's profile is very incomplete. An icon would be nice,
  and maybe also a more descriptive name.
  
* Add unit tests, as many as possible.

