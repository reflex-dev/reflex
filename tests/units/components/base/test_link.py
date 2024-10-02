from reflex.components.base.link import RawLink, ScriptTag


def test_raw_link():
    raw_link = RawLink.create("https://example.com").render()
    assert raw_link["name"] == "link"
    assert raw_link["children"][0]["contents"] == '{"https://example.com"}'


def test_script_tag():
    script_tag = ScriptTag.create("console.log('Hello, world!');").render()
    assert script_tag["name"] == "script"
    assert (
        script_tag["children"][0]["contents"] == "{\"console.log('Hello, world!');\"}"
    )
