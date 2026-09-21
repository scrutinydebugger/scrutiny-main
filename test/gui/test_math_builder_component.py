from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QModelIndex
from test.gui.fake_server_manager import FakeServerManager
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.components.globals.math_builder.math_element_tree import MathTreeModel
from scrutiny.gui.components.globals.math_builder.math_builder_component import MathBuilderComponent
from scrutiny.gui.core.watchable_registry.watchable_registry import WatchableRegistry
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.fqn_name_pair import FqnNamePair
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType


from scrutiny.tools.typing import *


class MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.registry = WatchableRegistry()
        self.server_manager = FakeServerManager(self.registry)

    def get_server_manager(self):
        return self.server_manager

    def get_watchable_registry(self):
        return self.registry


class DummyAppInterface(AbstractComponentAppInterface):
    def reveal_varlist_fqn(self, fqn: str) -> None:
        pass


class TestMathTreeModel(ScrutinyBaseGuiTest):
    def test_insert(self):
        model = MathTreeModel()
        element = GUIMathWatchable("AAA", "v1+v2+v3")
        with self.assertRaises(ValueError):
            model.insert_math_element(element)

        element.bind_watchable("v1", FqnNamePair("AAA", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        element.bind_watchable("v2", FqnNamePair("BBB", FQN.make(RegistryNodeType.Alias, "/a/b/d")))
        element.bind_watchable("v3", FqnNamePair("CCC", FQN.make(RegistryNodeType.RuntimePublishedValue, "/a/b/e")))

        model.insert_math_element(element)


class TestMathBuilderComponent(ScrutinyBaseGuiTest):
    def setUp(self):
        super().setUp()

        self.main_window = MainWindowStub()
        app_interface = DummyAppInterface()
        app_interface.server_manager = self.main_window.get_server_manager()
        app_interface.watchable_registry = self.main_window.get_watchable_registry()
        self.builder = MathBuilderComponent(
            self.main_window,
            'mathbuilder',
            app_interface
        )
        self.builder.setup()

    def tearDown(self):
        self.builder.teardown()
        return super().tearDown()
