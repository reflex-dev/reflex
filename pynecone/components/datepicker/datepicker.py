import pynecone as pc
from pynecone.var import Var


class DatePicker(pc.Component):
    library = "react-datepicker"
    tag = "DatePicker"
    value: Var[str]
    date_format: Var[str]
    close_on_scroll: Var[bool]
    start_date: Var[str]
    end_date: Var[str]
    is_clearable: Var[bool]
    show_week_numbers: Var[bool]
    should_close_on_select: Var[bool]
    placeholder_text: Var[str]

    @classmethod
    def get_controlled_triggers(cls) -> set[str]:
        return {"on_change", "on_select"}
