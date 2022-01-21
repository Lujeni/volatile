from volatile.volatile import get_signature_from_file


def test_get_signature_from_field(create_file, template_content):
    signature, content = get_signature_from_file(path=create_file)
    assert signature == "helloworld"
    assert content == template_content
