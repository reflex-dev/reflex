"""React Player component for audio and video."""

from . import react_player
from .audio import Audio
from .video import Video

audio = Audio.create
video = Video.create
