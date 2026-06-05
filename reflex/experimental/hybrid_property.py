"""hybrid_property decorator which functions like a normal python property but additionally allows (class-level) access from the frontend. You can use the same code for frontend and backend, or implement 2 different methods."""

from reflex_base.vars.hybrid_property import HybridProperty as HybridProperty
from reflex_base.vars.hybrid_property import hybrid_property as hybrid_property
