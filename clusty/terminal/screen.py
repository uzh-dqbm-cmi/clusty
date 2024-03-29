"""
Author: @matteobe
"""

import time
import re
from uuid import uuid4
from typing import List, Tuple, Union
import pexpect

from clusty.terminal.shell import Shell
from clusty.utils.validation import format_input_to_list


class Screen:
    """
    Screen class packages utilities for creating and attaching to screens
    """

    wait_period = 1

    @classmethod
    def create(cls, name: str = None, unique: bool = True, terminal: pexpect.spawn = None) -> str:
        """Create new detached screen and change the name if not unique"""

        terminal_passed_in = (terminal is not None)
        terminal = Shell() if terminal is None else terminal
        name = name if name is not None else str(uuid4().hex)[0:4]

        screen_list = cls.list(name=name, terminal=terminal)
        if unique and len(screen_list):
            name = f"{name}_{str(uuid4().hex[0:4])}"

        terminal.sendline(f"screen -dmS {name}")
        time.sleep(Screen.wait_period)

        if not terminal_passed_in:
            terminal.close(force=True)

        return name

    @staticmethod
    def kill(name: str, terminal: pexpect.spawn = None) -> None:
        """Kill a screen with the given name or identifier"""

        terminal_passed_in = (terminal is not None)
        terminal = Shell() if terminal is None else terminal
        if terminal is None:
            terminal = Shell()

        cmd = f"screen -XS {name} kill"
        terminal.sendline(cmd)
        time.sleep(Screen.wait_period)

        if not terminal_passed_in:
            terminal.close(force=True)

    @classmethod
    def kill_all(cls, name: str = None, exact_name_match: bool = True) -> None:
        """Kill all screens which match the passed-in name exactly or partially (depending on exact_name_match flag)"""

        screen_list = cls.list(name=name, exact_name_match=exact_name_match)
        for screen in screen_list:
            cls.kill(name=screen[0])

    @staticmethod
    def list(name: str = None, exact_name_match: bool = False, terminal: pexpect.spawn = None) \
            -> List[Tuple[str, str, bool]]:
        """Retrieve a list with the screen IDs associated with a given screen name, if None, retrieve all screen IDs"""

        cmd = "screen -ls" if name is None else f"screen -ls {name}"

        if terminal is None:
            terminal = pexpect.spawn(cmd)
            screen_list = terminal.read().decode()
            terminal.close()
        else:
            terminal.sendline(cmd)
            # IMPROVE: Somehow screen -ls doesn't trigger a EOF for matching, and only matches the TIMEOUT. Current
            #  workaround avoids an error, but is not technically correct. The downside of the current method is that
            #  the execution needs to wait for the timeout in order to continue.
            #  The before property stores ALL the shell output, not just the output of the screen.
            terminal.expect_list([pexpect.EOF, pexpect.TIMEOUT], timeout=Screen.wait_period)
            screen_list = terminal.before.decode()

        # IMPROVE: Check why \s+ regex not matching whitespace in the screen -ls name output
        screen_pattern = re.compile(r"([0-9]{3,6})\.(\w+).+(\(Detached\)|\(Attached\))", re.MULTILINE)
        matched_screens = screen_pattern.findall(screen_list)
        matched_screens = list(set(matched_screens))

        # Select the screens to return
        screens = list()
        for screen_id, screen_name, attach_status in matched_screens:
            add_screen = False if exact_name_match and not screen_name == name else True

            if add_screen:
                screen = (screen_id, screen_name, True if attach_status == "(Detached)" else False)
                screens.append(screen)

        return screens

    @staticmethod
    def attach(screen: str, terminal: pexpect.spawn = None) -> pexpect.spawn:
        """Attach to a screen"""

        terminal = Shell() if terminal is None else terminal
        terminal.sendline(f"screen -r {screen}")

        return terminal

    @classmethod
    def attach_nested(cls, screens: Union[str, List[str]], terminal: pexpect.spawn = None) -> pexpect.spawn:
        """Attach to a nested sequence of screens"""

        screens = format_input_to_list(screens)
        for screen in screens:
            terminal = cls.attach(screen, terminal)

        return terminal

    @staticmethod
    def detach(terminal: pexpect.spawn, level: int = 1) -> None:
        """Implements the screen detach procedure for a terminal"""

        terminal.sendcontrol('a')
        # For nested screen, multiple Ctrl-a signals plus a final a keystroke must be send in order to detach correctly
        for _ in range(2, level):
            terminal.sendcontrol('a')
        if level > 1:
            terminal.send('a')
        terminal.sendcontrol('d')
        time.sleep(Screen.wait_period)

    @classmethod
    def detach_nested(cls, terminal: pexpect.spawn, depth: int = 1, terminate: bool = False) -> None:
        """Detach from a nested sequence of screens"""

        level = depth
        while level > 0:
            cls.detach(terminal=terminal, level=level)
            level -= 1

        if terminate:
            terminal.close(force=True)
