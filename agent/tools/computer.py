import asyncio
import base64
import os
import shlex
import shutil
from enum import StrEnum
from pathlib import Path
from typing import Literal, TypedDict
from uuid import uuid4

from anthropic.types.beta import BetaToolComputerUse20251124Param

from .base import BaseAnthropicTool, ToolError, ToolResult
from .run import run

OUTPUT_DIR = "/tmp/outputs"

TYPING_DELAY_MS = 12
TYPING_GROUP_SIZE = 50

Action = Literal[
    "key",
    "hold_key",
    "type",
    "cursor_position",
    "mouse_move",
    "left_mouse_down",
    "left_mouse_up",
    "left_click",
    "left_click_drag",
    "right_click",
    "middle_click",
    "double_click",
    "triple_click",
    "scroll",
    "wait",
    "screenshot",
]

ScrollDirection = Literal["up", "down", "left", "right"]

CLICK_BUTTONS: dict[str, str] = {
    "left_click": "1",
    "middle_click": "2",
    "right_click": "3",
}

SCROLL_BUTTONS: dict[str, str] = {
    "up": "4",
    "down": "5",
    "left": "6",
    "right": "7",
}


class Resolution(TypedDict):
    width: int
    height: int


# sizes above XGA/WXGA are not recommended (see README.md)
# scale down to one of these targets if ComputerTool._scaling_enabled is set
MAX_SCALING_TARGETS: dict[str, Resolution] = {
    "XGA": Resolution(width=1024, height=768),  # 4:3
    "WXGA": Resolution(width=1280, height=800),  # 16:10
    "FWXGA": Resolution(width=1366, height=768),  # ~16:9
}


class ScalingSource(StrEnum):
    COMPUTER = "computer"
    API = "api"


class ComputerToolOptions(TypedDict):
    display_height_px: int
    display_width_px: int
    display_number: int | None


def chunks(s: str, chunk_size: int) -> list[str]:
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]


