import pytest

import pynecone as pc


@pytest.fixture
def upload_component():
    """A test upload component function.

    Returns:
        A test upload component function.
    """

    def upload_component():
        return pc.upload(
            pc.button("select file"),
            pc.text("Drag and drop files here or click to select files"),
            border="1px dotted black",
        )

    return upload_component()


@pytest.fixture
def upload_component_with_props():
    """A test upload component with props function.

    Returns:
        A test upload component with props function.
    """

    def upload_component_with_props():
        return pc.upload(
            pc.button("select file"),
            pc.text("Drag and drop files here or click to select files"),
            border="1px dotted black",
            no_drag=True,
            max_files=2,
        )

    return upload_component_with_props()


def test_upload_component_render(upload_component):
    """Test that the render function is set correctly.

    Args:
        upload_component: component fixture
    """
    upload = upload_component.render()

    # upload
    assert upload["name"] == "ReactDropzone"
    assert upload["props"] == [
        "multiple={true}",
        "onDrop={e => File(e)}",
    ]
    assert upload["args"] == ("getRootProps", "getInputProps")

    # box inside of upload
    [box] = upload["children"]
    assert box["name"] == "Box"
    assert box["props"] == [
        'sx={{"border": "1px dotted black"}}',
        "{...getRootProps()}",
    ]

    # input, button and text inside of box
    [input, button, text] = box["children"]
    assert input["name"] == "Input"
    assert input["props"] == ['type="file"', "{...getInputProps()}"]

    assert button["name"] == "Button"
    assert button["children"][0]["contents"] == "{`select file`}"

    assert text["name"] == "Text"
    assert (
        text["children"][0]["contents"]
        == "{`Drag and drop files here or click to select files`}"
    )


def test_upload_component_with_props_render(upload_component_with_props):
    """Test that the render function is set correctly.

    Args:
        upload_component_with_props: component fixture
    """
    upload = upload_component_with_props.render()

    assert upload["props"] == [
        "maxFiles={2}",
        "multiple={true}",
        "noDrag={true}",
        "onDrop={e => File(e)}",
    ]
