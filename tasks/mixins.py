import importlib
import os
import re

import requests


class SettingsMixin(object):
    SETTINGS = importlib.import_module(os.getenv('MARK_ISSUES_SETTINGS'))


class GitHubMixin(object):

    def get_pull_request(self):
        response = requests.get(self.gh_base_url, params={'access_token': self.SETTINGS.GITHUB_TOKEN})
        response.raise_for_status()
        return response.json()

    def get_pull_request_issues(self, *extra):
        issues = []
        next_url = '{}/commits?access_token={}'.format(self.gh_base_url, self.SETTINGS.GITHUB_TOKEN)

        while next_url is not None:
            response = requests.get(next_url)
            response.raise_for_status()
            next_url = response.links.get('next', {}).get('url', None)

            for commit in response.json():
                message = re.sub('FRONT-|SYNGUI-', 'DASH-', commit['commit']['message'])
                issues.extend(self.SETTINGS.ISSUE_PATTERN.findall(message))

        for text in extra:
            message = re.sub('FRONT-|SYNGUI-', 'DASH-', text)
            issues.extend(self.SETTINGS.ISSUE_PATTERN.findall(text))

        return list(set(issues))


class JiraMixin(object):

    def get_jira_jql(self, issues):
        return 'issuekey in ("{}")'.format('","'.join(issues))

    def get_jira_issues(self, issues, fields=None):
        jira_issues = []
        total = len(issues)
        per_chunk = 50
        url = '{}/search/'.format(self.jira_base_url)
        params = {'jql': None, 'maxResults': 1}

        if fields:
            params['fields'] = ','.join(fields)

        for index in range(0, total, per_chunk):
            chunk = issues[index:min(index + per_chunk, total)]

            params['jql'] = self.get_jira_jql(chunk)
            params['maxResults'] = len(chunk)

            response = requests.get(url, params=params, auth=self.jira_auth)
            response.raise_for_status()

            jira_issues.extend(response.json().get('issues', []))

        return jira_issues
