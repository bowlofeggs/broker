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
"""Define the locust test parameters."""

import random

from locust import HttpLocust, TaskSet, between


def publish(l):
    """Publish a random message on a random topic."""
    l.client.post(f"/{random.randint(0, 1)}", f"{random.randint(0, 1024)}")


def receive(l):
    """Retrieve a message from a random topic and random queue."""
    l.client.get(f"/{random.randint(0, 1)}/{random.randint(0, 1)}")


class UserBehavior(TaskSet):
    """Define the behavior of a user."""

    tasks = {
        publish: 1,
        receive: 1,
    }


class User(HttpLocust):
    """Define a user."""

    task_set = UserBehavior
    wait_time = lambda x: 0
