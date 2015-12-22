import os
import re

DEBUG = False
HOST = '0.0.0.0'

BROKER_URL = os.getenv('BROKER_URL')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND')
CELERY_IMPORTS = (
    'tasks.mark_issues',
    'tasks.send_changelog',
)

JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_PASSWORD = os.getenv('JIRA_PASSWORD')
JIRA_ROOT = os.getenv('JIRA_ROOT')

SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK')

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

STAGING_BRANCHES = ('devel', 'development')
PRODUCTION_BRANCHES = ('master', )
ALLOWED_BRANCHES = STAGING_BRANCHES + PRODUCTION_BRANCHES
ALLOWED_EVENTS = ('pull_request', 'release')
ISSUE_PATTERN = re.compile('[A-Za-z]{1,10}-[\d]+', re.I)
