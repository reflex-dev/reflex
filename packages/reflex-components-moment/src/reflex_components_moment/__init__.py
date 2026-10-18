"""Moment.js component."""

from .moment import Moment, MomentProvider
from .moment import MomentDelta as MomentDelta

moment = Moment.create
moment_provider = MomentProvider.create
