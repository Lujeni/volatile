#!/usr/bin/python env
import logging
from ast import literal_eval
from fnmatch import fnmatch
from hashlib import sha256
from os import getenv
from pathlib import Path
from sys import exit
from time import sleep

from gitlab import Gitlab
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    push_to_gateway,
    start_http_server,
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


def get_signature_from_file(path):
    """Generate silly signature from template file
       to easily compare content

    :param path: Path of the template file
    :param path: str

    :return: signature, content file
    :rtype: str, str
    """
    signature = []
    content = Path(path).read_text()
    for line in content:
        signature.append(line.strip().replace(" ", ""))
    return "".join(signature), content


def get_signature_from_gitlab_file(file):
    """Generate silly signature from GitLab file
    to easily compare content
    """
    signature = []
    for line in file.decode().splitlines():
        signature.append(line.decode().strip().replace(" ", ""))
    return "".join(signature)


class GitlabHelper(object):
    def __init__(
        self,
        url,
        token,
        timeout,
        search,
        search_in_group,
        mr_description,
        dry_run,
        volatile_template_path,
        metrics,
        exclude,
    ):
        self.client = None
        self.timeout = timeout
        self.token = token
        self.search = search
        self.search_in_group = search_in_group
        self.url = url
        self.groups = []
        self.exclude = exclude
        #
        self.mr_description = mr_description
        self.dry_run = dry_run
        #
        self.volatile_template_path = volatile_template_path
        #
        self.metrics = metrics
        print(self)

    def __repr__(self):
        return f"url={self.url} :: timeout={self.timeout} :: search={self.search} :: search_in_group={self.search_in_group} :: mr_description={self.mr_description} :: dry_run={self.dry_run} :: volatile_template_path={self.volatile_template_path} :: exclude={self.exclude}"

    def connect(self):
        """Performs an authentication via private token

        Raises:
            exception: If any errors occurs
        """
        try:
            self.client = Gitlab(
                url=self.url, private_token=self.token, timeout=self.timeout
            )
            self.client.auth()
        except Exception as e:
            raise Exception("unable to connect on gitlab :: {}".format(e))

    def get_projects(self):
        """Get all projects

        :return: List of GitLab project for success, empty otherwise
        :rtype: list
        """
        try:
            projects = []
            project_reference = []
            if self.search_in_group:
                groups = self.client.groups.list(search=self.search_in_group)
                for group in groups:
                    project_reference += group.projects.list(
                        all=True, include_subgroups=True
                    )
            else:
                project_reference = self.client.projects.list(
                    all=True, include_subgroups=True, search=self.search or ""
                )

            for project in project_reference:
                _project = self.client.projects.get(project.id)
                for exclude_pattern in self.exclude:
                    if fnmatch(_project.name, exclude_pattern):
                        logging.info(f"get_projects :: {_project.name} :: exclude=True")
                        self.metrics["excluded"].labels(
                            template=self.volatile_template_path,
                            gitlab_search=self.search,
                            gitlab_search_in_group=self.search_in_group,
                        ).inc(1)
                        break
                else:
                    projects.append(_project)
            self.metrics["total"].labels(
                template=self.volatile_template_path,
                gitlab_search=self.search,
                gitlab_search_in_group=self.search_in_group,
            ).set(len(projects))
            return projects
        except Exception as e:
            logging.error("unable to get projects :: {}".format(e))
        return []

    def get_file(self, project, file_path):
        """Retrieve file via GitLab project

        :param project: Project object from GitLab
        :type project: gitlab.Project

        :param file_path: .
        :type file_path: str

        :return: ProjectFile for sucess, None otherwise
        :rtype: gitlab.ProjectFile
        """
        try:
            return project.files.get(file_path=file_path, ref=project.default_branch)
        except Exception:
            return None
        return None

    def merge_content(self, project, project_file, content, branch=None):
        """Merge the actual content file with the new one

        :param project: Project object from GitLab
        :type project: gitlab.Project

        :param project_file: Project file object from GitLab
        :type project_file: gitlab.ProjectFile

        :param content: Content file added
        :type content: str

        :param branch: Override the default project branch
        :type branch: None or str

        :return: ProjectFile updated for success, None otherwise
        :rtype: gitlab.ProjectFile
        """
        project_file.content = f"{project_file.decode().decode()}\n{content}"
        try:
            project_file.save(
                branch=branch or project.default_branch,
                commit_message=f"Volatile update {project_file.file_path}",
            )
            return project_file
        except Exception as e:
            logging.error(
                f"merge_content :: {project.name} :: {project_file.file_path} :: {e}"
            )
            return None

    def is_optout(self, project, branch):
        """Check if the project decided to be 'optout' for a specific version

        :param project: Project object from GitLab
        :type project: gitlab.Project

        :param branch: branch's name used by the merge request
        :type branch: str

        :return: True if the project is optout, False otherwise
        :rtype: bool
        """
        for merge_request in project.mergerequests.list():
            if (
                merge_request.state == "closed"
                and merge_request.source_branch == branch
            ):
                return True
        return False

    def is_waiting(self, project, branch):
        """Check if the project 'waiting' for a specific version

        :param project: Project object from GitLab
        :type project: gitlab.Project

        :param branch: branch's name used by the merge request
        :type branch: str

        :return: True if the project is optout, False otherwise
        :rtype: bool
        """
        for merge_request in project.mergerequests.list():
            if (
                merge_request.state == "opened"
                and merge_request.source_branch == branch
            ):
                return True
        return False

    def create_merge_request(
        self, project, project_file, template_file_signature, content
    ):
        """Create a merge request to propose the new content version

        :param project: Project object from GitLab
        :type project: gitlab.Project

        :param project_file: Project file object from GitLab
        :type project_file: gitlab.ProjectFile

        :param template_file_signature:
        :type template_file_signature:

        :param content: Content file added
        :type content: str
        """
        branch_hash = sha256(template_file_signature.encode()).hexdigest()
        branch = f"volatile_{branch_hash}"

        if self.is_optout(project=project, branch=branch):
            logging.info(
                f"{project.name} :: {project_file.file_path} :: merge request :: optout"
            )
            self.metrics["refused"].labels(
                template=self.volatile_template_path,
                gitlab_search=self.search,
                gitlab_search_in_group=self.search_in_group,
            ).inc()
            return None

        if self.is_waiting(project=project, branch=branch):
            logging.info(
                f"{project.name} :: {project_file.file_path} :: merge request :: waiting"
            )
            self.metrics["waiting"].labels(
                template=self.volatile_template_path,
                gitlab_search=self.search,
                gitlab_search_in_group=self.search_in_group,
            ).inc()
            return None

        if not self.dry_run:
            try:
                project.branches.delete(branch)
            except Exception:  # nosec
                pass

            project.branches.create({"branch": branch, "ref": project.default_branch})
            self.merge_content(
                project=project,
                project_file=project_file,
                content=content,
                branch=branch,
            )

            project.mergerequests.create(
                {
                    "description": self.mr_description,
                    "remove_source_branch": True,
                    "source_branch": branch,
                    "target_branch": project.default_branch,
                    "title": f"Volatile - new version of {project_file.file_path}",
                }
            )
        logging.info(
            f"{project.name} :: {project_file.file_path} :: merge request :: create"
        )
        self.metrics["waiting"].labels(
            template=self.volatile_template_path,
            gitlab_search=self.search,
            gitlab_search_in_group=self.search_in_group,
        ).inc()


