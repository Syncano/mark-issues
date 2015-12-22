import os
import re
import importlib
import requests

from celery.utils.log import get_task_logger

from worker import celery

logger = get_task_logger(__name__)
SETTINGS = importlib.import_module(os.getenv('MARK_ISSUES_SETTINGS'))
ISSUE_PATTERN = re.compile('[A-Za-z]{1,10}-[\d]+', re.I)
JQL = '("Deployed to" != {} OR "Deployed to" = EMPTY) AND issuekey in ({})'


class MarkIssuesTask(celery.Task):
    name = 'MarkIssues'
    max_retries = 4
    default_retry_delay = 60 * 15

    def run(self, repository, number):
        self.repository = repository
        self.number = number
        self.deployed_to = None
        self.gh_base_url = 'https://api.github.com/repos/syncano/{}/pulls/{}'.format(self.repository, self.number)
        self.jira_base_url = '{}/rest/api/2'.format(SETTINGS.JIRA_ROOT)
        self.jira_auth = (SETTINGS.JIRA_USERNAME, SETTINGS.JIRA_PASSWORD)

        logger.info('Fetching pull request from github...')
        pull_request = self.get_github_pull_request()
        branch = pull_request['base']['ref']

        if pull_request['state'] != 'closed':
            logger.info('Unsupported state of pull request "{state}"'.format(**pull_request))
            return

        if not pull_request['merged']:
            logger.info('Pull request needs to be merged')
            return

        if branch in SETTINGS.PRODUCTION_BRANCHES:
            self.deployed_to = 'Production'
        elif branch in SETTINGS.STAGING_BRANCHES:
            self.deployed_to = 'Staging'

        if not self.deployed_to:
            logger.info('Unsupported "{}" branch'.format(branch))
            return

        logger.info('Fetching issues from github...')
        issues = self.get_github_issues(pull_request['title'], pull_request['body'])

        logger.info('{} issues found'.format(len(issues)))

        if issues:
            issues_to_update = self.get_jira_issues(issues)
            logger.info('{} issues needs to be updated'.format(len(issues_to_update)))

            for issue in issues_to_update:
                logger.info('Updating issue {key}'.format(**issue))
                self.update_jira_issue(issue)

        return 'Done, bay!'

    def get_github_pull_request(self):
        response = requests.get(self.gh_base_url, params={'access_token': SETTINGS.GITHUB_TOKEN})
        response.raise_for_status()
        return response.json()

    def get_github_issues(self, *extra):
        issues = []
        next_url = '{}/commits?access_token={}'.format(self.gh_base_url, SETTINGS.GITHUB_TOKEN)

        while next_url is not None:
            response = requests.get(next_url)
            response.raise_for_status()
            next_url = response.links.get('next', {}).get('url', None)

            for commit in response.json():
                message = re.sub('FRONT-|SYNGUI-', 'DASH-', commit['commit']['message'])
                issues.extend(ISSUE_PATTERN.findall(message))

        for text in extra:
            message = re.sub('FRONT-|SYNGUI-', 'DASH-', text)
            issues.extend(ISSUE_PATTERN.findall(text))

        return list(set(issues))

    def get_jira_issues(self, issues):
        jira_issues = []
        total = len(issues)
        per_chunk = 50
        url = '{}/search/'.format(self.jira_base_url)

        for index in range(0, total, per_chunk):
            chunk = issues[index:min(index + per_chunk, total)]
            issue_keys = ','.join(chunk)
            query = JQL.format(self.deployed_to, issue_keys)
            params = {
                'jql': query,
                'fields': 'key,customfield_10200',
                'maxResults': len(chunk)
            }
            response = requests.get(url, params=params, auth=self.jira_auth)
            response.raise_for_status()

            for issue in response.json().get('issues', []):
                customfield_10200 = issue['fields'].get('customfield_10200') or []
                customfield_10200.append({'value': self.deployed_to})

                jira_issues.append({
                    'key': issue['key'],
                    'customfield_10200': customfield_10200
                })

        return jira_issues

    def update_jira_issue(self, issue):
        url = '{}/issue/{}'.format(self.jira_base_url, issue['key'])
        json = {'fields': {'customfield_10200': issue['customfield_10200']}}
        response = requests.put(url, json=json, auth=self.jira_auth)
        response.raise_for_status()
