"""A html component."""

from typing import Any

from reflex.components.component import Component
from reflex.components.layout.box import Box


class Html(Box):
    """Render the html via React's dangerouslySetInnerHTML."""

    # The HTML to render.
    dangerouslySetInnerHTML: Any

    @classmethod
    def create(cls, *children, **props):
        """Create a html component.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The html component.

        Raises:
            ValueError: If children are not provided or more than one child is provided.
        """
        # If children are not provided, throw an error.
        if len(children) != 1:
            raise ValueError("Must provide children to the html component.")
        else:
            props["dangerouslySetInnerHTML"] = {"__html": children[0]}

        # Create the component.
        return super().create(**props)


class HtmlDangerous(Component):
    """Render the html via createRange().createContextualFragment.

    Allows for execution of scripts in the given HTML without restriction.
    """

    tag = "DangerouslySetHtmlContent"

    # The HTML to render.
    html: Any

    def _get_custom_code(self) -> str:
        """Include DangerouslySetHtmlContent component.

        Copyright 2023 christo-pr (https://github.com/christo-pr)

        Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

        Returns:
            The code to render the DangerouslySetHtmlContent component.
        """
        return """
// Copyright 2023 christo-pr (https://github.com/christo-pr)
function DangerouslySetHtmlContent({ html, dangerouslySetInnerHTML, ...rest }) {
    const divRef = useRef(null)

    useEffect(() => {
    if (!html || !divRef.current) throw new Error("html prop can't be null")

    const slotHtml = document.createRange().createContextualFragment(html)
    divRef.current.innerHTML = ''
    divRef.current.appendChild(slotHtml)
    }, [html, divRef])

    return <div {...rest} ref={divRef} />
}"""
