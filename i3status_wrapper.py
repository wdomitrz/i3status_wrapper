#!/usr/bin/env python3
################################################################
# Copyright (c) 2021 Witalis Domitrz <witekdomitrz@gmail.com>
# AGPL License
################################################################
#
# pyright: reportAny = false
# pyright: reportDeprecated = false
# pyright: reportMissingParameterType = false
# pyright: reportMissingTypeArgument = false
# pyright: reportUnknownArgumentType = false
# pyright: reportUnknownMemberType = false
# pyright: reportUnknownParameterType = false
# pyright: reportUnknownVariableType = false
# pyright: reportUnnecessaryIsInstance = false
# pyright: reportUnreachable = false
# pyright: reportUnusedCallResult = false
# pyright: reportUnusedParameter = false
#
# ruff: noqa: SIM905
#
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typing-extensions>=4.1; python_version < '3.11'",
# ]
# ///

from __future__ import annotations

import argparse
import contextlib
import functools
import itertools
import json
import multiprocessing
import operator
import select
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Protocol, TypeAlias

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

StatusBlock: TypeAlias = dict[str, object]


class ReadSource(Protocol):
    def fileno(self) -> int: ...

    def readline(self) -> str: ...


# Helper functions
def run_command_background(cmd: str | Sequence[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_command_blocking(
    cmd: str | Sequence[str],
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False
    )


REFRESH_STATUS_CMD: Sequence[str] = "killall -SIGUSR1 i3status".split()


# Click handling
def run_command_on_click(
    cmd: str | Sequence[str],
    *,
    accepted_button: int = 1,
    refresh: bool = False,
) -> Callable[..., None]:
    def helper(button: int, **_: object) -> None:
        if button != accepted_button:
            return
        if not refresh:
            run_command_background(cmd)
        else:
            run_command_blocking(cmd)
            run_command_background(REFRESH_STATUS_CMD)

    return helper


def handle_volume(*, button: int, modifiers: list[str], **_: object) -> None:
    if button == 3:  # noqa: PLR2004
        run_command_background("pavucontrol")
        return
    volume_mult = 1 if "Control" not in modifiers else 5
    if button in [1, 2]:
        cmd = "pactl set-sink-mute @DEFAULT_SINK@ toggle".split()
    elif button in [4, 7]:
        cmd = f"pactl set-sink-volume @DEFAULT_SINK@ +{volume_mult}%".split()
    elif button in [5, 6]:
        cmd = f"pactl set-sink-volume @DEFAULT_SINK@ -{volume_mult}%".split()
    else:
        return
    run_command_blocking(cmd)
    run_command_background(REFRESH_STATUS_CMD)


def handle_mic(*, button: int, modifiers: list[str], **_: object) -> None:
    del modifiers
    if button in [1, 2]:
        cmd = "pactl set-source-mute @DEFAULT_SOURCE@ toggle".split()
    else:
        return
    run_command_blocking(cmd)
    run_command_background(REFRESH_STATUS_CMD)


def handle_sound(*, instance: str, **data: object) -> None:
    button = data.get("button")
    modifiers = data.get("modifiers")
    if not isinstance(button, int) or not isinstance(modifiers, list):
        return None

    if not all(isinstance(modifier, str) for modifier in modifiers):
        return None

    if instance.startswith("default"):
        return handle_volume(instance=instance, button=button, modifiers=modifiers)
    elif "Capture" in instance:
        return handle_mic(instance=instance, button=button, modifiers=modifiers)
    else:
        return None


@dataclass(kw_only=True, frozen=True)
class Block:
    name: str
    instance: str | None = None
    full_text: str | None = None
    color: str | None = None
    on_click: Callable[..., None] | None = None


ALL_BLOCKS: dict[tuple[str, str] | str, Block] = {
    ((block.name, block.instance) if block.instance is not None else block.name): block
    for block in []
    # Button blocks
    + [
        Block(
            name="close",
            full_text="❌",
            on_click=run_command_on_click("i3-msg kill".split()),
        ),
        Block(
            name="editor",
            full_text="✍️",
            on_click=run_command_on_click("code".split()),
        ),
        Block(
            name="menu",
            full_text="🔍",
            on_click=run_command_on_click("run_menu.sh".split()),
        ),
        Block(
            name="terminal",
            full_text="📄",
            on_click=run_command_on_click("i3-sensible-terminal"),
        ),
    ]
    # Multimedia controls
    + [
        Block(
            name="next_track",
            full_text="⏭️",
            on_click=run_command_on_click("playerctl next".split(), refresh=True),
        ),
        Block(
            name="pause",
            full_text="⏸️",
            on_click=run_command_on_click("playerctl pause".split(), refresh=True),
        ),
        Block(
            name="play_pause",
            full_text="⏯️",
            on_click=run_command_on_click("playerctl play-pause".split(), refresh=True),
        ),
        Block(
            name="play",
            full_text="▶️",
            on_click=run_command_on_click("playerctl play".split(), refresh=True),
        ),
        Block(
            name="previous_track",
            full_text="⏮️",
            on_click=run_command_on_click("playerctl previous".split(), refresh=True),
        ),
        Block(
            name="stop",
            full_text="⏹️",
            on_click=run_command_on_click("playerctl stop".split(), refresh=True),
        ),
    ]
    # Click events, without full_text
    + [
        Block(
            name="battery",
            on_click=run_command_on_click("xfce4-power-manager-settings"),
        ),
        Block(
            name="cpu_temperature", on_click=run_command_on_click("xfce4-taskmanager")
        ),
        Block(name="disk_info", on_click=run_command_on_click("nautilus")),
        Block(name="ethernet", on_click=run_command_on_click("nm-connection-editor")),
        Block(name="ipv6", on_click=run_command_on_click("nm-connection-editor")),
        Block(name="load", on_click=run_command_on_click("xfce4-taskmanager")),
        Block(
            name="time",
            on_click=run_command_on_click(
                "xdg-open https://calendar.google.com/".split()
            ),
        ),
        Block(
            name="tztime",
            on_click=run_command_on_click(
                "xdg-open https://calendar.google.com/".split()
            ),
        ),
        Block(name="wireless", on_click=run_command_on_click("nm-connection-editor")),
        Block(
            name="media_info",
            on_click=run_command_on_click("playerctl play-pause".split(), refresh=True),
        ),
        Block(name="volume", on_click=handle_sound),
    ]
}


# Custom block groups
def media_block() -> Block:
    try:
        playerctl_title_process = run_command_blocking(
            "playerctl metadata title".split()
        )
        playerctl_status_process = run_command_blocking("playerctl status".split())
    except (FileNotFoundError, OSError):
        return replace(ALL_BLOCKS["media_info"], full_text="")

    if (
        playerctl_title_process.returncode != 0
        or playerctl_status_process.returncode != 0
    ):
        return replace(ALL_BLOCKS["media_info"], full_text="")

    title = playerctl_title_process.stdout.decode().strip()
    status = playerctl_status_process.stdout.decode().strip()
    control_icon = "⏸️" if status == "Playing" else "▶️"

    return replace(
        ALL_BLOCKS["media_info"],
        full_text=f"{title} {control_icon}",
        color="#BBFFBB" if status == "Playing" else "#BBBBFF",
    )


def add_no_internet_info(old_blocks: list[StatusBlock]) -> list[StatusBlock]:
    def is_internet_block(block: StatusBlock) -> bool:
        return block.get("name") in ["ipv6", "wireless", "ethernet"]

    internet_blocks = list(filter(is_internet_block, old_blocks))

    if len(internet_blocks) == 0:
        return old_blocks

    if any(x.get("full_text") is not None for x in internet_blocks):
        return old_blocks

    for i, old_block in enumerate(old_blocks):
        if is_internet_block(old_block):
            old_blocks[i]["full_text"] = "⛔"
            break

    return old_blocks


# Config
BLOCKS_TO_ADD = ["terminal", "menu", "close"]


def process_blocks(old_blocks: list[StatusBlock]) -> list[StatusBlock]:
    return (
        [asdict(media_block())]
        + add_no_internet_info(old_blocks)
        + [asdict(ALL_BLOCKS[name]) for name in BLOCKS_TO_ADD]
    )


# Execution
HEADER = {"version": 1, "click_events": True}
I3STATUS_COMMANDS = ["i3status"]


def combine_read_sources(
    read_sources: Sequence[ReadSource],
) -> Iterator[tuple[int, str]]:
    while True:
        ready_reads, _, _ = select.select(read_sources, [], [])
        for ready_read in ready_reads:
            yield ready_read.fileno(), ready_read.readline()


def process_i3status_output(i3status_output: str) -> None | list[StatusBlock]:
    i3status_output_str: str = i3status_output.strip().strip(",")

    try:
        result: list[StatusBlock] = json.loads(i3status_output_str)
    except json.decoder.JSONDecodeError:
        return None

    if not isinstance(result, list):
        return None
    return result


def combine_i3status_outputs(
    i3status_outputs: Sequence[ReadSource],
) -> Iterator[list[StatusBlock]]:
    fileno_order: list[int] = [output.fileno() for output in i3status_outputs]

    last_remembered_lists: dict[int, list[StatusBlock]] = {
        fileno: [] for fileno in fileno_order
    }
    for fileno, output in combine_read_sources(i3status_outputs):
        result = process_i3status_output(output)
        if result is None:
            continue
        last_remembered_lists[fileno] = result

        yield functools.reduce(
            operator.iadd,
            [last_remembered_lists[fileno] for fileno in fileno_order],
            [],
        )


def show_status_text() -> None:
    print(json.dumps(HEADER, separators=(",", ":")), flush=True)
    print("[", flush=True)

    with contextlib.ExitStack() as stack:
        i3status_processes = [
            stack.enter_context(
                subprocess.Popen(i3status_command, stdout=subprocess.PIPE, text=True)
            )
            for i3status_command in I3STATUS_COMMANDS
        ]
        i3status_outputs: list[ReadSource] = []
        for i3status_process in i3status_processes:
            if i3status_process.stdout is None:
                raise RuntimeError("i3status process stdout was not captured")
            i3status_outputs.append(i3status_process.stdout)

        for unprocessed_data in combine_i3status_outputs(i3status_outputs):
            data = process_blocks(unprocessed_data)
            print(
                json.dumps(data, separators=(",", ":"), default=lambda v: str(type(v)))
                + ",",
                flush=True,
            )

    print("]", flush=True)


# Click handing
def handle_click(line: str) -> None:
    data = json.loads(line.strip().strip(","))

    block: Block | None = ALL_BLOCKS.get((data.get("name"), data.get("instance")))
    if block is None:
        block = ALL_BLOCKS.get(data.get("name"))

    if block is None or block.on_click is None:
        return

    block.on_click(**data)


def clicks_handler() -> None:
    for line in itertools.islice(sys.stdin, 1, None):
        multiprocessing.Process(target=handle_click, args=[line]).start()


@dataclass(kw_only=True, frozen=True)
class Args:
    @classmethod
    def from_args(cls, argv: list[str] | None = None) -> Self:
        parser = argparse.ArgumentParser()
        _ = parser.parse_args(argv)
        return cls()

    def run(self) -> int:
        process = multiprocessing.Process(target=show_status_text)
        process.start()
        clicks_handler()
        process.join()
        return 0


if __name__ == "__main__":
    raise SystemExit(Args.from_args().run())
