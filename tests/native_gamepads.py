"""Exercise real SDL controller acquisition with two simulated virtual devices.

This checks the native adapter, not physical-controller compatibility. Run alone
on macOS with a desktop session; ordinary pytest uses deterministic input tests.
"""

import ctypes
import json
from pathlib import Path

import pygame
from pygame._sdl2 import controller

from plocks import Canvas, Event, GamepadButton, GamepadLayout, GamepadPress, Sprite, Stage


def main() -> None:
    sdl = ctypes.CDLL(pygame.base.__file__)
    sdl.SDL_InitSubSystem.argtypes = [ctypes.c_uint32]
    sdl.SDL_InitSubSystem.restype = ctypes.c_int
    sdl.SDL_QuitSubSystem.argtypes = [ctypes.c_uint32]
    sdl.SDL_JoystickAttachVirtual.argtypes = [ctypes.c_int] * 4
    sdl.SDL_JoystickAttachVirtual.restype = ctypes.c_int
    sdl.SDL_JoystickOpen.argtypes = [ctypes.c_int]
    sdl.SDL_JoystickOpen.restype = ctypes.c_void_p
    sdl.SDL_JoystickClose.argtypes = [ctypes.c_void_p]
    sdl.SDL_JoystickSetVirtualButton.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint8]
    sdl.SDL_JoystickDetachVirtual.argtypes = [ctypes.c_int]
    sdl.SDL_JoystickInstanceID.argtypes = [ctypes.c_void_p]
    sdl.SDL_JoystickInstanceID.restype = ctypes.c_int
    sdl.SDL_GameControllerFromInstanceID.argtypes = [ctypes.c_int]
    sdl.SDL_GameControllerFromInstanceID.restype = ctypes.c_void_p
    pygame.display.init()
    assert sdl.SDL_InitSubSystem(0x200) == 0
    assert pygame.joystick.get_count() == 0, (
        "Disconnect physical devices for this deterministic proof"
    )
    handles: list[int] = []
    try:
        for index in range(2):
            assert sdl.SDL_JoystickAttachVirtual(1, 6, 15, 0) == index
            handles.append(sdl.SDL_JoystickOpen(index))
        stage = Stage(gamepad_count=2)
        one, two = stage.gamepads
        two.layout = GamepadLayout.NINTENDO
        hero = Sprite(Path(__file__).parent / "fixtures/games/integrations_proof/assets/hero.png")
        stage.add(hero)
        presses: list[int] = []
        turbo: list[float] = []
        identity: list[object] = []

        @stage.on_button_down(GamepadButton.A)
        def pressed(event: Event[Stage, GamepadPress]) -> None:
            presses.append(event.data.gamepad.index)

        @hero.on_button_down(GamepadButton.B, gamepad=one, repeat=0.05)
        def repeated(event: Event[Sprite, GamepadPress]) -> None:
            turbo.append(stage.time)

        frame = 0

        @stage.on_draw
        def exercise(canvas: Canvas) -> None:
            nonlocal frame
            frame += 1
            if frame == 2:
                assert one.connected and two.connected
                identity.append(two._device)
                # SDL queues both edges; final polling sees the button released.
                assert sdl.SDL_JoystickSetVirtualButton(handles[0], 0, 1) == 0
                pygame.event.pump()
                assert sdl.SDL_JoystickSetVirtualButton(handles[0], 0, 0) == 0
                pygame.event.pump()
            if frame == 5:
                assert presses == [0], presses
                assert sdl.SDL_JoystickSetVirtualButton(handles[1], 1, 1) == 0
                assert sdl.SDL_JoystickSetVirtualButton(handles[0], 1, 1) == 0
            if frame == 18:
                assert presses == [0, 1] and len(turbo) >= 3, (presses, turbo)
                sdl.SDL_JoystickSetVirtualButton(handles[1], 1, 0)
                sdl.SDL_JoystickSetVirtualButton(handles[0], 1, 0)
                sdl.SDL_JoystickClose(handles[0])
                handles[0] = 0
                assert sdl.SDL_JoystickDetachVirtual(0) == 0
            if frame == 22:
                assert not one.connected and two._device is identity[0] and two.connected
                assert sdl.SDL_JoystickAttachVirtual(1, 6, 15, 0) == 1
                handles[0] = sdl.SDL_JoystickOpen(1)
            if frame == 26:
                assert one.connected and two._device is identity[0]
                sdl.SDL_JoystickSetVirtualButton(handles[1], 1, 1)
                sdl.SDL_JoystickSetVirtualButton(handles[0], 0, 1)
            if frame == 32:
                assert presses[:2] == [0, 1] and sorted(presses[2:]) == [0, 1], presses
                print(
                    "NATIVE_VIRTUAL_CONTROLLERS_OK",
                    json.dumps(
                        {
                            "driver": pygame.display.get_driver(),
                            "presses": presses,
                            "turbo": turbo,
                            "hotplug": True,
                        }
                    ),
                    flush=True,
                )
                stage.stop()
            if frame > 90:
                raise AssertionError("Native controller proof timed out")

        stage.run()
        assert stage._target is None and not stage._actions and not stage._gamepad_handlers
        assert all(p._device is None and not p._buttons for p in stage.gamepads)
        assert not controller.get_init()
        # The external test joysticks remain open, so check actual controller
        # handles as well as the Python module flag after stage-owned shutdown.
        assert all(
            sdl.SDL_GameControllerFromInstanceID(sdl.SDL_JoystickInstanceID(handle)) is None
            for handle in handles
            if handle
        )
        print("NATIVE_VIRTUAL_CLEANUP_OK", flush=True)
    finally:
        if controller.get_init():
            controller.quit()
        for handle in handles:
            if handle:
                sdl.SDL_JoystickClose(handle)
        for index in range(pygame.joystick.get_count() - 1, -1, -1):
            sdl.SDL_JoystickDetachVirtual(index)
        sdl.SDL_QuitSubSystem(0x200)
        pygame.display.quit()


if __name__ == "__main__":
    main()
