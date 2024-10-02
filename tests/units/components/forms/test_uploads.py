import pytest

import reflex as rx


@pytest.fixture
def upload_root_component():
    """A test upload component function.

    Returns:
        A test upload component function.
    """

    def upload_root_component():
        return rx.upload.root(
            rx.button("select file"),
            rx.text("Drag and drop files here or click to select files"),
            border="1px dotted black",
        )

    return upload_root_component()


@pytest.fixture
def upload_component():
    """A test upload component function.

    Returns:
        A test upload component function.
    """

    def upload_component():
        return rx.upload(
            rx.button("select file"),
            rx.text("Drag and drop files here or click to select files"),
            border="1px dotted black",
        )

    return upload_component()


@pytest.fixture
def upload_component_id_special():
    def upload_component():
        return rx.upload(
            rx.button("select file"),
            rx.text("Drag and drop files here or click to select files"),
            border="1px dotted black",
            id="#spec!`al-_98ID",
        )

    return upload_component()


@pytest.fixture
def upload_component_with_props():
    """A test upload component with props function.

    Returns:
        A test upload component with props function.
    """

    def upload_component_with_props():
        return rx.upload(
            rx.button("select file"),
            rx.text("Drag and drop files here or click to select files"),
            border="1px dotted black",
            no_drag=True,
            max_files=2,
        )

    return upload_component_with_props()


def test_upload_root_component_render(upload_root_component):
    """Test that the render function is set correctly.

    Args:
        upload_root_component: component fixture
    """
    upload = upload_root_component.render()

    # upload
    assert upload["name"] == "ReactDropzone"
    assert upload["props"] == [
        'id={"default"}',
        "multiple={true}",
        "onDrop={e => setFilesById(filesById => {\n"
        "    const updatedFilesById = Object.assign({}, filesById);\n"
        '    updatedFilesById["default"] = e;\n'
        "    return updatedFilesById;\n"
        "  })\n"
        "    }",
        "ref={ref_default}",
    ]
    assert upload["args"] == ("getRootProps", "getInputProps")

    # box inside of upload
    [box] = upload["children"]
    assert box["name"] == "RadixThemesBox"
    assert box["props"] == [
        'className={"rx-Upload"}',
        'css={({ ["border"] : "1px dotted black" })}',
        "{...getRootProps()}",
    ]

    # input, button and text inside of box
    [input, button, text] = box["children"]
    assert input["name"] == "input"
    assert input["props"] == ['type={"file"}', "{...getInputProps()}"]

    assert button["name"] == "RadixThemesButton"
    assert button["children"][0]["contents"] == '{"select file"}'

    assert text["name"] == "RadixThemesText"
    assert (
        text["children"][0]["contents"]
        == '{"Drag and drop files here or click to select files"}'
    )


def test_upload_component_render(upload_component):
    """Test that the render function is set correctly.

    Args:
        upload_component: component fixture
    """
    upload = upload_component.render()

    # upload
    assert upload["name"] == "ReactDropzone"
    assert upload["props"] == [
        'id={"default"}',
        "multiple={true}",
        "onDrop={e => setFilesById(filesById => {\n"
        "    const updatedFilesById = Object.assign({}, filesById);\n"
        '    updatedFilesById["default"] = e;\n'
        "    return updatedFilesById;\n"
        "  })\n"
        "    }",
        "ref={ref_default}",
    ]
    assert upload["args"] == ("getRootProps", "getInputProps")

    # box inside of upload
    [box] = upload["children"]
    assert box["name"] == "RadixThemesBox"
    assert box["props"] == [
        'className={"rx-Upload"}',
        'css={({ ["border"] : "1px dotted black", ["padding"] : "5em", ["textAlign"] : "center" })}',
        "{...getRootProps()}",
    ]

    # input, button and text inside of box
    [input, button, text] = box["children"]
    assert input["name"] == "input"
    assert input["props"] == ['type={"file"}', "{...getInputProps()}"]

    assert button["name"] == "RadixThemesButton"
    assert button["children"][0]["contents"] == '{"select file"}'

    assert text["name"] == "RadixThemesText"
    assert (
        text["children"][0]["contents"]
        == '{"Drag and drop files here or click to select files"}'
    )


def test_upload_component_with_props_render(upload_component_with_props):
    """Test that the render function is set correctly.

    Args:
        upload_component_with_props: component fixture
    """
    upload = upload_component_with_props.render()

    assert upload["props"] == [
        'id={"default"}',
        "maxFiles={2}",
        "multiple={true}",
        "noDrag={true}",
        "onDrop={e => setFilesById(filesById => {\n"
        "    const updatedFilesById = Object.assign({}, filesById);\n"
        '    updatedFilesById["default"] = e;\n'
        "    return updatedFilesById;\n"
        "  })\n"
        "    }",
        "ref={ref_default}",
    ]


def test_upload_component_id_with_special_chars(upload_component_id_special):
    upload = upload_component_id_special.render()

    assert upload["props"] == [
        r'id={"#spec!`al-_98ID"}',
        "multiple={true}",
        "onDrop={e => setFilesById(filesById => {\n"
        "    const updatedFilesById = Object.assign({}, filesById);\n"
        '    updatedFilesById["#spec!`al-_98ID"] = e;\n'
        "    return updatedFilesById;\n"
        "  })\n"
        "    }",
        "ref={ref__spec_al__98ID}",
    ]
