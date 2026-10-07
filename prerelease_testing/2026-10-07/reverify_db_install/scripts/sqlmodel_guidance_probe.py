"""Do the model declarations that sqlmodel>=0.0.45 documents still import under sqlmodel 0.0.44?

Usage: <venv>/bin/python -I sqlmodel_guidance_probe.py <expect_venv_substring>
"""
import sys
import traceback
from importlib.metadata import version

assert sys.argv[1] in sys.executable, sys.executable
print(f"--- sqlmodel {version('sqlmodel')} / pydantic {version('pydantic')} / reflex {version('reflex')}")

CASES = {
    "AwareDatetime field": "from pydantic import AwareDatetime\nfrom sqlmodel import Field, SQLModel\nclass E1(SQLModel, table=True):\n    id: int | None = Field(default=None, primary_key=True)\n    at: AwareDatetime\nprint('   column type:', repr(E1.__table__.c.at.type))",
    "NaiveDatetime field": "from pydantic import NaiveDatetime\nfrom sqlmodel import Field, SQLModel\nclass E2(SQLModel, table=True):\n    id: int | None = Field(default=None, primary_key=True)\n    at: NaiveDatetime\nprint('   column type:', repr(E2.__table__.c.at.type))",
    "from sqlmodel import UTCDateTime": "from sqlmodel import UTCDateTime\nprint('   ok', UTCDateTime)",
    "sa_type=DateTime(timezone=False)": "from datetime import datetime\nfrom sqlalchemy import DateTime\nfrom sqlmodel import Field, SQLModel\nclass E3(SQLModel, table=True):\n    id: int | None = Field(default=None, primary_key=True)\n    at: datetime = Field(sa_type=DateTime(timezone=False))\nprint('   column type:', repr(E3.__table__.c.at.type))",
}
for name, src in CASES.items():
    try:
        exec(compile(src, name, "exec"), {})
        print(f"OK    {name}")
    except Exception as e:  # noqa: BLE001
        print(f"FAIL  {name}: {type(e).__name__}: {str(e).splitlines()[0][:160]}")
