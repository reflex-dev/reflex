"""Radix components."""
from .avatar import *
from .separator import *
from .slider import *
from .tooltip import *

separator = Separator.create

slider_root = SliderRoot.create
slider_track = SliderTrack.create
slider_range = SliderRange.create
slider_thumb = SliderThumb.create

avatar_root = AvatarRoot.create
avatar_image = AvatarImage.create
avatar_fallback = AvatarFallback.create

tooltip_provider = TooltipProvider.create
tooltip_root = TooltipRoot.create
tooltip_trigger = TooltipTrigger.create
tooltip_content = TooltipContent.create
tooltip_portal = TooltipPortal.create
tooltip_arrow = TooltipArrow.create
