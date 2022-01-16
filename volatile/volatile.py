#!/usr/bin/python env
import logging
from ast import literal_eval
from os import getenv
from pathlib import Path
from sys import exit

from gitlab import Gitlab

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
        signature.append(line.strip())
    return "".join(signature), content


def get_signature_from_gitlab_file(file):
    """Generate silly signature from GitLab file
    to easily compare content
    """
    signature = []
    for line in file.decode().splitlines():
        signature.append(line.decode().strip())
    return "".join(signature)


class GitlabHelper(object):
    def __init__(self, url, token, timeout, search):
        self.client = None
        self.timeout = timeout
        self.token = token
        self.search = search
        self.url = url
        self.groups = []

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
            return [
                self.client.projects.get(project.id)
                for project in self.client.projects.list(
                    all=True, include_subgroups=True, search=self.search or ""
                )
            ]
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
        except Exception as e:
            logging.error(f"get_file :: {project.name} :: {file_path} :: {e}")
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

    def create_merge_request(self, project, project_file, content):
        """Create a merge request to propose the new content version

        :param project: Project object from GitLab
        :type project: gitlab.Project

        :param project_file: Project file object from GitLab
        :type project_file: gitlab.ProjectFile

        :param content: Content file added
        :type content: str
        """
        # TODO: improve the way to retrieve current branch or merge request to avoid multiple GitLab calls
        branch = f"volatile_{project_file.file_path}"
        try:
            project.branches.delete(branch)
        except Exception:  # nosec
            pass

        project.branches.create({"branch": branch, "ref": project.default_branch})
        self.merge_content(
            project=project, project_file=project_file, content=content, branch=branch
        )

        project.mergerequests.create(
            {
                "remove_source_branch": True,
                "source_branch": branch,
                "target_branch": project.default_branch,
                "title": f"Volatile - new version of {project_file.file_path}",
            }
        )


def main():
    GITLAB_URL = getenv("GITLAB_URL")
    GITLAB_PRIVATE_TOKEN = getenv("GITLAB_PRIVATE_TOKEN")
    GITLAB_TARGET_FILE = getenv("GITLAB_TARGET_FILE")
    GITLAB_TIMEOUT = getenv("GITLAB_TIMEOUT", 3)
    GITLAB_SEARCH = getenv("GITLAB_SEARCH", None)
    #
    VOLATILE_TEMPLATE_PATH = getenv("VOLATILE_TEMPLATE_PATH")
    VOLATILE_MERGE_REQUEST = literal_eval(getenv("VOLATILE_MERGE_REQUEST", "True"))

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

    gitlab_helper = GitlabHelper(
        url=GITLAB_URL,
        token=GITLAB_PRIVATE_TOKEN,
        timeout=GITLAB_TIMEOUT,
        search=GITLAB_SEARCH,
    )
    gitlab_helper.connect()
    for project in gitlab_helper.get_projects():
        logging.info(f"{project.name} :: {GITLAB_TARGET_FILE}")
        gitlab_file = gitlab_helper.get_file(
            project=project, file_path=GITLAB_TARGET_FILE
        )
        if not gitlab_file:
            logging.info(f"{project.name} :: {GITLAB_TARGET_FILE} :: not found")
            continue

        gitlab_file_signature = get_signature_from_gitlab_file(file=gitlab_file)
        if template_file_signature in gitlab_file_signature:
            logging.info(f"{project.name} :: {GITLAB_TARGET_FILE} :: already good")
            continue

        if not VOLATILE_MERGE_REQUEST:
            gitlab_helper.merge_content(
                project=project, project_file=gitlab_file, content=template_file_content
            )
            logging.info(f"{project.name} :: {GITLAB_TARGET_FILE} :: push")
            continue

        logging.info(f"{project.name} :: {GITLAB_TARGET_FILE} :: merge request")
        gitlab_helper.create_merge_request(
            project=project, project_file=gitlab_file, content=template_file_content
        )


if __name__ == "__main__":
    main()
