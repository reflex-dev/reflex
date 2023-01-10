import pynecone as pc
from pynecone.var import Var


class DatePicker(pc.Component):
    library = "react-date-picker"
    tag = "DatePicker"
    value: Var[str]

    @classmethod
    def get_controlled_triggers(cls) -> set[str]:
        return {"on_change"}
