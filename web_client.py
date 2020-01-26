#!/usr/bin/python3
# Copyright © 2020 Randy Barlow
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""A simple websocket client that listens on a given topic."""

import _thread as thread
import sys
import time

import websocket


if len(sys.argv) != 2:
    print("Usage: web_client.py <topic>")
    sys.exit(1)


def on_message(ws, message):
    print(message)


def on_error(ws, error):
    print(f"ERROR: {error}")


def on_close(ws):
    ws.close()


def on_open(ws):
    def run(*args):
        ws.send(f"{sys.argv[1]}")
    thread.start_new_thread(run, ())


ws = websocket.WebSocketApp(
    "ws://localhost:5000/ws",
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)
ws.on_open = on_open
ws.run_forever()
