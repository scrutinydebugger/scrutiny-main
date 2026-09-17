from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.tools.typing import *


class MathBuilderComponent(ScrutinyGUIBaseGlobalComponent):

    def setup(self) -> None:
        pass

    def ready(self) -> None:
        pass

    def teardown(self) -> None:
        pass

    def visibilityChanged(self, visible: bool) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True
