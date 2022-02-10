"""Misc methods based on configuration data"""


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
