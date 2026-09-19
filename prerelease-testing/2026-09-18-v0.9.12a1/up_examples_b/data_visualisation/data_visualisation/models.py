from sqlmodel import Field, SQLModel


class Customer(SQLModel, table=True):
    """The customer model."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str
    phone: str
    address: str


class Cereals(SQLModel, table=True):
    """The cereal model."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    mfr: str
    type: str
    calories: str
    protein: str
    fat: str
    sodium: str
    fiber: str
    carbo: str
    sugars: str
    potass: str
    vitamins: str
    shelf: str
    weight: str
    cups: str
    rating: str


class Covid(SQLModel, table=True):
    """The covid model."""

    id: int | None = Field(default=None, primary_key=True)
    state: str
    zone: str
    total_cases: str
    active: str
    discharged: str
    deaths: str
    active_ratio: str
    discharge_ratio: str
    discharge_avg: str
    death_ratio: str
    death_avg: str
    population: str


class Countries(SQLModel, table=True):
    """The countries model."""

    id: int | None = Field(default=None, primary_key=True)
    place: str
    pop1980: str
    pop2000: str
    pop2010: str
    pop2022: str
    pop2023: str
    pop2030: str
    pop2050: str
    country: str
    area: str
    landAreaKm: str
    cca2: str
    cca3: str
    netChange: str
    growthRate: str
    worldPercentage: str
    density: str
    densityMi: str
    rank: str
