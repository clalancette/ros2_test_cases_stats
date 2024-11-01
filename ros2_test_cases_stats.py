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
import json
from string import Template
import sys
import os
import time
import urllib3

import requests

ISSUE_QUERY = Template("""
{
  search(first: 100, after: $cursor, query: "repo:$repo is:issue label:$label", type: ISSUE) {
    pageInfo {
      hasNextPage,
      endCursor
    },
    nodes {
      ... on Issue {
        id,
        number,
        createdAt,
        closed,
        assignees(first: 100) {
          nodes {
            login
          },
        },
        author {
          login
        },
        timelineItems (first: 100, itemTypes: [CROSS_REFERENCED_EVENT]) {
          totalCount
          nodes {
            ... on CrossReferencedEvent {
              isCrossRepository
              source {
                ... on PullRequest {
                  url
                  merged
                }
                ... on Issue {
                  url
                  closed
                }
              }
            },
          },
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


def query_open_assignment(token: str, repo: str, label: str):
    cursor = 'null'
    has_next_page = True
    contributors = {}
    open_issues_count = 0
    assigned_issues_count = 0
    while has_next_page:
        issue_query = ISSUE_QUERY.substitute(
            cursor=cursor, repo=repo, label=label)
        response = graphql_query(issue_query, token)
        results = response['data']['search']
        for issue in results['nodes']:
            if not issue['closed']:
                assignees = issue["assignees"]["nodes"]
                if assignees:
                    assigned_issues_count += 1
                for assignee in assignees:
                    login = assignee['login']
                    if login not in contributors:
                        contributors[login] = 0
                    contributors[login] += 1
                open_issues_count += 1

        page_info = results['pageInfo']
        if page_info['hasNextPage']:
            # If there are more issues, move the overall cursor forward
            cursor = '"%s"' % (page_info['endCursor'])
            has_next_page = True
        else:
            has_next_page = False

    for i, (num_tests, name) in enumerate(
        sorted(((v, k) for k, v in contributors.items()), reverse=True)
    ):
        print(f'{i + 1}. {name}: {num_tests}')
    print(
        f"Total number of assigned issues {assigned_issues_count} out of {open_issues_count} open issues,\
        {assigned_issues_count * 100.0 / open_issues_count}%"
    )


def query_repository_issues(token: str, repo: str, label: str):
    cursor = 'null'
    has_next_page = True
    contributors = {}
    open_issues_count = 0
    closed_issues_count = 0
    responses = []
    while has_next_page:
        issue_query = ISSUE_QUERY.substitute(
            cursor=cursor, repo=repo, label=label)
        response = graphql_query(issue_query, token)
        responses.append(response)
        results = response['data']['search']
        for issue in results['nodes']:
            if issue['closed']:
                closed_issues_count += 1
                assignees = issue["assignees"]["nodes"]
                for assignee in assignees:
                    login = assignee['login']
                    if login not in contributors:
                        contributors[login] = 0
                    contributors[login] += 1
            else:
                open_issues_count += 1

        page_info = results['pageInfo']
        if page_info['hasNextPage']:
            # If there are more issues, move the overall cursor forward
            cursor = '"%s"' % (page_info['endCursor'])
            has_next_page = True
        else:
            has_next_page = False

    for i, (num_tests, name) in enumerate(
        sorted(((v, k) for k, v in contributors.items()), reverse=True)
    ):
        print(f"{i + 1}. {name}: {num_tests}")
    total_num_tests = open_issues_count + closed_issues_count
    print(
        f"Issues closed {closed_issues_count} out of {total_num_tests},\
        {closed_issues_count * 100.0 / total_num_tests}%"
    )

    return responses


def IsoDate(value: str) -> datetime.date:
    """Validate and translate an argparse input into a datetime.date from ISO format."""
    return datetime.datetime.strptime(value, '%Y-%m-%d').date()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--repo',
        help='Repository in the format <owner>/<repo>. \
                e.g. osrf/ros2_test_cases or gazebosim/gazebo_test_cases. (default: %(default)s)'
        , default="osrf/ros2_test_cases")
    parser.add_argument(
        '--label', required=True,
        help='Label to filter issues by. e.g. jazzy or ionic')
    parser.add_argument(
        '--assignments',
        action='store_true',
        help='Assignment of open issues')
    parser.add_argument(
        '--raw-output',
        type=argparse.FileType('w'),
        help='Output file to save raw JSON output from queries for manual JSON manipulation')

    return parser.parse_args()


def main() -> int:
    options = parse_args()

    token = os.environ.get('GITHUB_TOKEN')
    if token is None or token == '':
        print("GITHUB_TOKEN needs to be set before running this script")
        sys.exit(1)
    if options.assignments:
        query_open_assignment(token, options.repo, options.label)
    else:
        responses = query_repository_issues(token, options.repo, options.label)
        if options.raw_output:
            json.dump(responses, options.raw_output)

    return 0


if __name__ == '__main__':
    sys.exit(main())
