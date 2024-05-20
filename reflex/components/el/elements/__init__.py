"""Element classes."""
# from .forms import (
#     Button,
#     Fieldset,
#     Form,
#     Input,
#     Label,
#     Legend,
#     Meter,
#     Optgroup,
#     Option,
#     Output,
#     Progress,
#     Select,
#     Textarea,
# )
# from .inline import (
#     A,
#     Abbr,
#     B,
#     Bdi,
#     Bdo,
#     Br,
#     Cite,
#     Code,
#     Data,
#     Dfn,
#     Em,
#     I,
#     Kbd,
#     Mark,
#     Q,
#     Rp,
#     Rt,
#     Ruby,
#     S,
#     Samp,
#     Small,
#     Span,
#     Strong,
#     Sub,
#     Sup,
#     Time,
#     U,
#     Wbr,
# )
# from .media import (
#     Area,
#     Audio,
#     Embed,
#     Iframe,
#     Img,
#     Map,
#     Object,
#     Path,
#     Picture,
#     Portal,
#     Source,
#     Svg,
#     Track,
#     Video,
# )
# from .metadata import Base, Head, Link, Meta, Title
# from .other import Details, Dialog, Html, Math, Slot, Summary, Template
# from .scripts import Canvas, Noscript, Script
# from .sectioning import (
#     H1,
#     H2,
#     H3,
#     H4,
#     H5,
#     H6,
#     Address,
#     Article,
#     Aside,
#     Body,
#     Footer,
#     Header,
#     Main,
#     Nav,
#     Section,
# )
# from .tables import Caption, Col, Colgroup, Table, Tbody, Td, Tfoot, Th, Thead, Tr
# from .typography import (
#     Blockquote,
#     Dd,
#     Del,
#     Div,
#     Dl,
#     Dt,
#     Figcaption,
#     Hr,
#     Ins,
#     Li,
#     Ol,
#     P,
#     Pre,
#     Ul,
# )

# Forms
# button = Button.create
# fieldset = Fieldset.create
# form = Form.create
# input = Input.create
# label = Label.create
# legend = Legend.create
# meter = Meter.create
# optgroup = Optgroup.create
# option = Option.create
# output = Output.create
# progress = Progress.create
# select = Select.create
# textarea = Textarea.create
#
# # Tables
# caption = Caption.create
# col = Col.create
# colgroup = Colgroup.create
# table = Table.create
# tbody = Tbody.create
# td = Td.create
# tfoot = Tfoot.create
# th = Th.create
# thead = Thead.create
# tr = Tr.create
#
# # Media
# area = Area.create
# audio = Audio.create
# img = Img.create
# map = Map.create
# track = Track.create
# video = Video.create
# embed = Embed.create
# iframe = Iframe.create
# object = Object.create
# picture = Picture.create
# portal = Portal.create
# source = Source.create
# svg = Svg.create
# path = Path.create
#
# # Sectioning
# address = Address.create
# article = Article.create
# aside = Aside.create
# body = Body.create
# header = Header.create
# footer = Footer.create
# h1 = H1.create
# h2 = H2.create
# h3 = H3.create
# h4 = H4.create
# h5 = H5.create
# h6 = H6.create
# main = Main.create
# nav = Nav.create
# section = Section.create
#
# # Typography
# blockquote = Blockquote.create
# dd = Dd.create
# div = Div.create
# dl = Dl.create
# dt = Dt.create
# figcaption = Figcaption.create
# hr = Hr.create
# li = Li.create
# ol = Ol.create
# p = P.create
# pre = Pre.create
# ul = Ul.create
# ins = Ins.create
# del_ = Del.create  # 'del' is a reserved keyword in Python
#
#
# # Inline
# a = A.create
# abbr = Abbr.create
# b = B.create
# bdi = Bdi.create
# bdo = Bdo.create
# br = Br.create
# cite = Cite.create
# code = Code.create
# data = Data.create
# dfn = Dfn.create
# em = Em.create
# i = I.create
# kbd = Kbd.create
# mark = Mark.create
# q = Q.create
# rp = Rp.create
# rt = Rt.create
# ruby = Ruby.create
# s = S.create
# samp = Samp.create
# small = Small.create
# span = Span.create
# strong = Strong.create
# sub = Sub.create
# sup = Sup.create
# time = Time.create
# u = U.create
# wbr = Wbr.create
#
# # Metadata
# base = Base.create
# head = Head.create
# link = Link.create
# meta = Meta.create
# title = Title.create
#
# # Scripts
# canvas = Canvas.create
# noscript = Noscript.create
# script = Script.create
#
# # Other
# details = Details.create
# dialog = Dialog.create
# summary = Summary.create
# slot = Slot.create
# template = Template.create
# math = Math.create
# html = Html.create

MAP = {
        "forms": [
            "button",
            "fieldset",
            "form",
            "input",
            "label",
            "legend",
            "meter",
            "optgroup",
            "option",
            "output",
            "progress",
            "select",
            "textarea"
        ],
        "inline": [
            "a",
            "A",
            "abbr",
            "Abbr",
            "b",
            "bdi",
            "bdo",
            "br",
            "cite",
            "code",
            "data",
            "dfn",
            "em",
            # "Em",
            "i",
            "kbd",
            "mark",
            "q",
            "rp",
            "rt",
            "ruby",
            "s",
            "samp",
            "small",
            "span",
            # "Span",
            "strong",
            "sub",
            "sup",
            "time",
            "u",
            "wbr"
        ],
        "media": [
            "area",
            "audio",
            "img",
            "map",
            "track",
            "video",
            "embed",
            "iframe",
            "object",
            "picture",
            "portal",
            "source",
            "svg",
            "path"
        ],
        "metadata": [
            "base",
            "head",
            "link",
            "meta",
            "title",
        ],
        "other": [
            "details",
            "dialog",
            "summary",
            "slot",
            "template",
            "math",
            "html"
        ],
        "scripts": [
            "canvas",
            "noscript",
            "script"
        ],
        "sectioning": [
            "address",
            "article",
            "aside",
            "body",
            "header",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "main",
            "nav",
            "section"
        ],
        "tables": [
            "caption",
            "col",
            "colgroup",
            "table",
            "td",
            "tfoot",
            "th",
            "thead",
            "tr"
        ],
        "typography": [
            "blockquote",
            "dd",
            "div",
            # "Div",
            "dl",
            "dt",
            "figcaption",
            "hr",
            "ol",
            "li",
            "p",
            "pre",
            "ul",
            "ins",
            "del_",
            "Del"
        ],
    }
import lazy_loader as lazy
# fin_map = {f"elements.{key}": value for key, value in MAP.items()}
# fin_map.update(MAP)
EXCLUDE = ["del_", "Del"]
for k, v in MAP.items():
    v.extend([a.capitalize() if not a in EXCLUDE else a for a in v])

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"base"},
    submod_attrs=MAP,
)