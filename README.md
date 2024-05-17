# Usage

## Configuration

Copy [.env.example](.env.example) to `.env` and fill required credentials

`toggl_api_token` and `tempo_api_token` are required only for Toggl import

## Importing JIRA entries from Toggl

To sync toggl entries with JIRA run:

`$ python3 sync.py`

## Submitting iTime reports

### Setup:
In [jira_itime_task_mapping.json](jira_itime_task_mapping.json) you can associate Jira issues/accounts to specific iTime jobs (especially for administration tasks)
By default there are preconfigured most common cases

Also for each itime job ID you need to specify its name (under `task_names` section) which must be obtained in iTime

### Running
To submit itime reports for selected weeks run:

`$ python3 itime.py`