#!/usr/bin/env python

import os

from flask import Flask, request

from tasks import MarkIssuesTask


app = Flask(__name__)
app.config.from_object(os.getenv('MARK_ISSUES_SETTINGS'))


@app.route('/')
def mark_issues():
    content = request.get_json(silent=True, force=True)
    event = request.headers.get('X-Github-Event')

    if not content or event not in app.config['ALLOWED_EVENTS']:
        return ''

    if event == 'pull_request':
        action = content['action']
        merged = content['pull_request']['merged']
        base = content['pull_request']['base']['ref']
        number = content['pull_request']['number']
        repository = content['repository']['name']

        if action == 'closed' and merged is True and base in app.config['ALLOWED_BRANCHES']:
            MarkIssuesTask().delay(repository, number)

    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
