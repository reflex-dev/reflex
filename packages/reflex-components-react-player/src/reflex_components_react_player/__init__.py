"""React Player component for audio and video."""

from . import react_player
from .audio import Audio as Audio
from .video import Video as Video

audio = Audio.create
video = Video.create
