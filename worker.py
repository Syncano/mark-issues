import os

from celery import Celery


os.environ.setdefault('MARK_ISSUES_SETTINGS', 'settings.development')

celery = Celery('mark-issues')
celery.config_from_envvar('MARK_ISSUES_SETTINGS')
