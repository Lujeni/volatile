[![Docker Image CI](https://github.com/Lujeni/volatile/actions/workflows/docker-image.yml/badge.svg)](https://github.com/Lujeni/volatile/actions/workflows/docker-image.yml) [![Python application](https://github.com/Lujeni/volatile/actions/workflows/python-app.yml/badge.svg)](https://github.com/Lujeni/volatile/actions/workflows/python-app.yml)

## Volatile
Fast and easy way to make changes in multiple GitLab project based on template.

## Why ?
After looking for a tool to simply enforce a development practice at the scale of a GitLab instance,
I didn't find anything simple so I started this little script.

### Some examples
- Add new task on every `.gitlab-ci.yml` (check [examples](Volatile/templates/example.yml))
- Apply new change on particular file (e.g. gitignore)
- In the context of governance, ensure that all projects have this content on this specific file
- Optout system, user can close the merge request, Volatile considered this specific template version as optout

### Similar (and/or better) tool
- https://github.com/lindell/multi-gitter

## Usage
### Running locally
#### Requirements
* Python 3 (should also work with Python 2 but it's not supported)
* Virtualenv (recommended)

#### Setup
Then you can clone the repository, install the dependencies and run `Volatile`:

```sh
$ git clone https://github.com/Lujeni/volatile.git
$ cd volatile
# optional
$ virtualenv .venv && source .venv/bin/activate
(.venv) $ pip install -r requirements.txt
(.venv) $ python volatile/volatile.py
```

#### Configuration
Volatile supports multiple environment variables for configuration:

| Flag                          | Description                                                                                 | Mandatory | Default      |
|-------------------------------|---------------------------------------------------------------------------------------------|-----------|--------------|
| `GITLAB_URL`                  | Your GitLab instance (e.g. https://gitlab.foo.bar)                                          | yes       | N/a          |
| `GITLAB_PRIVATE_TOKEN`        | [Authentication Token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) | yes       | N/a          |
| `GITLAB_TARGET_FILE`          | The GitLab file you wanna update (e.g. `.gitlab-ci.yml`)                                    | yes       | N/a          |
| `GITLAB_SEARCH`               | Returns project matching the given pattern (default all)                                    | no        | all          |
| `GITLAB_SEARCH_IN_GROUP`      | Returns project inside this group (cant be use with GITLAB_SEARCH)                          | no        | None         |
| `GITLAB_MR_DESCRIPTION`       | Description of MR. Limited to 1,048,576 characters                                          | no        | None         |
| `GITLAB_EXCLUDE`              | Exclude project from their name based on fnmatch pattern (e.g. `foo*,bar*`)                 | no        | None         |
| `VOLATILE_DRY_RUN`            | It will not make any changes on remote system (GitLab)                                      | no        | True         |
| `VOLATILE_TEMPLATE_PATH`      | The path of the file with the new content (e.g. `volatile/templates/example.yml`)           | yes       | N/a          |
| `VOLATILE_MERGE_REQUEST`      | Create merge request, otherwise, script push on default branch                              | no        | True         |
| `VOLATILE_PROMETHEUS_PORT`    | Prometheus HTTP port                                                                        | no        | 8000         |
| `VOLATILE_PROMETHEUS_GATEWAY` | The Prometheus Gateway address                                                              | no        | N/a          |


#### Metrics
By default, Volatile expose a temporary prometheus HTTP server with few metrics.
The main goal is to track the adoption of your template.
If you prefer, you can use a Prometheus Gateway (check configuration above).

![](example_metrics.png)

### Using Kubernetes
You can use this simple [manifest](kubernetes.yml), before using it, replace with your current setup (e.g. GITLAB_URL)

## License
MIT
