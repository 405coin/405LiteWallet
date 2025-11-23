                                                             
                                                                         
                                              

                                                                                             

from typing import TYPE_CHECKING, Mapping, Optional

if TYPE_CHECKING:
    from . import qt
    from electrum.simple_config import SimpleConfig
    from electrum.daemon import Daemon
    from electrum.plugin import Plugins


class BaseElectrumGui:
    def __init__(self, *, config: 'SimpleConfig', daemon: 'Daemon', plugins: 'Plugins'):
        self.config = config
        self.daemon = daemon
        self.plugins = plugins

    def main(self) -> None:
        raise NotImplementedError()

    def stop(self) -> None:
        """Stops the GUI.
        This method must be thread-safe.
        """
        pass

    @classmethod
    def version_info(cls) -> Mapping[str, Optional[str]]:
        return {}
