from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QPen, QBrush, QColor

from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.circle_hmi_widget import CircleHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.rectangle_hmi_widget import RectangleHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.line_hmi_widget import LineHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.text_label_hmi_widget import TextLabelHMIWidget
from test.gui.fake_server_manager import FakeServerManager
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.gui import ScrutinyQtGUI, SupportedTheme
from scrutiny.gui.app_settings import configure_unit_test_app_settings


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


class HMIComponentBaseTest(ScrutinyBaseGuiTest):
    def setUp(self):
        super().setUp()
        settings = ScrutinyQtGUI.Settings(
            debug_layout=False,
            auto_connect=False,
            opengl_enabled=False,
            local_server_port=8765,
            start_local_server=False,
            theme=SupportedTheme.Default
        )
        configure_unit_test_app_settings(settings)

        self.main_window = MainWindowStub()
        app_interface = DummyAppInterface()
        app_interface.server_manager = self.main_window.get_server_manager()
        app_interface.watchable_registry = self.main_window.get_watchable_registry()
        self.hmi_component = HMIComponent(
            self.main_window,
            'watch1',
            app_interface
        )
        self.hmi_component.setup()
        self.hmi_component.ready()

    def tearDown(self):
        self.hmi_component.teardown()
        return super().tearDown()


class TestHMIWidgetSerialization(HMIComponentBaseTest):

    def test_serialize_circle(self):
        circle = CircleHMIWidget(self.hmi_component)
        circle.set_size(QSize(64, 128))
        self.hmi_component.add_hmi_widget(circle, QPoint(16, 32))
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)

        pen1 = QPen()
        pen1.setWidthF(2.5)
        pen1.setColor(QColor("#123456"))
        pen1.setStyle(Qt.PenStyle.DashDotLine)
        circle.set_border_pen(pen1)

        brush1 = QBrush()
        brush1.setColor(QColor("#558844"))
        circle.set_fill_brush(brush1)

        state = self.hmi_component.get_state()
        self.hmi_component.delete_hmi_widget(circle)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 0)

        fully_loaded = self.hmi_component.load_state(state)
        self.assertTrue(fully_loaded)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)
        all_widgets = list(self.hmi_component.iterate_hmi_widgets())
        self.assertEqual(len(all_widgets), 1)
        new_circle = all_widgets[0]
        self.assertIsInstance(new_circle, CircleHMIWidget)
        assert isinstance(new_circle, CircleHMIWidget)
        pen2 = new_circle.get_border_pen()
        brush2 = new_circle.get_fill_brush()

        self.assertEqual(new_circle.pos(), QPoint(16, 32))
        self.assertEqual(new_circle.get_size(), QSize(64, 128))

        self.assertEqual(pen1.widthF(), pen2.widthF())
        self.assertEqual(pen1.color(), pen2.color())
        self.assertEqual(pen1.style(), pen2.style())

        self.assertEqual(brush1.style(), brush2.style())
        self.assertEqual(brush1.color(), brush2.color())

    def test_serialize_rectangle(self):
        rectangle = RectangleHMIWidget(self.hmi_component)
        rectangle.set_size(QSize(64, 128))
        self.hmi_component.add_hmi_widget(rectangle, QPoint(16, 32))
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)

        pen1 = QPen()
        pen1.setWidthF(2.5)
        pen1.setColor(QColor("#123456"))
        pen1.setStyle(Qt.PenStyle.DashDotLine)
        rectangle.set_border_pen(pen1)

        brush1 = QBrush()
        brush1.setColor(QColor("#558844"))
        rectangle.set_fill_brush(brush1)

        state = self.hmi_component.get_state()
        self.hmi_component.delete_hmi_widget(rectangle)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 0)

        fully_loaded = self.hmi_component.load_state(state)
        self.assertTrue(fully_loaded)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)
        all_widgets = list(self.hmi_component.iterate_hmi_widgets())
        self.assertEqual(len(all_widgets), 1)
        new_rectangle = all_widgets[0]
        self.assertIsInstance(new_rectangle, RectangleHMIWidget)
        assert isinstance(new_rectangle, RectangleHMIWidget)
        pen2 = new_rectangle.get_border_pen()
        brush2 = new_rectangle.get_fill_brush()

        self.assertEqual(new_rectangle.pos(), QPoint(16, 32))
        self.assertEqual(new_rectangle.get_size(), QSize(64, 128))

        self.assertEqual(pen1.widthF(), pen2.widthF())
        self.assertEqual(pen1.color(), pen2.color())
        self.assertEqual(pen1.style(), pen2.style())

        self.assertEqual(brush1.style(), brush2.style())
        self.assertEqual(brush1.color(), brush2.color())

    def test_serialize_line(self):
        line = LineHMIWidget(self.hmi_component)
        line.set_size(QSize(64, 128))
        self.hmi_component.add_hmi_widget(line, QPoint(16, 32))
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)

        pen1 = QPen()
        pen1.setWidthF(2.5)
        pen1.setColor(QColor("#123456"))
        pen1.setStyle(Qt.PenStyle.DashDotLine)
        line.set_border_pen(pen1)

        state = self.hmi_component.get_state()
        self.hmi_component.delete_hmi_widget(line)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 0)

        fully_loaded = self.hmi_component.load_state(state)
        self.assertTrue(fully_loaded)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)
        all_widgets = list(self.hmi_component.iterate_hmi_widgets())
        self.assertEqual(len(all_widgets), 1)
        new_line = all_widgets[0]
        self.assertIsInstance(new_line, LineHMIWidget)
        assert isinstance(new_line, LineHMIWidget)
        pen2 = new_line.get_border_pen()

        self.assertEqual(new_line.pos(), QPoint(16, 32))
        self.assertEqual(new_line.get_size(), QSize(64, 128))

        self.assertEqual(pen1.widthF(), pen2.widthF())
        self.assertEqual(pen1.color(), pen2.color())
        self.assertEqual(pen1.style(), pen2.style())

    def test_serialize_text_label(self):
        text_label = TextLabelHMIWidget(self.hmi_component)
        text_label.set_size(QSize(64, 128))
        self.hmi_component.add_hmi_widget(text_label, QPoint(16, 32))
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)

        pen1 = QPen()
        pen1.setWidthF(2.5)
        pen1.setColor(QColor("#123456"))
        pen1.setStyle(Qt.PenStyle.DashDotLine)
        text_label.set_border_pen(pen1)

        brush1 = QBrush()
        brush1.setColor(QColor("#558844"))
        text_label.set_fill_brush(brush1)

        text_label.set_text("Potato")
        text_label.set_font_color(QColor("#975123"))

        state = self.hmi_component.get_state()
        self.hmi_component.delete_hmi_widget(text_label)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 0)

        fully_loaded = self.hmi_component.load_state(state)
        self.assertTrue(fully_loaded)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)
        all_widgets = list(self.hmi_component.iterate_hmi_widgets())
        self.assertEqual(len(all_widgets), 1)
        new_text_label = all_widgets[0]
        self.assertIsInstance(new_text_label, TextLabelHMIWidget)
        assert isinstance(new_text_label, TextLabelHMIWidget)
        pen2 = new_text_label.get_border_pen()
        brush2 = new_text_label.get_fill_brush()

        self.assertEqual(new_text_label.pos(), QPoint(16, 32))
        self.assertEqual(new_text_label.get_size(), QSize(64, 128))

        self.assertEqual(pen1.widthF(), pen2.widthF())
        self.assertEqual(pen1.color(), pen2.color())
        self.assertEqual(pen1.style(), pen2.style())

        self.assertEqual(brush1.style(), brush2.style())
        self.assertEqual(brush1.color(), brush2.color())

        self.assertEqual(new_text_label.get_text(), "Potato")
        self.assertEqual(new_text_label.get_font_color(), text_label.get_font_color())
