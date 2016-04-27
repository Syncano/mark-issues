#!/bin/bash

DATA=$(cat <<EOF
{
  "build_parameters": {
    "BUILD_TYPE": "mark_issues"
  }
}
EOF)

curl \
--header "Accept: application/json" \
--header "Content-Type: application/json" \
--data "$DATA" \
--request POST $DEPLOY_MARK_ISSUES_URL
