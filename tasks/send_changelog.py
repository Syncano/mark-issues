import requests
from celery.utils.log import get_task_logger

from worker import celery

from .mixins import GitHubMixin, JiraMixin, SettingsMixin

logger = get_task_logger(__name__)


class SendChangelogTask(SettingsMixin, GitHubMixin, JiraMixin, celery.Task):
    name = 'SendChangelog'
    max_retries = 4
    default_retry_delay = 60 * 15

    def run(self, repository, number):
        self.repository = repository
        self.number = number
        self.deployed_to = None
        self.gh_base_url = 'https://api.github.com/repos/syncano/{}/pulls/{}'.format(self.repository, self.number)
        self.jira_base_url = '{}/rest/api/2'.format(self.SETTINGS.JIRA_ROOT)
        self.jira_auth = (self.SETTINGS.JIRA_USERNAME, self.SETTINGS.JIRA_PASSWORD)

        pull_request = self.get_pull_request()
        branch = pull_request['base']['ref']

        if pull_request['state'] != 'closed':
            logger.info('Unsupported state of pull request "{state}"'.format(**pull_request))
            return

        if not pull_request['merged']:
            logger.info('Pull request needs to be merged')
            return

        if branch not in self.SETTINGS.PRODUCTION_BRANCHES:
            logger.info('Invalid production branch "{}"'.format(branch))
            return

        logger.info('Fetching issues from github...')
        issues = self.get_pull_request_issues(pull_request['title'], pull_request['body'])

        logger.info('{} issues found'.format(len(issues)))

        if issues:
            issues_for_changelog = self.get_jira_issues(issues)
            self.send_changelog(pull_request, issues_for_changelog)

        return 'Done, bye!'

    def send_changelog(self, pull_request, issues):
        colors = {
            'Task': '#3B7FC4',
            'Bug': '#D04437',
            'Story': '#67AB49',
            'Epic': '#654982',
        }

        json = {
            'username': 'Changelog',
            'channel': self.SETTINGS.SLACK_CHANGELOG_CHANNEL,
            'attachments': [{
                'color': '#C3C3C3',
                'title': 'There was a new release',
                'fields': [
                    {
                        'title': 'Project',
                        'value': self.repository,
                        'short': True
                    },
                    {
                        'title': 'Pull request',
                        'value': pull_request['title'],
                        'short': True
                    },
                    {
                        'title': 'Release done by',
                        'value': pull_request['merged_by']['login'],
                        'short': True
                    }
                ]
            }]
        }

        attachments = {}
        for issue in issues:
            fields = issue['fields']
            issue_type = fields['issuetype']['name']
            attachments[issue_type] = attachments.get(issue_type, {'fallback': [], 'text': [], 'color': None})
            attachment = attachments[issue_type]

            key = issue['key']
            epic_key = fields.get('customfield_10007', '')

            format_kwargs = {
                'key': key,
                'url': '{}/browse/{}'.format(self.SETTINGS.JIRA_ROOT, key),
                'epic_key': epic_key,
                'epic_url': '{}/browse/{}'.format(self.SETTINGS.JIRA_ROOT, epic_key),
                'summary': fields['summary'],
            }

            attachment['fallback'].append('[{key}] {summary}: {url} Epic: [{epic_key}]'.format(**format_kwargs))
            attachment['text'].append('<{url}|[{key}]> {summary} Epic <{epic_url}|[{epic_key}]>'.format(**format_kwargs))

        for _type, content in attachments.iteritems():
            json['attachments'].append({
                'color': colors.get(_type, '#C3C3C3'),
                'text': '\n'.join(content['text']),
                'fallback': '\n'.join(content['fallback']),
                'fields': [
                    {
                        'title': 'Issue type',
                        'value': _type,
                        'short': True
                    },
                    {
                        'title': 'Total',
                        'value': len(content['text']),
                        'short': True
                    }
                ]
            })

        response = requests.post(self.SETTINGS.SLACK_WEBHOOK, json=json)
        response.raise_for_status()
