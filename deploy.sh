#!/bin/bash

set -e

pytest
sam build
sam deploy --s3-bucket sam-deployments-941817831 \
    --stack-name sns-to-ap \
    --capabilities CAPABILITY_IAM

