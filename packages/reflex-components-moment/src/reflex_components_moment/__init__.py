"""Moment.js component."""

from .moment import Moment as Moment
from .moment import MomentDelta as MomentDelta
from .moment import MomentProvider as MomentProvider

moment = Moment.create
moment_provider = MomentProvider.create
