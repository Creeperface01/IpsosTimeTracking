# Usage

## Configuration

Copy [.env.example](.env.example) to `.env` and fill required credentials

`toggl_api_token` and `tempo_api_token` are required only for Toggl import

### Create environemnt

This project uses [poetry](https://python-poetry.org/docs/) for dependency management.

- Install dependencies: `poetry install`
- Enter python shell: `poetry shell`
- Run scripts: `python itime.py`

## Importing JIRA entries from Toggl

To sync toggl entries with JIRA run:

`python sync.py`

## Submitting iTime reports

### Note
iTime submitter is currently more suitable for self-employed, 
since it does not handle different types of time off work.
To support this some kind of integration with financial gate would be required.

### Setup:
In [jira_itime_task_mapping.json](jira_itime_task_mapping.json) you can associate Jira issues/accounts to specific iTime jobs (especially for administration tasks)
By default there are preconfigured most common cases

Also for each itime job ID you need to specify its name (under `task_names` section) which must be obtained in iTime

### Running
To submit itime reports for selected weeks run:

`python itime.py`