#!/usr/bin/env python3.6

import logging
from pprint import pprint
from shutil import get_terminal_size
import signal
import sys
from time import sleep
from typing import List, Dict, Tuple

import colorama
# import readline

logging.basicConfig(
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO)

_LOGGER = logging.getLogger("")

from tmuxcmd import TmuxFmtCmd, tmux_attach

_MASTER_SESSION_NAME = 'master'

from tmuxcmd import TmuxCmd

config = {
    'minnamelen': 15,
    'n_cols': 5,
    'fmt_overhead': 6,
}

def handle_winch(signum, frame):
    do_table_loop()

def main():
    colorama.init()

    signal.signal(signal.SIGWINCH, handle_winch)
    do_table_loop()

def do_table_loop():
    display_error_message = ""

    while True:
        # Redraw screen and move cursor to top
        print(chr(27) + '[2J' + chr(27) + '[H', end='', flush=True)

        sessions = tmux_list_sessions()

        draw_table(sessions)

        if display_error_message:
            print(colorama.Fore.RED + "Error: " + colorama.Fore.RESET +
                  display_error_message)
            display_error_message = ""
        else:
            print()

        sessions_prompt = f'0-{len(sessions) -1}]' if sessions else ""
        prompt = f'Attach [cqu? {sessions_prompt}]: '
        command = input(prompt)

        _LOGGER.warning(f'cmd: {command}')

        help_dict = {
            "q": "Quit",
            "c": "Create session (: c sess_name)",
            "u": "Update screen",
        }

        if command.isdecimal():
            # We know we have an index number. Find the session and attach it
            session_idx = int(command)

            try:
                session_to_attach = sessions[session_idx]['session_id']
            except IndexError:
                display_error_message = "Invalid index"
                continue

            tmux_attach(session_to_attach)

        else:
            if command == "q":
                break
            elif command.startswith("c"):
                session_name = command[2:]

                try:
                    cmd = TmuxCmd(["new-session", "-s", session_name, "-d"])
                except RuntimeError as e:
                    if 'bad session name' in str(e):
                        display_error_message = "Invalid tmux session name"
                        continue
                    else:
                        raise

            elif command == "u":
                continue

            else:
                display_error_message = f'command "{command}" not recognized'


def _print_err(err: str) -> None:
    print(f'Error: {err}')
    sleep(.3)


def format_session_name(name: str, maxlen: int) -> str:
    """Format the tmux session_name, removing middle chars if it is too long

    Args:
        name: session name
        maxlen: maximum size of string to return

    Returns:
        str: formatted sessions name

    """
    if len(name) <= maxlen:
        return name

    # Our name is too long. Trim some chars in the middle and replace with '*'
    startchars = maxlen // 2
    new_name = name[:startchars] + '*' + name[-(maxlen - startchars - 1):]
    return new_name


def draw_table(sessions: List[Dict[str, str]]) -> None:

    if len(sessions) == 0:
        return

    n_cols, column_width = get_column_width()
    items_per_col = (len(sessions) + n_cols - 1) // n_cols

    session_strings = format_session_strings(column_width, sessions)

    for i in range(items_per_col):
        for j in range(n_cols):

            index = j * items_per_col + i

            # Does this index exist, or have we run out of sessions before filling the last
            # row?
            if index >= len(session_strings):
                break
            print(session_strings[index], end='')

        # print the newline since we're at the end of a row
        print('')


def format_session_strings(column_width: int,
                           sessions: List[Dict[str, str]]) -> List[str]:

    session_strings: List[str] = []

    # How many characters do we need for the index numbers?
    n_sessions = len(sessions)
    if n_sessions > 1000:
        # srsly?
        raise RuntimeError(
            f'you have {n_sessions} sessions, which is too many')
    elif n_sessions > 100:
        idx_len = 3
    elif n_sessions > 10:
        idx_len = 2
    else:
        idx_len = 1

    # Get the max number of chars required to display all session ids
    session_id_len = max(len(x['session_id']) for x in sessions)

    fmt_overhead = config['fmt_overhead']
    fmt_overhead += idx_len + session_id_len

    for i, session in enumerate(sessions):

        session_string = f'{i:>{idx_len}d})'

        # If the session is attached anywhere, we want to put a hash in the list next to the name
        if session['session_attached'] == '1':
            session_string += colorama.Style.BRIGHT + '#' + colorama.Style.RESET_ALL
        else:
            session_string += ' '

        # The name we use in the display may not be the actual session name, but instead may be
        # a shortened version, returned from format_session_name()
        session_fmt_name = format_session_name(session['session_name'],
                                               config['minnamelen'])
        session_string += session_fmt_name

        session_string += ' ' + '-' * (
            column_width - len(session_fmt_name) - fmt_overhead)
        session_string += f'[{session["session_id"]:<{session_id_len}}] '
        session_strings.append(session_string)

    return session_strings


def get_column_width() -> Tuple[int, int]:
    # A relatively dirty hack to figure out how many columns we can display
    terminal_size = get_terminal_size()
    n_cols = config['n_cols'] + 1
    column_width: int = 0

    while column_width < (config['fmt_overhead'] + config['minnamelen'] + 3):
        n_cols -= 1
        column_width = (terminal_size.columns - n_cols + 1) // n_cols
        _LOGGER.debug(f'shrinking n_cols to {n_cols}')

    return n_cols, column_width


def tmux_list_sessions() -> List[Dict[str, str]]:

    try:
        tmux_cmd = TmuxFmtCmd(['list-sessions'],
                              ['session_id', 'session_name', 'session_attached'])
    except RuntimeError as e:
        if 'no server running' in str(e):
            # This is okay. It just means there's no server yet. We return an empty session
            # list
            return []

    return sorted(tmux_cmd.stdout, key=lambda k: k['session_name'])


if __name__ == "__main__":
    main()
