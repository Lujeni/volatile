## Volatile
Fast and easy way to make changes in multiple GitLab project based on template.

## Why ?
After looking for a tool to simply enforce a development practice at the scale of a GitLab instance,
I didn't find anything simple so I started this little script.

The main goal of the script is not to replace GitLab Template, cookiecutter, or even [GitLab includes](https://docs.gitlab.com/ee/ci/yaml/includes.html) but to facilitate adoption and reduce friction.

### Some examples
- Add new task on every `.gitlab-ci.yml` (check [examples](Volatile/templates/example.yml))
- Update a particular file (dependencies, gitignore [...])
- In the context of governance, ensure that all projects have this content

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

| Flag                     | Description                                                                                 | Mandatory   | Default |
|--------------------------|---------------------------------------------------------------------------------------------|-------------|---------|
| `GITLAB_URL`             | Your GitLab instance (e.g. https://gitlab.foo.bar)                                          | yes         | N/a     |
| `GITLAB_PRIVATE_TOKEN`   | [Authentication Token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) | yes         | N/a     |
| `GITLAB_TARGET_FILE`     | The GitLab file you wanna update (e.g. `.gitlab-ci.yml`)                                    | yes         | N/a     |
| `GITLAB_SEARCH`          | Returns project matching the given pattern (default all)                                    | no          | all     |
| `VOLATILE_TEMPLATE_PATH` | The path of the file with the new content (e.g. `volatile/templates/example.yml`)           | yes         | N/a     |
| `VOLATILE_MERGE_REQUEST` | Create merge request, otherwise, script push on default branch                              | no          | True    |

## License
MIT
