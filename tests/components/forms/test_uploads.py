import os

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
    assert (
        str(upload_component) == f"<ReactDropzone multiple={{true}}{os.linesep}"
        "onDrop={e => File(e)}>{({getRootProps, getInputProps}) => (<Box "
        'sx={{"border": "1px dotted black"}}{...getRootProps()}><Input '
        f'type="file"{{...getInputProps()}}/>{os.linesep}'
        f"<Button>{{`select file`}}</Button>{os.linesep}"
        "<Text>{`Drag and drop files here or click to select "
        "files`}</Text></Box>)}</ReactDropzone>"
    )


def test_upload_component_with_props_render(upload_component_with_props):
    """Test that the render function is set correctly.

    Args:
        upload_component_with_props: component fixture
    """
    assert (
        str(upload_component_with_props) == f"<ReactDropzone maxFiles={{2}}{os.linesep}"
        f"multiple={{true}}{os.linesep}"
        f"noDrag={{true}}{os.linesep}"
        "onDrop={e => File(e)}>{({getRootProps, getInputProps}) => (<Box "
        'sx={{"border": "1px dotted black"}}{...getRootProps()}><Input '
        f'type="file"{{...getInputProps()}}/>{os.linesep}'
        f"<Button>{{`select file`}}</Button>{os.linesep}"
        "<Text>{`Drag and drop files here or click to select "
        "files`}</Text></Box>)}</ReactDropzone>"
    )
