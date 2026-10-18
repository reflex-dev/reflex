"""Moment.js component."""

from .moment import Moment, MomentDelta as MomentDelta, MomentProvider

moment = Moment.create
moment_provider = MomentProvider.create
