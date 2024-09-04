# Copyright 2024 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import datetime
from string import Template
import sys
import time
import urllib3

import requests

ISSUE_QUERY = Template("""
{
  search(first: 100, after: $cursor, query: "repo:osrf/ros2_test_cases is:issue created:>=$since", type: ISSUE) {
    pageInfo {
      hasNextPage,
      endCursor
    },
    nodes {
      ... on Issue {
        id,
        number,
        createdAt,
        assignees(first: 100) {
          nodes {
            login
          },
        },
        author {
          login
        },
      },
    },
  }
}
""")


def graphql_query(query: str, token: str) -> dict:
    headers = {'Authorization': f'Bearer {token}'}

    while True:
        try:
            response = requests.post(
                'https://api.github.com/graphql',
                json={'query': query},
                headers=headers)
        except (ValueError, urllib3.exceptions.InvalidChunkLength, urllib3.exceptions.ProtocolError, requests.exceptions.ChunkedEncodingError):
            # We've seen this happen with urllib3 response.py throwing the following exception:
            # Traceback (most recent call last):
            #   File "/usr/lib/python3.10/site-packages/urllib3/response.py", line 697, in _update_chunk_length
            #     self.chunk_left = int(line, 16)
            # ValueError: invalid literal for int() with base 16: b''
            print('Failed HTTP call, sleeping for 10 seconds and trying again')
            time.sleep(10)
            continue

        if response.status_code != 200:
            print('GitHub GraphQL query failed with code {}; sleeping 1 minute.'.format(response.status_code))
            time.sleep(1 * 60)
            continue

        return response.json()


def query_repository_issues(since: str, token: str) -> dict:
    cursor = 'null'
    has_next_page = True
    contributors = {}
    while has_next_page:
        issue_query = ISSUE_QUERY.substitute(
            cursor=cursor,
            since=since)
        response = graphql_query(issue_query, token)
        results = response['data']['search']
        for issue in results['nodes']:
            assignees = issue["assignees"]["nodes"]
            for assignee in assignees:
                login = assignee['login']
                if login not in contributors:
                    contributors[login] = 0
                contributors[login] += 1

        page_info = results['pageInfo']
        if page_info['hasNextPage']:
            # If there are more issues, move the overall cursor forward
            cursor = '"%s"' % (page_info['endCursor'])
            has_next_page = True
        else:
            has_next_page = False

    for num_tests, name in sorted(((v, k) for k, v in contributors.items()), reverse=True):
        print(f'{name}: {num_tests}')

def IsoDate(value: str) -> datetime.date:
    """Validate and translate an argparse input into a datetime.date from ISO format."""
    return datetime.datetime.strptime(value, '%Y-%m-%d').date()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-t', '--token',
        required=True,
        help='Github access token, which must at least have admin:org:read:org and repo:public_repo rights')
    parser.add_argument(
        '-s', '--since',
        type=IsoDate,
        required=True,
        help='Only fetch data since the date specified (in ISO YYYY-MM-DD form)')

    return parser.parse_args()


def main() -> int:
    options = parse_args()

    query_repository_issues(options.since, options.token)

    return 0

if __name__ == '__main__':
    sys.exit(main())
