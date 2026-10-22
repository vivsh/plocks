"""Small, typed desktop Python games with explicit objects and scripts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._commands import Actor as Actor
from ._scripts import WhenBusy as WhenBusy
from .actions import Action as Action
from .audio import Sound as Sound
from .audio import Voice as Voice
from .callbacks import ActorCallback as ActorCallback
from .callbacks import ActorUpdateCallback as ActorUpdateCallback
from .callbacks import Callback as Callback
from .callbacks import DrawCallback as DrawCallback
from .callbacks import UpdateCallback as UpdateCallback
from .canvas import Canvas as Canvas
from .conditions import Condition as Condition
from .conditions import GamepadDown as GamepadDown
from .conditions import Grounded as Grounded
from .conditions import Not as Not
from .conditions import Touching as Touching
from .connections import Connection as Connection
from .connections import Hinge as Hinge
from .connections import Motor as Motor
from .connections import Rope as Rope
from .connections import Spring as Spring
from .errors import (
    AssetError as AssetError,
)
from .errors import (
    AudioError as AudioError,
)
from .errors import NavigationError as NavigationError
from .errors import NetworkError as NetworkError
from .errors import PhysicsError as PhysicsError
from .errors import (
    PlocksError as PlocksError,
)
from .errors import (
    StageError as StageError,
)
from .events import Click as Click
from .events import Event as Event
from .events import GamepadPress as GamepadPress
from .events import RemoteChange as RemoteChange
from .gamepads import Gamepad as Gamepad
from .gamepads import GamepadButton as GamepadButton
from .gamepads import GamepadInput as GamepadInput
from .gamepads import GamepadLayout as GamepadLayout
from .geometry import Bounds as Bounds
from .geometry import Color as Color
from .geometry import Point as Point
from .image_map import ImageMap as ImageMap
from .imaging import Anchor as Anchor
from .imaging import CostumeSource as CostumeSource
from .imaging import Image as Image
from .imaging import ImageGrid as ImageGrid
from .imaging import ImageSource as ImageSource
from .input import Key as Key
from .input import Mouse as Mouse
from .input import MouseButton as MouseButton
from .messages import Message as Message
from .motion import Ease as Ease
from .motion import RotationStyle as RotationStyle
from .multiplayer import Multiplayer as Multiplayer
from .physics import Body as Body
from .physics import BodyType as BodyType
from .physics import Box as Box
from .physics import Circle as Circle
from .physics import Physics as Physics
from .pixelorama import PixeloramaSheet as PixeloramaSheet
from .puppets import Puppet as Puppet
from .rigging import HumanJoint as HumanJoint
from .rigging import Joint as Joint
from .rigging import Pose as Pose
from .rigging import Skeleton as Skeleton
from .scripts import Script as Script
from .sprites import Sprite as Sprite
from .stage import Stage as Stage
from .theme import AlertLevel as AlertLevel
from .theme import UITheme as UITheme
from .tiled import TiledMap as TiledMap
from .tiling import TiledBackground as TiledBackground
from .tiling import TileMap as TileMap
from .ui import Button as Button
from .ui import Label as Label
from .ui import Panel as Panel
from .ui import ProgressBar as ProgressBar

if TYPE_CHECKING:
    Costume = Image
    SpriteSheet = ImageGrid
else:
    from .imaging import _legacy_asset

    __getattr__ = _legacy_asset


__all__ = (
    "Action",
    "Actor",
    "ActorCallback",
    "ActorUpdateCallback",
    "AlertLevel",
    "Anchor",
    "AssetError",
    "AudioError",
    "Body",
    "BodyType",
    "Bounds",
    "Box",
    "Button",
    "Callback",
    "Canvas",
    "Circle",
    "Click",
    "Color",
    "Condition",
    "Connection",
    "Costume",
    "CostumeSource",
    "DrawCallback",
    "Ease",
    "Event",
    "Gamepad",
    "GamepadButton",
    "GamepadDown",
    "GamepadInput",
    "GamepadLayout",
    "GamepadPress",
    "Grounded",
    "Hinge",
    "HumanJoint",
    "Image",
    "ImageGrid",
    "ImageMap",
    "ImageSource",
    "Joint",
    "Key",
    "Label",
    "Message",
    "Motor",
    "Mouse",
    "MouseButton",
    "Multiplayer",
    "NavigationError",
    "NetworkError",
    "Not",
    "Panel",
    "Physics",
    "PhysicsError",
    "PixeloramaSheet",
    "PlocksError",
    "Point",
    "Pose",
    "ProgressBar",
    "Puppet",
    "RemoteChange",
    "Rope",
    "RotationStyle",
    "Script",
    "Skeleton",
    "Sound",
    "Spring",
    "Sprite",
    "SpriteSheet",
    "Stage",
    "StageError",
    "TileMap",
    "TiledBackground",
    "TiledMap",
    "Touching",
    "UITheme",
    "UpdateCallback",
    "Voice",
    "WhenBusy",
)
