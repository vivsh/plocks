"""Use terminal IPython's existing asyncio loop; execution state stays on Stage."""

from __future__ import annotations

import asyncio
import atexit
import traceback
from collections.abc import Callable
from threading import current_thread, main_thread
from typing import TYPE_CHECKING, cast

from ._runtime import _acquire, _check_start, close, drive
from .errors import StageError

if TYPE_CHECKING:
    from .stage import Stage


def _start(stage: Stage) -> None:
    """Validate the shell before opening a window, then admit one observed driver task."""
    _check_start(stage)
    try:
        from IPython import get_ipython
        from IPython.core.async_helpers import get_asyncio_loop
        from IPython.terminal.interactiveshell import TerminalInteractiveShell
    except ImportError as error:
        raise StageError(
            'Interactive mode needs IPython 9.x: python -m pip install "ipython>=9,<10"'
        ) from error
    shell = get_ipython()
    if not isinstance(shell, TerminalInteractiveShell) or shell.simple_prompt:
        raise StageError(
            "Use interactive=True in terminal IPython with its full prompt, not a notebook"
        )
    if current_thread() is not main_thread():
        raise StageError("Interactive games must start on the main thread")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise StageError(
            "Call run(interactive=True) from a normal IPython command, outside async code"
        )
    if shell.active_eventloop not in (None, "asyncio"):
        raise StageError("Another IPython GUI loop is active; use %gui to disable it first")
    shell.enable_gui("asyncio")
    loop = cast(Callable[[], asyncio.AbstractEventLoop], get_asyncio_loop)()
    _acquire(stage)

    def completed(task: asyncio.Task[None]) -> None:
        error = None if task.cancelled() else task.exception()
        try:
            # A task canceled before its first turn never enters drive()'s finally.
            if stage._task is task:
                close(stage)
        except BaseException as cleanup:  # noqa: BLE001 -- observe every cleanup failure
            if error is None:
                error = cleanup
            else:
                error.add_note(f"Cleanup also failed: {cleanup!r}")
        if error is not None:
            try:
                shell.showtraceback((type(error), error, error.__traceback__))
            except Exception:  # noqa: BLE001 -- preserve the game error if IPython formatting fails
                traceback.print_exception(error)

    coroutine = drive(stage)
    try:
        stage._task = loop.create_task(coroutine, name="Plocks")
        stage._task.add_done_callback(completed)
        atexit.register(stage.stop)
    except BaseException:
        if stage._task is None:
            coroutine.close()
            close(stage)
        else:
            _stop(stage)
        raise


def _stop(stage: Stage) -> None:
    """Close promptly from the prompt; let an executing driver reach its safe boundary."""
    task = stage._task
    if task is None or task is asyncio.current_task(loop=task.get_loop()):
        return
    loop = task.get_loop()
    try:
        close(stage)
    finally:
        if not loop.is_running() and not loop.is_closed():
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                try:
                    loop.run_until_complete(task)
                except asyncio.CancelledError:
                    pass
