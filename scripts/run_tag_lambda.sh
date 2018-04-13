#!/bin/bash
set -euo pipefail

STACK_NAME="${STACK_NAME}"
DRAIN_TAG="${DRAIN_TAG}"

echo "Setting 'drain' tag on $STACK_NAME to $DRAIN_TAG"

result=$(aws lambda invoke \
  --function-name "tag-ecs-lambda" \
  --log-type "Tail" \
  --payload "{\"StackName\": \"$STACK_NAME\", \"Drain\": \"$DRAIN_TAG\"}" \
  outfile)

echo "$result" | jq '.LogResult' --raw-output | base64 --decode

status_code=$(echo "$result" | jq '.StatusCode' --raw-output )
[[ "$status_code" != "200" ]] && echo "FAILED" && exit 1
echo "Success."