def main():
    GITLAB_URL = getenv("GITLAB_URL")
    GITLAB_PRIVATE_TOKEN = getenv("GITLAB_PRIVATE_TOKEN")
    GITLAB_TARGET_FILE = getenv("GITLAB_TARGET_FILE")
    GITLAB_TIMEOUT = getenv("GITLAB_TIMEOUT", 3)
    GITLAB_SEARCH = getenv("GITLAB_SEARCH", None)
    GITLAB_SEARCH_IN_GROUP = getenv("GITLAB_SEARCH_IN_GROUP", None)
    GITLAB_EXCLUDE = getenv("GITLAB_EXCLUDE", [])
    if GITLAB_EXCLUDE:
        GITLAB_EXCLUDE = GITLAB_EXCLUDE.split(",")
    #
    GITLAB_MR_DESCRIPTION = getenv("GITLAB_MR_DESCRIPTION", None)
    #
    VOLATILE_TEMPLATE_PATH = getenv("VOLATILE_TEMPLATE_PATH")
    VOLATILE_MERGE_REQUEST = literal_eval(getenv("VOLATILE_MERGE_REQUEST", "True"))
    VOLATILE_DRY_RUN = literal_eval(getenv("VOLATILE_DRY_RUN", "True"))
    VOLATILE_PROMETHEUS_PORT = int(getenv("VOLATILE_PROMETHEUS_PORT", "8000"))
    VOLATILE_PROMETHEUS_GATEWAY = getenv("VOLATILE_PROMETHEUS_GATEWAY", "")

    if not GITLAB_URL:
        print("missing variable GITLAB_URL")
        exit(1)

    if not GITLAB_PRIVATE_TOKEN:
        print("missing variable GITLAB_PRIVATE_TOKEN")
        exit(1)

    if not GITLAB_TARGET_FILE:
        print("missing variable GITLAB_TARGET_FILE")
        exit(1)

    if not VOLATILE_TEMPLATE_PATH:
        print("missing variable VOLATILE_TEMPLATE_PATH")
        exit(1)

    template_file_signature, template_file_content = get_signature_from_file(
        path=VOLATILE_TEMPLATE_PATH
    )

    # prometheus stuff
    registry = CollectorRegistry()
    metrics = {}

    # I dunno why registry=None disabled pull system
    if VOLATILE_PROMETHEUS_GATEWAY:
        metrics["total"] = Gauge(
            "volatile_projects_total",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
            registry=registry,
        )
        metrics["done"] = Gauge(
            "volatile_projects_done",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
            registry=registry,
        )
        metrics["refused"] = Gauge(
            "volatile_projects_refused",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
            registry=registry,
        )
        metrics["waiting"] = Gauge(
            "volatile_projects_waiting",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
            registry=registry,
        )
        metrics["missing"] = Gauge(
            "volatile_projects_missing",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
            registry=registry,
        )
        metrics["excluded"] = Gauge(
            "volatile_projects_excluded",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
            registry=registry,
        )
    else:
        metrics["total"] = Gauge(
            "volatile_projects_total",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
        )
        metrics["done"] = Gauge(
            "volatile_projects_done",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
        )
        metrics["refused"] = Gauge(
            "volatile_projects_refused",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
        )
        metrics["waiting"] = Gauge(
            "volatile_projects_waiting",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
        )
        metrics["missing"] = Gauge(
            "volatile_projects_missing",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
        )
        metrics["excluded"] = Gauge(
            "volatile_projects_excluded",
            ".",
            ["template", "gitlab_search", "gitlab_search_in_group"],
        )

    if not VOLATILE_PROMETHEUS_GATEWAY:
        start_http_server(VOLATILE_PROMETHEUS_PORT)

    gitlab_helper = GitlabHelper(
        url=GITLAB_URL,
        token=GITLAB_PRIVATE_TOKEN,
        timeout=GITLAB_TIMEOUT,
        search=GITLAB_SEARCH,
        search_in_group=GITLAB_SEARCH_IN_GROUP,
        mr_description=GITLAB_MR_DESCRIPTION,
        dry_run=VOLATILE_DRY_RUN,
        volatile_template_path=VOLATILE_TEMPLATE_PATH,
        metrics=metrics,
        exclude=GITLAB_EXCLUDE,
    )

    gitlab_helper.connect()
    for project in gitlab_helper.get_projects():
        logging.info(f"{project.name} :: {GITLAB_TARGET_FILE}")
        gitlab_file = gitlab_helper.get_file(
            project=project, file_path=GITLAB_TARGET_FILE
        )
        if not gitlab_file:
            logging.info(f"{project.name} :: {GITLAB_TARGET_FILE} :: not found")
            metrics["missing"].labels(
                template=VOLATILE_TEMPLATE_PATH,
                gitlab_search=GITLAB_SEARCH,
                gitlab_search_in_group=GITLAB_SEARCH_IN_GROUP,
            ).inc()
            continue

        gitlab_file_signature = get_signature_from_gitlab_file(file=gitlab_file)
        if template_file_signature in gitlab_file_signature:
            logging.info(f"{project.name} :: {GITLAB_TARGET_FILE} :: already good")
            metrics["done"].labels(
                template=VOLATILE_TEMPLATE_PATH,
                gitlab_search=GITLAB_SEARCH,
                gitlab_search_in_group=GITLAB_SEARCH_IN_GROUP,
            ).inc()
            continue

        if not VOLATILE_MERGE_REQUEST:
            if not VOLATILE_DRY_RUN:
                gitlab_helper.merge_content(
                    project=project,
                    project_file=gitlab_file,
                    content=template_file_content,
                )
            logging.info(f"{project.name} :: {GITLAB_TARGET_FILE} :: push")
            continue

        gitlab_helper.create_merge_request(
            project=project,
            project_file=gitlab_file,
            template_file_signature=template_file_signature,
            content=template_file_content,
        )

    if VOLATILE_PROMETHEUS_GATEWAY:
        logging.info(f"push metrics via gateway :: {VOLATILE_PROMETHEUS_GATEWAY}")
        push_to_gateway(
            VOLATILE_PROMETHEUS_GATEWAY, job="batch-volatile", registry=registry
        )
        logging.info("push metrics via gateway :: done")
        return
    logging.debug("waiting the silly scrapper")
    sleep(240)


if __name__ == "__main__":
    main()
