#!/usr/bin/env python3

import argparse
import datetime
import os
import pykube
import time


def parse_time(s: str):
    return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()


parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=int, default=3600, help='Delete all jobs older than ..')
parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
args = parser.parse_args()

try:
    config = pykube.KubeConfig.from_service_account()
except FileNotFoundError:
    # local testing
    config = pykube.KubeConfig.from_file(os.path.expanduser('~/.kube/config'))
api = pykube.HTTPClient(config)

now = time.time()
for job in pykube.Job.objects(api, namespace=pykube.all):
    completion_time = job.obj['status'].get('completionTime')
    if job.obj['status'].get('succeeded') and completion_time:
        completion_time = parse_time(completion_time)
        seconds_since_completion = now - completion_time
        if seconds_since_completion > args.seconds:
            print('Deleting {} ({:.0f}s old)..'.format(job.name, seconds_since_completion))
            if args.dry_run:
                print('** DRY RUN **')
            else:
                job.delete()

for pod in pykube.Pod.objects(api, namespace=pykube.all):
    if pod.obj['status'].get('phase') in ('Succeeded', 'Failed'):
        seconds_since_completion = 0
        for container in pod.obj['status'].get('containerStatuses'):
            if 'terminated' in container['state']:
                if container['state']['terminated']['reason'] == 'Completed':
                    finish = now - parse_time(container['state']['terminated']['finishedAt'])
                    if seconds_since_completion == 0 or finish < seconds_since_completion:
                        seconds_since_completion = finish
        if seconds_since_completion > args.seconds:
            print('Deleting {} ({:.0f}s old)..'.format(pod.name, seconds_since_completion))
            if args.dry_run:
                print('** DRY RUN **')
            else:
                pod.delete()