class ComputerTool(BaseAnthropicTool):
    """
    A tool that allows the agent to interact with the screen, keyboard, and mouse of the current computer.
    The tool parameters are defined by Anthropic and are not editable.
    """

    name: Literal["computer"] = "computer"
    api_type: Literal["computer_20251124"] = "computer_20251124"
    width: int
    height: int
    display_num: int | None

    _screenshot_delay = 2.0
    _scaling_enabled = True

    @property
    def options(self) -> ComputerToolOptions:
        width, height = self.scale_coordinates(
            ScalingSource.COMPUTER, self.width, self.height
        )
        return {
            "display_width_px": width,
            "display_height_px": height,
            "display_number": self.display_num,
        }

    def to_params(self) -> BetaToolComputerUse20251124Param:
        return {"name": self.name, "type": self.api_type, **self.options}

    def __init__(self):
        super().__init__()

        self.width = int(os.getenv("WIDTH") or 0)
        self.height = int(os.getenv("HEIGHT") or 0)
        assert self.width and self.height, "WIDTH, HEIGHT must be set"
        if (display_num := os.getenv("DISPLAY_NUM")) is not None:
            self.display_num = int(display_num)
            self._display_prefix = f"DISPLAY=:{self.display_num} "
        else:
            self.display_num = None
            self._display_prefix = ""

        self.xdotool = f"{self._display_prefix}xdotool"

    async def __call__(
        self,
        *,
        action: Action,
        text: str | None = None,
        coordinate: tuple[int, int] | None = None,
        scroll_direction: ScrollDirection | None = None,
        scroll_amount: int | None = None,
        duration: int | float | None = None,
        **kwargs,
    ):
        if action == "mouse_move":
            if coordinate is None:
                raise ToolError(f"coordinate is required for {action}")
            if text is not None:
                raise ToolError(f"text is not accepted for {action}")
            x, y = self._validate_and_get_coordinates(coordinate)
            return await self.shell(f"{self.xdotool} mousemove --sync {x} {y}")

        if action == "left_click_drag":
            if coordinate is None:
                raise ToolError(f"coordinate is required for {action}")
            start_coordinate = kwargs.get("start_coordinate")
            x, y = self._validate_and_get_coordinates(coordinate)
            move_cmd = ""
            if start_coordinate is not None:
                sx, sy = self._validate_and_get_coordinates(start_coordinate)
                move_cmd = f"mousemove --sync {sx} {sy} "
            return await self.shell(
                f"{self.xdotool} {move_cmd}mousedown 1 mousemove --sync {x} {y} mouseup 1"
            )

        if action in ("left_mouse_down", "left_mouse_up"):
            if text is not None:
                raise ToolError(f"text is not accepted for {action}")
            move_cmd = ""
            if coordinate is not None:
                x, y = self._validate_and_get_coordinates(coordinate)
                move_cmd = f"mousemove --sync {x} {y} "
            verb = "mousedown" if action == "left_mouse_down" else "mouseup"
            return await self.shell(f"{self.xdotool} {move_cmd}{verb} 1")

        if action in ("key", "hold_key"):
            if text is None:
                raise ToolError(f"text is required for {action}")
            if coordinate is not None:
                raise ToolError(f"coordinate is not accepted for {action}")
            if not isinstance(text, str):
                raise ToolError(output=f"{text} must be a string")

            if action == "key":
                return await self.shell(f"{self.xdotool} key -- {text}")
            else:
                hold_seconds = float(duration) if duration is not None else 1.0
                return await self.shell(
                    f"{self.xdotool} keydown -- {text} sleep {hold_seconds} keyup -- {text}"
                )

        if action == "type":
            if text is None:
                raise ToolError(f"text is required for {action}")
            if coordinate is not None:
                raise ToolError(f"coordinate is not accepted for {action}")
            if not isinstance(text, str):
                raise ToolError(output=f"{text} must be a string")

            results: list[ToolResult] = []
            for chunk in chunks(text, TYPING_GROUP_SIZE):
                cmd = f"{self.xdotool} type --delay {TYPING_DELAY_MS} -- {shlex.quote(chunk)}"
                results.append(await self.shell(cmd, take_screenshot=False))
            screenshot_base64 = (await self.screenshot()).base64_image
            return ToolResult(
                output="".join(result.output or "" for result in results),
                error="".join(result.error or "" for result in results),
                base64_image=screenshot_base64,
            )

        if action == "scroll":
            if scroll_direction is None or scroll_direction not in SCROLL_BUTTONS:
                raise ToolError(
                    f"scroll_direction must be one of {list(SCROLL_BUTTONS)}"
                )
            if not isinstance(scroll_amount, int) or scroll_amount < 0:
                raise ToolError("scroll_amount must be a non-negative int")

            move_cmd = ""
            if coordinate is not None:
                x, y = self._validate_and_get_coordinates(coordinate)
                move_cmd = f"mousemove --sync {x} {y} "

            modifier = f"keydown -- {text} " if text else ""
            unmodifier = f" keyup -- {text}" if text else ""
            button = SCROLL_BUTTONS[scroll_direction]
            return await self.shell(
                f"{self.xdotool} {modifier}{move_cmd}click --repeat {scroll_amount} {button}{unmodifier}"
            )

        if action == "wait":
            wait_seconds = float(duration) if duration is not None else 1.0
            await asyncio.sleep(wait_seconds)
            return await self.screenshot()

        if action in (
            "left_click",
            "right_click",
            "double_click",
            "triple_click",
            "middle_click",
            "screenshot",
            "cursor_position",
        ):
            if action == "screenshot":
                if text is not None or coordinate is not None:
                    raise ToolError(f"text/coordinate is not accepted for {action}")
                return await self.screenshot()
            elif action == "cursor_position":
                if text is not None or coordinate is not None:
                    raise ToolError(f"text/coordinate is not accepted for {action}")
                result = await self.shell(
                    f"{self.xdotool} getmouselocation --shell",
                    take_screenshot=False,
                )
                output = result.output or ""
                x, y = self.scale_coordinates(
                    ScalingSource.COMPUTER,
                    int(output.split("X=")[1].split("\n")[0]),
                    int(output.split("Y=")[1].split("\n")[0]),
                )
                return result.replace(output=f"X={x},Y={y}")
            else:
                move_cmd = ""
                if coordinate is not None:
                    x, y = self._validate_and_get_coordinates(coordinate)
                    move_cmd = f"mousemove --sync {x} {y} "
                modifier = f"keydown -- {text} " if text else ""
                unmodifier = f" keyup -- {text}" if text else ""
                repeat = {"double_click": 2, "triple_click": 3}.get(action, 1)
                button = CLICK_BUTTONS[
                    action if action in CLICK_BUTTONS else "left_click"
                ]
                return await self.shell(
                    f"{self.xdotool} {modifier}{move_cmd}click --repeat {repeat} --delay 100 {button}{unmodifier}"
                )

        raise ToolError(f"Invalid action: {action}")

    def _validate_and_get_coordinates(self, coordinate: tuple[int, int] | None):
        if not isinstance(coordinate, list) or len(coordinate) != 2:
            raise ToolError(f"{coordinate} must be a tuple of length 2")
        if not all(isinstance(i, int) and i >= 0 for i in coordinate):
            raise ToolError(f"{coordinate} must be a tuple of non-negative ints")
        return self.scale_coordinates(ScalingSource.API, coordinate[0], coordinate[1])

    async def screenshot(self):
        """Take a screenshot of the current screen and return the base64 encoded image."""
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"screenshot_{uuid4().hex}.png"

        # Try gnome-screenshot first
        if shutil.which("gnome-screenshot"):
            screenshot_cmd = f"{self._display_prefix}gnome-screenshot -f {path} -p"
        else:
            # Fall back to scrot if gnome-screenshot isn't available
            screenshot_cmd = f"{self._display_prefix}scrot -p {path}"

        result = await self.shell(screenshot_cmd, take_screenshot=False)
        if self._scaling_enabled:
            x, y = self.scale_coordinates(
                ScalingSource.COMPUTER, self.width, self.height
            )
            await self.shell(
                f"convert {path} -resize {x}x{y}! {path}", take_screenshot=False
            )

        if path.exists():
            return result.replace(
                base64_image=base64.b64encode(path.read_bytes()).decode()
            )
        raise ToolError(f"Failed to take screenshot: {result.error}")

    async def shell(self, command: str, take_screenshot=True) -> ToolResult:
        """Run a shell command and return the output, error, and optionally a screenshot."""
        _, stdout, stderr = await run(command)
        base64_image = None

        if take_screenshot:
            # delay to let things settle before taking a screenshot
            await asyncio.sleep(self._screenshot_delay)
            base64_image = (await self.screenshot()).base64_image

        return ToolResult(output=stdout, error=stderr, base64_image=base64_image)

    def scale_coordinates(self, source: ScalingSource, x: int, y: int):
        """Scale coordinates to a target maximum resolution."""
        if not self._scaling_enabled:
            return x, y
        ratio = self.width / self.height
        target_dimension = None
        for dimension in MAX_SCALING_TARGETS.values():
            # allow some error in the aspect ratio - not ratios are exactly 16:9
            if abs(dimension["width"] / dimension["height"] - ratio) < 0.02:
                if dimension["width"] < self.width:
                    target_dimension = dimension
                break
        if target_dimension is None:
            return x, y
        # should be less than 1
        x_scaling_factor = target_dimension["width"] / self.width
        y_scaling_factor = target_dimension["height"] / self.height
        if source == ScalingSource.API:
            if x > self.width or y > self.height:
                raise ToolError(f"Coordinates {x}, {y} are out of bounds")
            # scale up
            return round(x / x_scaling_factor), round(y / y_scaling_factor)
        # scale down
        return round(x * x_scaling_factor), round(y * y_scaling_factor)
