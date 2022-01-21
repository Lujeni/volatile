import pytest


@pytest.fixture
def template_content():
    yield "hello\nworld"


@pytest.fixture
def create_file(tmp_path, template_content):
    p = tmp_path / "hello.txt"
    p.write_text(template_content)
    yield p
    p.unlink()
