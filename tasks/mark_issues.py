import requests
from celery.utils.log import get_task_logger

from worker import celery

from .mixins import GitHubMixin, JiraMixin, SettingsMixin

logger = get_task_logger(__name__)


class MarkIssuesTask(SettingsMixin, JiraMixin, GitHubMixin, celery.Task):
    name = 'MarkIssues'
    max_retries = 4
    default_retry_delay = 60 * 15

    def run(self, repository, number):
        self.repository = repository
        self.number = number
        self.deployed_to = None
        self.gh_base_url = 'https://api.github.com/repos/syncano/{}/pulls/{}'.format(self.repository, self.number)
        self.jira_base_url = '{}/rest/api/2'.format(self.SETTINGS.JIRA_ROOT)
        self.jira_auth = (self.SETTINGS.JIRA_USERNAME, self.SETTINGS.JIRA_PASSWORD)

        logger.info('Fetching pull request from github...')
        pull_request = self.get_pull_request()
        branch = pull_request['base']['ref']

        if pull_request['state'] != 'closed':
            logger.info('Unsupported state of pull request "{state}"'.format(**pull_request))
            return

        if not pull_request['merged']:
            logger.info('Pull request needs to be merged')
            return

        if branch in self.SETTINGS.PRODUCTION_BRANCHES:
            self.deployed_to = 'Production'
        elif branch in self.SETTINGS.STAGING_BRANCHES:
            self.deployed_to = 'Staging'

        if not self.deployed_to:
            logger.info('Unsupported "{}" branch'.format(branch))
            return

        logger.info('Fetching issues from github...')
        issues = self.get_pull_request_issues(pull_request['title'], pull_request['body'])

        logger.info('{} issues found'.format(len(issues)))

        if issues:
            issues_to_update = self.get_jira_issues(issues, ['key', 'customfield_10200'])
            logger.info('{} issues needs to be updated'.format(len(issues_to_update)))

            for issue in issues_to_update:
                logger.info('Updating issue {key}'.format(**issue))
                self.update_jira_issue(issue)

        return 'Done, bay!'

    def get_jira_jql(self, issues):
        issues = ','.join(issues)
        return '("Deployed to" != {} OR "Deployed to" = EMPTY) AND issuekey in ({})'.format(self.deployed_to, issues)

    def get_jira_issues(self, *args, **kwargs):
        issues = super(MarkIssuesTask, self).get_jira_issues(*args, **kwargs)
        jira_issues = []

        for issue in issues:
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
