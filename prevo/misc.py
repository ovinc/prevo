"""Misc methods based on configuration data"""

# ----------------------------- License information --------------------------

# This file is part of the prevo python package.
# Copyright (C) 2022 Olivier Vincent

# The prevo package is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# The prevo package is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with the prevo python package.
# If not, see <https://www.gnu.org/licenses/>


# =========================== Dataname management ============================


class NamesMgmt:
    """Manage things related to sensor names from configuration info."""

    def __init__(self, config):
        """Config is a dict that must contain the keys:

        - 'sensors'
        - 'default names'
        """
        self.config = config

    def mode_to_names(self, mode):
        """Determine active names as a function of input mode."""
        if mode is None:
            return self.config['default names']
        names = []
        for name in self.config['sensors']:
            if name in mode:
                names.append(name)
        return names
