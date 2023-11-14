"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.vars import Var as Var_

from .base import BaseHTML


class A(BaseHTML):  # Inherits common attributes from BaseMeta
    """Display the 'a' element."""

    tag = "a"

    # Specifies that the target (the file specified in the href attribute) will be downloaded when a user clicks on the hyperlink.
    download: Var_[Union[str, int, bool]]

    # Specifies the URL of the page the link goes to
    href: Var_[Union[str, int, bool]]

    # Specifies the language of the linked document
    href_lang: Var_[Union[str, int, bool]]

    # Specifies what media/device the linked document is optimized for
    media: Var_[Union[str, int, bool]]

    # Specifies which referrer is sent when fetching the resource
    ping: Var_[Union[str, int, bool]]

    # Specifies the relationship between the current document and the linked document
    referrer_policy: Var_[Union[str, int, bool]]

    # Specifies the relationship between the linked document and the current document
    rel: Var_[Union[str, int, bool]]

    # Specifies the shape of the area
    shape: Var_[Union[str, int, bool]]

    # Specifies where to open the linked document
    target: Var_[Union[str, int, bool]]


class Abbr(BaseHTML):  # noqa: E742
    """Display the abbr element."""

    tag = "abbr"


class B(BaseHTML):  # noqa: E742
    """Display the b element."""

    tag = "b"


class Bdi(BaseHTML):  # noqa: E742
    """Display the bdi element."""

    tag = "bdi"


class Bdo(BaseHTML):  # noqa: E742
    """Display the bdo element."""

    tag = "bdo"


class Br(BaseHTML):  # noqa: E742
    """Display the br element."""

    tag = "br"


class Cite(BaseHTML):  # noqa: E742
    """Display the cite element."""

    tag = "cite"


class Code(BaseHTML):  # noqa: E742
    """Display the code element."""

    tag = "code"


class Data(BaseHTML):  # noqa: E742
    """Display the data element."""

    tag = "data"

    value: Var_[Union[str, int, bool]]


class Dfn(BaseHTML):  # noqa: E742
    """Display the dfn element."""

    tag = "dfn"


class Em(BaseHTML):  # noqa: E742
    """Display the em element."""

    tag = "em"


class I(BaseHTML):  # noqa: E742
    """Display the i element."""

    tag = "i"


class Kbd(BaseHTML):  # noqa: E742
    """Display the kbd element."""

    tag = "kbd"


class Mark(BaseHTML):  # noqa: E742
    """Display the mark element."""

    tag = "mark"


class Q(BaseHTML):  # noqa: E742
    """Display the q element."""

    tag = "q"

    cite: Var_[Union[str, int, bool]]


class Rp(BaseHTML):  # noqa: E742
    """Display the rp element."""

    tag = "rp"


class Rt(BaseHTML):  # noqa: E742
    """Display the rt element."""

    tag = "rt"


class Ruby(BaseHTML):  # noqa: E742
    """Display the ruby element."""

    tag = "ruby"


class S(BaseHTML):  # noqa: E742
    """Display the s element."""

    tag = "s"


class Samp(BaseHTML):  # noqa: E742
    """Display the samp element."""

    tag = "samp"


class Small(BaseHTML):  # noqa: E742
    """Display the small element."""

    tag = "small"


class Span(BaseHTML):  # noqa: E742
    """Display the span element."""

    tag = "span"


class Strong(BaseHTML):  # noqa: E742
    """Display the strong element."""

    tag = "strong"


class Sub(BaseHTML):  # noqa: E742
    """Display the sub element."""

    tag = "sub"


class Sup(BaseHTML):  # noqa: E742
    """Display the sup element."""

    tag = "sup"


class Time(BaseHTML):  # noqa: E742
    """Display the time element."""

    tag = "time"
    date_time: Var_[Union[str, int, bool]]


class U(BaseHTML):  # noqa: E742
    """Display the u element."""

    tag = "u"


class Var(BaseHTML):  # noqa: E742
    """Display the var element."""

    tag = "var"


class Wbr(BaseHTML):  # noqa: E742
    """Display the wbr element."""

    tag = "wbr"
