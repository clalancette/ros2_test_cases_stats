# Usage

The `ros2_test_cases_stats.py` has two modes:

1. Use it to compute user statistics of closed issues, for example to get the
   top 10 contributors to a ROS or Gazebo tutorial party. Example:

```bash
python3 ros2_test_cases_stats.py --repo osrf/ros2_test_cases --label jazzy
```

1. Get the number of **open** issues assigned to each user. This can be used to
   ensure that users are not assigning too many issues to themselves. Example

```bash
python3 ros2_test_cases_stats.py --repo osrf/ros2_test_cases --label jazzy --assignments

```

In addition to these modes, the `--raw-output` mode can be used to get the raw
JSON, which can then be manipulated with tools such as `jq`. The Github query
contains additional data that is not processed by the python script, so it is
necessary to use `--raw-output` to access these data.

For example, a list of issues and pull requests created to fix issues identified
in a tutorial party can be obtained with the following `jq` command.

```bash
python3 ros2_test_cases_stats.py --repo gazebosim/gazebo_test_cases --label ionic --raw-output raw.json
cat raw.json | jq '.[].data.search.nodes[].timelineItems | select(.totalCount > 0).nodes[] | select(.isCrossRepository == true).source.url'

```
