#    test_hmi_component.py
#        A test suite to the the HMI component
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QPoint, QSize, Qt, QEvent
from PySide6.QtGui import QPen, QBrush, QColor, QMouseEvent, QDragEnterEvent, QDragMoveEvent, QDropEvent, QDragLeaveEvent, QResizeEvent

from scrutiny import sdk
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData
from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.circle_hmi_widget import CircleHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.rectangle_hmi_widget import RectangleHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.line_hmi_widget import LineHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.text_label_hmi_widget import TextLabelHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.display.numerical_display_hmi_widget import NumericalDisplayHMIWidget, NumberFormattingConfig
from scrutiny.gui.components.locals.hmi.hmi_widgets.display.radial_gauge_hmi_widget import RadialGaugeHMIWidget, GaugeOverflowBehavior, ColorSpan
from scrutiny.gui.components.locals.hmi.hmi_widgets.display.linear_gauge_hmi_widget import LinearGaugeHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.display.color_indicator_hmi_widget import ColorIndicatorHMIWidget, RelationalOperator, ActiveBehavior
from scrutiny.gui.components.locals.hmi.common.hmi_colors import HMIColor
from test.gui.fake_server_manager import FakeServerManager
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.gui import ScrutinyQtGUI, SupportedTheme
from scrutiny.gui.app_settings import configure_unit_test_app_settings
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
        self.app_interface = DummyAppInterface()
        self.app_interface.server_manager = self.main_window.get_server_manager()
        self.app_interface.watchable_registry = self.main_window.get_watchable_registry()
        self.hmi_component = HMIComponent(
            self.main_window,
            'hmi1',
            self.app_interface
        )
        self.hmi_component.setup()
        self.hmi_component.ready()
        self.hmi_component.set_unittest_mode(True)

        workzone = self.hmi_component.get_workzone()
        old_size = workzone.viewport().size()
        workzone.viewport().setGeometry(7, 9, 645, 483)    # Not round on purpose
        new_size = workzone.viewport().size()
        workzone.resizeEvent(QResizeEvent(new_size, old_size))

    def tearDown(self):
        self.hmi_component.teardown()
        return super().tearDown()


class TestHMIWidgetSerialization(HMIComponentBaseTest):

    def test_serialize_circle(self):
        circle = CircleHMIWidget(self.app_interface)
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
        rectangle = RectangleHMIWidget(self.app_interface)
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
        line = LineHMIWidget(self.app_interface)
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
        text_label = TextLabelHMIWidget(self.app_interface)
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

    def test_serialize_numerical_display(self):
        display = NumericalDisplayHMIWidget(self.app_interface)
        display.set_size(QSize(64, 128))
        self.hmi_component.add_hmi_widget(display, QPoint(16, 32))
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)

        display.set_alignment(Qt.AlignmentFlag.AlignLeft)
        display.set_background_color(QColor("#987654"))
        display.set_border_color(QColor("#123456"))
        display.set_border_width(4)
        display.set_text_color(QColor("#147258"))
        config = NumberFormattingConfig(
            decimals=5,
            eng_notation=False,
            max_ints=4,
            units='W',
        )
        display.set_number_formatting_config(config)

        state = self.hmi_component.get_state()
        self.hmi_component.delete_hmi_widget(display)
        self.assertEqual(self.hmi_component.hmi_widget_count(), 0)
        fully_loaded = self.hmi_component.load_state(state)
        self.assertTrue(fully_loaded)
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)
        all_widgets = list(self.hmi_component.iterate_hmi_widgets())
        self.assertEqual(len(all_widgets), 1)
        new_display = all_widgets[0]

        self.assertIsInstance(new_display, NumericalDisplayHMIWidget)
        assert isinstance(new_display, NumericalDisplayHMIWidget)

        self.assertEqual(new_display.pos(), QPoint(16, 32))
        self.assertEqual(new_display.get_size(), QSize(64, 128))
        self.assertEqual(new_display.get_alignment(), display.get_alignment())
        self.assertEqual(new_display.get_background_color(), display.get_background_color())
        self.assertEqual(new_display.get_border_color(), display.get_border_color())
        self.assertEqual(new_display.get_border_width(), display.get_border_width())
        self.assertEqual(new_display.get_text_color(), display.get_text_color())
        self.assertEqual(new_display.get_number_formatting_config(), display.get_number_formatting_config())

    def test_serialize_radial_gauge(self):
        gauge = RadialGaugeHMIWidget(self.app_interface)
        gauge.set_size(QSize(64, 128))
        self.hmi_component.add_hmi_widget(gauge, QPoint(16, 32))
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)

        gauge.set_major_ticks(6)
        gauge.set_minor_ticks(3)
        config = NumberFormattingConfig(
            decimals=5,
            eng_notation=False,
            max_ints=4,
            units='W',
        )
        gauge.set_number_formatting_config(config)
        gauge.set_overflow_behavior(GaugeOverflowBehavior.SHOW_NA)
        color_spans = [
            ColorSpan(start=10, stop=30.5, color=HMIColor.HIGHLIGHT),
            ColorSpan(start=50.1, stop=90, color=HMIColor.WARNING)
        ]
        gauge.set_color_spans(color_spans)
        gauge.set_label_size_percent(35)

        state = self.hmi_component.get_state()
        self.hmi_component.delete_hmi_widget(gauge)
        self.assertEqual(self.hmi_component.hmi_widget_count(), 0)
        fully_loaded = self.hmi_component.load_state(state)
        self.assertTrue(fully_loaded)
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)
        all_widgets = list(self.hmi_component.iterate_hmi_widgets())
        self.assertEqual(len(all_widgets), 1)
        new_gauge = all_widgets[0]

        self.assertIsInstance(new_gauge, RadialGaugeHMIWidget)
        assert isinstance(new_gauge, RadialGaugeHMIWidget)

        self.assertEqual(new_gauge.pos(), QPoint(16, 32))
        self.assertEqual(new_gauge.get_size(), QSize(64, 128))
        self.assertEqual(new_gauge.get_major_ticks(), gauge.get_major_ticks())
        self.assertEqual(new_gauge.get_minor_ticks(), gauge.get_minor_ticks())
        self.assertEqual(new_gauge.get_number_formatting_config(), gauge.get_number_formatting_config())
        self.assertEqual(new_gauge.get_overflow_behavior(), gauge.get_overflow_behavior())
        self.assertEqual(new_gauge.get_label_size_percent(), gauge.get_label_size_percent())

    def test_serialize_linear_gauge(self):
        gauge = LinearGaugeHMIWidget(self.app_interface)
        gauge.set_size(QSize(128, 256))
        self.hmi_component.add_hmi_widget(gauge, QPoint(16, 32))
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)

        gauge.set_major_ticks(8)
        gauge.set_minor_ticks(4)
        gauge.set_overflow_behavior(GaugeOverflowBehavior.SHOW_NA)
        color_spans = [
            ColorSpan(start=10, stop=30.5, color=HMIColor.HIGHLIGHT),
            ColorSpan(start=50.1, stop=90, color=HMIColor.WARNING)
        ]
        gauge.set_color_spans(color_spans)
        gauge.set_inverted_axis(True)
        gauge.set_gauge_width_percent(33)
        gauge.set_label_size_percent(58)
        label_config = NumberFormattingConfig(decimals=3, eng_notation=False, max_ints=6, units='mV')
        gauge.set_label_format_config(label_config)

        # Verify all getters directly
        self.assertEqual(gauge.get_major_ticks(), 8)
        self.assertEqual(gauge.get_minor_ticks(), 4)
        self.assertEqual(gauge.get_overflow_behavior(), GaugeOverflowBehavior.SHOW_NA)
        loaded_spans = gauge.get_color_spans()
        self.assertEqual(len(loaded_spans), 2)
        self.assertEqual(loaded_spans[0], color_spans[0])
        self.assertEqual(loaded_spans[1], color_spans[1])
        self.assertEqual(gauge.get_inverted_axis(), True)
        self.assertEqual(gauge.get_gauge_width_percent(), 33)
        self.assertEqual(gauge.get_label_size_percent(), 58)
        self.assertEqual(gauge.get_label_format_config(), label_config)

        # Serialization round-trip
        state = self.hmi_component.get_state()
        self.hmi_component.delete_hmi_widget(gauge)
        self.assertEqual(self.hmi_component.hmi_widget_count(), 0)
        fully_loaded = self.hmi_component.load_state(state)
        self.assertTrue(fully_loaded)
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)
        all_widgets = list(self.hmi_component.iterate_hmi_widgets())
        self.assertEqual(len(all_widgets), 1)
        new_gauge = all_widgets[0]

        self.assertIsInstance(new_gauge, LinearGaugeHMIWidget)
        assert isinstance(new_gauge, LinearGaugeHMIWidget)

        self.assertEqual(new_gauge.pos(), QPoint(16, 32))
        self.assertEqual(new_gauge.get_size(), QSize(128, 256))
        self.assertEqual(new_gauge.get_major_ticks(), gauge.get_major_ticks())
        self.assertEqual(new_gauge.get_minor_ticks(), gauge.get_minor_ticks())
        self.assertEqual(new_gauge.get_overflow_behavior(), gauge.get_overflow_behavior())
        new_spans = new_gauge.get_color_spans()
        self.assertEqual(len(new_spans), len(color_spans))
        for i in range(len(color_spans)):
            self.assertEqual(new_spans[i], color_spans[i])
        self.assertEqual(new_gauge.get_inverted_axis(), gauge.get_inverted_axis())
        self.assertEqual(new_gauge.get_gauge_width_percent(), gauge.get_gauge_width_percent())
        self.assertEqual(new_gauge.get_label_size_percent(), gauge.get_label_size_percent())
        self.assertEqual(new_gauge.get_label_format_config(), gauge.get_label_format_config())

    def test_serialize_color_indicator(self):
        indicator = ColorIndicatorHMIWidget(self.app_interface)
        indicator.set_size(QSize(32, 32))
        self.hmi_component.add_hmi_widget(indicator, QPoint(16, 32))
        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)

        indicator.set_on_color(HMIColor.WARNING)
        indicator.set_off_color(HMIColor.DANGER)
        indicator.set_operator(RelationalOperator.GEQ)
        indicator.set_active_behavior(ActiveBehavior.BlinkSlow)

        state = self.hmi_component.get_state()
        self.hmi_component.delete_hmi_widget(indicator)
        self.assertEqual(self.hmi_component.hmi_widget_count(), 0)

        fully_loaded = self.hmi_component.load_state(state)
        self.assertTrue(fully_loaded)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 1)
        all_widgets = list(self.hmi_component.iterate_hmi_widgets())
        self.assertEqual(len(all_widgets), 1)
        new_indicator = all_widgets[0]

        self.assertIsInstance(new_indicator, ColorIndicatorHMIWidget)
        assert isinstance(new_indicator, ColorIndicatorHMIWidget)

        self.assertEqual(new_indicator.pos(), QPoint(16, 32))
        self.assertEqual(new_indicator.get_size(), QSize(32, 32))
        self.assertEqual(new_indicator.get_on_color(), indicator.get_on_color())
        self.assertEqual(new_indicator.get_off_color(), indicator.get_off_color())
        self.assertEqual(new_indicator.get_operator(), indicator.get_operator())
        self.assertEqual(new_indicator.get_active_behavior(), indicator.get_active_behavior())


class TestWorkZone(HMIComponentBaseTest):
    def test_selection_logic(self):
        workzone = self.hmi_component.get_workzone()

        selection_change_call_list = []

        def selection_changed_slot(new_selection):
            selection_change_call_list.append(new_selection)

        workzone.signals.selection_changed.connect(selection_changed_slot)

        circle1 = CircleHMIWidget(self.app_interface)
        circle2 = CircleHMIWidget(self.app_interface)
        circle3 = CircleHMIWidget(self.app_interface)
        circle1.set_size(QSize(16, 16))
        circle2.set_size(QSize(16, 16))
        circle3.set_size(QSize(16, 16))
        self.hmi_component.add_hmi_widget(circle1, QPoint(0, 0))
        self.hmi_component.add_hmi_widget(circle2, QPoint(32, 0))
        self.hmi_component.add_hmi_widget(circle3, QPoint(0, 32))

        self.assertEqual(len(selection_change_call_list), 0)

        selection = [circle1, circle2]
        workzone.select_widgets(selection)
        self.assertEqual(len(selection_change_call_list), 1)
        self.assertEqual(selection, selection_change_call_list[0])
        self.assertIsNot(selection, selection_change_call_list[0])  # Ensure a copy is made

        workzone.add_widgets_to_selection([circle3])
        self.assertEqual(len(selection_change_call_list), 2)
        self.assertEqual([circle1, circle2, circle3], selection_change_call_list[1])

        workzone.deselect_all_widgets()
        self.assertEqual(len(selection_change_call_list), 3)
        self.assertEqual([], selection_change_call_list[2])

        workzone.deselect_all_widgets()
        selection_change_call_list.clear()

        def get_center(w) -> QPoint:
            return QPoint(
                int(w.pos().x() + w.get_size().width() / 2),
                int(w.pos().y() + w.get_size().height() / 2),
            )

        down_event = QMouseEvent(QEvent.Type.MouseButtonPress, get_center(circle1),
                                 Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                 )
        up_event = QMouseEvent(QEvent.Type.MouseButtonRelease, get_center(circle1),
                               Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                               )
        workzone.mousePressEvent(down_event)
        workzone.mouseReleaseEvent(up_event)
        self.assertEqual(len(selection_change_call_list), 1)
        self.assertEqual(selection_change_call_list[0], [circle1])

        down_event = QMouseEvent(QEvent.Type.MouseButtonPress, get_center(circle2),
                                 Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                 )
        up_event = QMouseEvent(QEvent.Type.MouseButtonRelease, get_center(circle2),
                               Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                               )
        workzone.mousePressEvent(down_event)
        workzone.mouseReleaseEvent(up_event)
        self.assertEqual(len(selection_change_call_list), 2)
        self.assertEqual(selection_change_call_list[1], [circle2])

        down_event = QMouseEvent(QEvent.Type.MouseButtonPress, get_center(circle3),
                                 Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier
                                 )
        up_event = QMouseEvent(QEvent.Type.MouseButtonRelease, get_center(circle3),
                               Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier
                               )
        workzone.mousePressEvent(down_event)
        workzone.mouseReleaseEvent(up_event)
        self.assertEqual(len(selection_change_call_list), 3)
        self.assertEqual(selection_change_call_list[2], [circle2, circle3])

        selection_change_call_list.clear()
        workzone.select_widgets([circle1, circle2, circle3])
        self.assertEqual(len(selection_change_call_list), 1)

        workzone.remove_widget(circle2)
        self.assertEqual(len(selection_change_call_list), 2)
        self.assertEqual([circle1, circle3], selection_change_call_list[1])

        self.assertEqual(workzone.selected_widgets(), [circle1, circle3])
        workzone.deselect_all_widgets()

        # Check if click in grid deselect
        workzone.select_widgets([circle1, circle2, circle3])
        down_event = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(256, 256),
                                 Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier
                                 )
        up_event = QMouseEvent(QEvent.Type.MouseButtonRelease, QPoint(256, 256),
                               Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier
                               )
        workzone.mousePressEvent(down_event)    # Click empty region
        workzone.mouseReleaseEvent(up_event)
        self.assertEqual(workzone.selected_widgets(), [])   # Deselected

    def test_drop_library_input(self):
        workzone = self.hmi_component.get_workzone()
        mimedata = ScrutinyDragData(ScrutinyDragData.DataType.HMIWidgetClass, {'class': CircleHMIWidget.__name__}).to_mime()
        assert mimedata is not None
        drop_event = QDropEvent(QPoint(16, 32), Qt.DropAction.CopyAction, mimedata, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        self.assertEqual(workzone.count_hmi_widgets(), 0)
        workzone.dropEvent(drop_event)
        self.assertEqual(workzone.count_hmi_widgets(), 1)

        mimedata = ScrutinyDragData(ScrutinyDragData.DataType.HMIWidgetClass, {'class': 'unknown_class'}).to_mime()
        assert mimedata is not None
        drop_event = QDropEvent(QPoint(16, 32), Qt.DropAction.CopyAction, mimedata, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        workzone.dropEvent(drop_event)
        self.assertEqual(workzone.count_hmi_widgets(), 1)   # Expect no changes

    def test_drag_library_input(self):

        workzone = self.hmi_component.get_workzone()
        drop_placeholder = workzone.get_drop_placeholder()
        mimedata = ScrutinyDragData(ScrutinyDragData.DataType.HMIWidgetClass, {'class': CircleHMIWidget.__name__}).to_mime()
        assert mimedata is not None
        drag_enter = QDragEnterEvent(QPoint(16, 16), Qt.DropAction.CopyAction, mimedata, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        self.assertFalse(drop_placeholder.isVisible())
        workzone.dragEnterEvent(drag_enter)
        self.assertTrue(drop_placeholder.isVisible())

        expected_size = CircleHMIWidget.default_size()
        target_left_corner = QPoint(16, 32)
        required_center = target_left_corner + QPoint(expected_size.width() // 2, expected_size.height() // 2)
        drag_move = QDragMoveEvent(required_center, Qt.DropAction.CopyAction, mimedata, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        workzone.dragMoveEvent(drag_move)
        self.assertEqual(drop_placeholder.pos(), target_left_corner)
        self.assertTrue(drop_placeholder.isVisible())

        drag_leave = QDragLeaveEvent()
        workzone.dragLeaveEvent(drag_leave)
        self.assertFalse(drop_placeholder.isVisible())

    def test_rubber_band(self):
        workzone = self.hmi_component.get_workzone()
        circle1 = CircleHMIWidget(self.app_interface)
        circle2 = CircleHMIWidget(self.app_interface)
        circle3 = CircleHMIWidget(self.app_interface)

        circle1.set_size(QSize(16, 16))
        circle2.set_size(QSize(16, 16))
        circle3.set_size(QSize(16, 16))

        self.hmi_component.add_hmi_widget(circle1, QPoint(16, 32))
        self.hmi_component.add_hmi_widget(circle2, QPoint(32, 16))
        self.hmi_component.add_hmi_widget(circle3, QPoint(64, 64))

        down_event = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(15, 15),
                                 Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                 )
        move_event = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(32 + 16 + 1, 32 + 16 + 1),
                                 Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                 )
        up_event = QMouseEvent(QEvent.Type.MouseButtonRelease, QPoint(32 + 16 + 1, 32 + 16 + 1),
                               Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                               )

        workzone.mousePressEvent(down_event)
        workzone.mouseMoveEvent(move_event)
        workzone.mouseReleaseEvent(up_event)

        self.assertCountEqual(workzone.selected_widgets(), [circle1, circle2])

    def test_resize(self):
        circle = CircleHMIWidget(self.app_interface)
        initial_w = 64
        initial_h = 64
        initial_pos = QPoint(128, 128)
        self.hmi_component.resize(640, 640)
        self.hmi_component.add_hmi_widget(circle)

        def top_left(w: BaseHMIWidget) -> QPoint:
            return w.pos().toPoint() + QPoint(1, 1)

        def top_right(w: BaseHMIWidget) -> QPoint:
            return w.pos().toPoint() + QPoint(w.get_size().width(), 0) + QPoint(-1, 1)

        def bottom_left(w: BaseHMIWidget) -> QPoint:
            return w.pos().toPoint() + QPoint(0, w.get_size().height()) + QPoint(1, -1)

        def bottom_right(w: BaseHMIWidget) -> QPoint:
            return w.pos().toPoint() + QPoint(w.get_size().width(), w.get_size().height()) + QPoint(-1, -1)

        def mid_left(w: BaseHMIWidget) -> QPoint:
            return w.pos().toPoint() + QPoint(0, w.get_size().height() // 2) + QPoint(1, 0)

        def mid_right(w: BaseHMIWidget) -> QPoint:
            return w.pos().toPoint() + QPoint(w.get_size().width(), w.get_size().height() // 2) + QPoint(-1, 0)

        def bottom_mid(w: BaseHMIWidget) -> QPoint:
            return w.pos().toPoint() + QPoint(w.get_size().width() // 2, w.get_size().height()) + QPoint(0, -1)

        def top_mid(w: BaseHMIWidget) -> QPoint:
            return w.pos().toPoint() + QPoint(w.get_size().width() // 2, 0) + QPoint(0, 1)

        def do_scale_test(func: Callable[[BaseHMIWidget], QPoint], delta_move: QPoint, expected_size: QSize, unchanged_point: Callable[[BaseHMIWidget], QPoint]):
            workzone = self.hmi_component.get_workzone()
            self.assertGreater(workzone.width(), 256)
            self.assertGreater(workzone.height(), 256)
            circle.setPos(initial_pos)
            circle.set_size(QSize(initial_w, initial_h))
            start_pos = func(circle)
            before_unchanged_point = unchanged_point(circle)
            down_event = QMouseEvent(QEvent.Type.MouseButtonPress, start_pos,
                                     Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                     )
            move_event = QMouseEvent(QEvent.Type.MouseButtonPress, start_pos + delta_move,
                                     Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                     )
            up_event = QMouseEvent(QEvent.Type.MouseButtonRelease, start_pos + delta_move,
                                   Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                   )

            workzone.mousePressEvent(down_event)
            workzone.mouseMoveEvent(move_event)
            workzone.mouseReleaseEvent(up_event)

            self.assertEqual(circle.get_size(), expected_size, "Size mismatch")
            self.assertEqual(unchanged_point(circle), before_unchanged_point)

        delta = 32

        self.assertLess(circle.min_width(), initial_w - delta)
        self.assertLess(circle.min_height(), initial_h - delta)

        delta_down = QPoint(0, delta - 1)
        delta_down_long = QPoint(0, delta + circle.get_size().height() - 1)
        delta_up = QPoint(0, -delta - 1)
        delta_up_long = QPoint(0, -delta - circle.get_size().height() + 1)
        delta_left = QPoint(-delta + 1, 0)
        delta_left_long = QPoint(-delta - circle.get_size().width() + 1, 0)
        delta_right = QPoint(delta - 1, 0)
        delta_right_long = QPoint(delta + circle.get_size().width() - 1, 0)
        delta_down_right = delta_down + delta_right
        delta_down_right_long = delta_down_long + delta_right_long
        delta_up_left = delta_up + delta_left
        delta_up_left_long = delta_up_long + delta_left_long
        delta_up_right_long = delta_up_long + delta_right_long
        delta_down_left_long = delta_down_long + delta_left_long
        delta_down_right_long = delta_down_long + delta_right_long

        unchanged_size = QSize(initial_w, initial_h)
        smaller_w = QSize(initial_w - delta, initial_h)
        smaller_h = QSize(initial_w, initial_h - delta)
        smaller_wh = QSize(initial_w - delta, initial_h - delta)
        bigger_w = QSize(initial_w + delta, initial_h)
        bigger_h = QSize(initial_w, initial_h + delta)
        bigger_wh = QSize(initial_w + delta, initial_h + delta)
        bigger_w_smaller_h = QSize(initial_w + delta, initial_h - delta)
        smaller_w_bigger_h = QSize(initial_w - delta, initial_h + delta)
        min_w = QSize(circle.min_width(), initial_h)
        min_h = QSize(initial_w, circle.min_height())
        min_wh = QSize(circle.min_width(), circle.min_height())

        with self.subTest("bottom_right -> scale down"):
            do_scale_test(bottom_right, delta_down, expected_size=bigger_h, unchanged_point=top_left)
        with self.subTest("bottom_right -> scale right"):
            do_scale_test(bottom_right, delta_right, expected_size=bigger_w, unchanged_point=top_left)
        with self.subTest("bottom_right -> scale down right"):
            do_scale_test(bottom_right, delta_down_right, expected_size=bigger_wh, unchanged_point=top_left)
        with self.subTest("bottom_right -> scale left"):
            do_scale_test(bottom_right, delta_left, expected_size=smaller_w, unchanged_point=top_left)
        with self.subTest("bottom_right -> scale up"):
            do_scale_test(bottom_right, delta_up, expected_size=smaller_h, unchanged_point=top_left)
        with self.subTest("bottom_right -> scale up left"):
            do_scale_test(bottom_right, delta_up_left, expected_size=smaller_wh, unchanged_point=top_left)

        with self.subTest("top_right -> scale down"):
            do_scale_test(top_right, delta_down, expected_size=smaller_h, unchanged_point=bottom_left)
        with self.subTest("top_right -> scale right"):
            do_scale_test(top_right, delta_right, expected_size=bigger_w, unchanged_point=bottom_left)
        with self.subTest("top_right -> scale down right"):
            do_scale_test(top_right, delta_down_right, expected_size=bigger_w_smaller_h, unchanged_point=bottom_left)
        with self.subTest("top_right -> scale left"):
            do_scale_test(top_right, delta_left, expected_size=smaller_w, unchanged_point=bottom_left)
        with self.subTest("top_right -> scale up"):
            do_scale_test(top_right, delta_up, expected_size=bigger_h, unchanged_point=bottom_left)
        with self.subTest("top_right -> scale up left"):
            do_scale_test(top_right, delta_up_left, expected_size=smaller_w_bigger_h, unchanged_point=bottom_left)

        with self.subTest("bottom_left -> scale down"):
            do_scale_test(bottom_left, delta_down, expected_size=bigger_h, unchanged_point=top_right)
        with self.subTest("bottom_left -> scale right"):
            do_scale_test(bottom_left, delta_right, expected_size=smaller_w, unchanged_point=top_right)
        with self.subTest("bottom_left -> scale down right"):
            do_scale_test(bottom_left, delta_down_right, expected_size=smaller_w_bigger_h, unchanged_point=top_right)
        with self.subTest("bottom_left -> scale left"):
            do_scale_test(bottom_left, delta_left, expected_size=bigger_w, unchanged_point=top_right)
        with self.subTest("bottom_left -> scale up"):
            do_scale_test(bottom_left, delta_up, expected_size=smaller_h, unchanged_point=top_right)
        with self.subTest("bottom_left -> scale up left"):
            do_scale_test(bottom_left, delta_up_left, expected_size=bigger_w_smaller_h, unchanged_point=top_right)

        with self.subTest("top_left -> scale down"):
            do_scale_test(top_left, delta_down, expected_size=smaller_h, unchanged_point=bottom_right)
        with self.subTest("top_left -> scale right"):
            do_scale_test(top_left, delta_right, expected_size=smaller_w, unchanged_point=bottom_right)
        with self.subTest("top_left -> scale down right"):
            do_scale_test(top_left, delta_down_right, expected_size=smaller_wh, unchanged_point=bottom_right)
        with self.subTest("top_left -> scale left"):
            do_scale_test(top_left, delta_left, expected_size=bigger_w, unchanged_point=bottom_right)
        with self.subTest("top_left -> scale up"):
            do_scale_test(top_left, delta_up, expected_size=bigger_h, unchanged_point=bottom_right)
        with self.subTest("top_left -> scale up left"):
            do_scale_test(top_left, delta_up_left, expected_size=bigger_wh, unchanged_point=bottom_right)

        with self.subTest("mid_left -> scale down"):
            do_scale_test(mid_left, delta_down, expected_size=unchanged_size, unchanged_point=bottom_right)
        with self.subTest("mid_left -> scale right"):
            do_scale_test(mid_left, delta_right, expected_size=smaller_w, unchanged_point=bottom_right)
        with self.subTest("mid_left -> scale down right"):
            do_scale_test(mid_left, delta_down_right, expected_size=smaller_w, unchanged_point=bottom_right)
        with self.subTest("mid_left -> scale left"):
            do_scale_test(mid_left, delta_left, expected_size=bigger_w, unchanged_point=bottom_right)
        with self.subTest("mid_left -> scale up"):
            do_scale_test(mid_left, delta_up, expected_size=unchanged_size, unchanged_point=bottom_right)
        with self.subTest("mid_left -> scale up left"):
            do_scale_test(mid_left, delta_up_left, expected_size=bigger_w, unchanged_point=bottom_right)

        with self.subTest("mid_right -> scale down"):
            do_scale_test(mid_right, delta_down, expected_size=unchanged_size, unchanged_point=bottom_left)
        with self.subTest("mid_right -> scale right"):
            do_scale_test(mid_right, delta_right, expected_size=bigger_w, unchanged_point=bottom_left)
        with self.subTest("mid_right -> scale down right"):
            do_scale_test(mid_right, delta_down_right, expected_size=bigger_w, unchanged_point=bottom_left)
        with self.subTest("mid_right -> scale left"):
            do_scale_test(mid_right, delta_left, expected_size=smaller_w, unchanged_point=bottom_left)
        with self.subTest("mid_right -> scale up"):
            do_scale_test(mid_right, delta_up, expected_size=unchanged_size, unchanged_point=bottom_left)
        with self.subTest("mid_right -> scale up left"):
            do_scale_test(mid_right, delta_up_left, expected_size=smaller_w, unchanged_point=bottom_left)

        with self.subTest("top_mid -> scale down"):
            do_scale_test(top_mid, delta_down, expected_size=smaller_h, unchanged_point=bottom_mid)
        with self.subTest("top_mid -> scale right"):
            do_scale_test(top_mid, delta_right, expected_size=unchanged_size, unchanged_point=bottom_mid)
        with self.subTest("top_mid -> scale down right"):
            do_scale_test(top_mid, delta_down_right, expected_size=smaller_h, unchanged_point=bottom_mid)
        with self.subTest("top_mid -> scale left"):
            do_scale_test(top_mid, delta_left, expected_size=unchanged_size, unchanged_point=bottom_mid)
        with self.subTest("top_mid -> scale up"):
            do_scale_test(top_mid, delta_up, expected_size=bigger_h, unchanged_point=bottom_mid)
        with self.subTest("top_mid -> scale up left"):
            do_scale_test(top_mid, delta_up_left, expected_size=bigger_h, unchanged_point=bottom_mid)

        with self.subTest("bottom_mid -> scale down"):
            do_scale_test(bottom_mid, delta_down, expected_size=bigger_h, unchanged_point=top_mid)
        with self.subTest("bottom_mid -> scale right"):
            do_scale_test(bottom_mid, delta_right, expected_size=unchanged_size, unchanged_point=top_mid)
        with self.subTest("bottom_mid -> scale down right"):
            do_scale_test(bottom_mid, delta_down_right, expected_size=bigger_h, unchanged_point=top_mid)
        with self.subTest("bottom_mid -> scale left"):
            do_scale_test(bottom_mid, delta_left, expected_size=unchanged_size, unchanged_point=top_mid)
        with self.subTest("bottom_mid -> scale up"):
            do_scale_test(bottom_mid, delta_up, expected_size=smaller_h, unchanged_point=top_mid)
        with self.subTest("bottom_mid -> scale up left"):
            do_scale_test(bottom_mid, delta_up_left, expected_size=smaller_h, unchanged_point=top_mid)

        # Go beyond other size to clip at min
        with self.subTest("top_left -> reduce clip right"):
            do_scale_test(top_left, delta_right_long, expected_size=min_w, unchanged_point=bottom_right)
        with self.subTest("top_left -> reduce clip down"):
            do_scale_test(top_left, delta_down_long, expected_size=min_h, unchanged_point=bottom_right)
        with self.subTest("top_left -> reduce clip down right"):
            do_scale_test(top_left, delta_down_right_long, expected_size=min_wh, unchanged_point=bottom_right)

        with self.subTest("bottom_right -> reduce clip left"):
            do_scale_test(bottom_right, delta_left_long, expected_size=min_w, unchanged_point=top_left)
        with self.subTest("bottom_right -> reduce clip up"):
            do_scale_test(bottom_right, delta_up_long, expected_size=min_h, unchanged_point=top_left)
        with self.subTest("bottom_right -> reduce clip up left"):
            do_scale_test(bottom_right, delta_up_left_long, expected_size=min_wh, unchanged_point=top_left)

        with self.subTest("top_right -> reduce clip left"):
            do_scale_test(top_right, delta_left_long, expected_size=min_w, unchanged_point=bottom_left)
        with self.subTest("top_right -> reduce clip down"):
            do_scale_test(top_right, delta_down_long, expected_size=min_h, unchanged_point=bottom_left)
        with self.subTest("top_right -> reduce clip down left"):
            do_scale_test(top_right, delta_down_left_long, expected_size=min_wh, unchanged_point=bottom_left)

        with self.subTest("bottom_left -> reduce clip left"):
            do_scale_test(bottom_left, delta_right_long, expected_size=min_w, unchanged_point=top_right)
        with self.subTest("bottom_left -> reduce clip up"):
            do_scale_test(bottom_left, delta_up_long, expected_size=min_h, unchanged_point=top_right)
        with self.subTest("bottom_left -> reduce clip up left"):
            do_scale_test(bottom_left, delta_up_right_long, expected_size=min_wh, unchanged_point=top_right)

    def test_move_widget(self):
        workzone = self.hmi_component.get_workzone()
        circle = CircleHMIWidget(self.app_interface)
        initial_size = QSize(64, 64)
        initial_pos = QPoint(32, 32)
        circle.set_size(initial_size)
        self.hmi_component.add_hmi_widget(circle)

        def apply_move(start_pos: QPoint, delta_move: QPoint):
            down_event = QMouseEvent(QEvent.Type.MouseButtonPress, start_pos,
                                     Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                     )
            move_event = QMouseEvent(QEvent.Type.MouseButtonPress, start_pos + delta_move,
                                     Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                     )
            up_event = QMouseEvent(QEvent.Type.MouseButtonRelease, start_pos + delta_move,
                                   Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                   )

            workzone.mousePressEvent(down_event)
            workzone.mouseMoveEvent(move_event)
            workzone.mouseReleaseEvent(up_event)

        circle.setPos(initial_pos)
        apply_move(QPoint(50, 50), QPoint(9, 25))
        self.assertEqual(circle.pos().toPoint(), initial_pos + QPoint(16, 32))
        self.assertEqual(circle.get_size(), initial_size)

        circle.setPos(initial_pos)
        apply_move(QPoint(50, 50), QPoint(7, 23))
        self.assertEqual(circle.pos().toPoint(), initial_pos + QPoint(0, 16))
        self.assertEqual(circle.get_size(), initial_size)

        circle.setPos(initial_pos)
        apply_move(QPoint(50, 50), QPoint(-7, -23))
        self.assertEqual(circle.pos().toPoint(), initial_pos + QPoint(0, -16))
        self.assertEqual(circle.get_size(), initial_size)

        circle.setPos(initial_pos)
        apply_move(QPoint(50, 50), QPoint(-9, -25))
        self.assertEqual(circle.pos().toPoint(), initial_pos + QPoint(-16, -32))
        self.assertEqual(circle.get_size(), initial_size)

        # Check clip top left
        circle.setPos(initial_pos)
        apply_move(QPoint(50, 50), -circle.pos().toPoint() + QPoint(-32, -32))
        self.assertEqual(circle.pos().toPoint(), QPoint(0, 0))
        self.assertEqual(circle.get_size(), initial_size)

        # check clip bottom right
        circle.setPos(initial_pos)

        apply_move(QPoint(50, 50), workzone.sceneRect().bottomRight().toPoint() + QPoint(32, 32))
        max_x = int(((workzone.sceneRect().width() - circle.get_size().width()) // 16) * 16)
        max_y = int(((workzone.sceneRect().height() - circle.get_size().height()) // 16) * 16)
        expected_pos = QPoint(max_x, max_y)
        self.assertEqual(circle.pos().toPoint(), expected_pos)
        self.assertEqual(circle.get_size(), initial_size)

    def test_emit_right_click(self):
        right_click_list = []

        def click_slot(widget, event):
            right_click_list.append(widget)

        workzone = self.hmi_component.get_workzone()
        workzone.signals.right_click.connect(click_slot)

        circle = CircleHMIWidget(self.app_interface)
        circle.set_size(QSize(32, 32))
        self.hmi_component.add_hmi_widget(circle)

        click_pos = circle.pos() + QPoint(circle.get_size().width() // 2, circle.get_size().height() // 2)

        down_event = QMouseEvent(QEvent.Type.MouseButtonPress, click_pos,
                                 Qt.MouseButton.RightButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                 )

        up_event = QMouseEvent(QEvent.Type.MouseButtonRelease, click_pos,
                               Qt.MouseButton.RightButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                               )

        workzone.mousePressEvent(down_event)
        workzone.mouseReleaseEvent(up_event)

        click_pos = circle.pos() + QPoint(circle.get_size().width() + 1, circle.get_size().height() + 1)

        down_event = QMouseEvent(QEvent.Type.MouseButtonPress, click_pos,
                                 Qt.MouseButton.RightButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                                 )

        up_event = QMouseEvent(QEvent.Type.MouseButtonRelease, click_pos,
                               Qt.MouseButton.RightButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
                               )

        workzone.mousePressEvent(down_event)
        workzone.mouseReleaseEvent(up_event)

        self.assertEqual(len(right_click_list), 2)

        self.assertEqual(right_click_list[0], circle)
        self.assertEqual(right_click_list[1], None)

    def test_zvalue_manipualtion(self):
        workzone = self.hmi_component.get_workzone()
        circle1 = CircleHMIWidget(self.app_interface)
        circle2 = CircleHMIWidget(self.app_interface)
        circle3 = CircleHMIWidget(self.app_interface)
        circle4 = CircleHMIWidget(self.app_interface)

        self.hmi_component.add_hmi_widget(circle1)
        self.hmi_component.add_hmi_widget(circle2)
        self.hmi_component.add_hmi_widget(circle3)
        self.hmi_component.add_hmi_widget(circle4)

        self.assertEqual(circle1.zValue(), 0)
        self.assertEqual(circle2.zValue(), 1)
        self.assertEqual(circle3.zValue(), 2)
        self.assertEqual(circle4.zValue(), 3)

        self.hmi_component.move_forward(circle4)  # Should have no effect
        self.assertEqual(circle1.zValue(), 0)
        self.assertEqual(circle2.zValue(), 1)
        self.assertEqual(circle3.zValue(), 2)
        self.assertEqual(circle4.zValue(), 3)

        self.hmi_component.move_backward(circle1)  # Should have no effect
        self.assertEqual(circle1.zValue(), 0)
        self.assertEqual(circle2.zValue(), 1)
        self.assertEqual(circle3.zValue(), 2)
        self.assertEqual(circle4.zValue(), 3)

        self.hmi_component.move_backward(circle3)
        self.hmi_component.move_backward(circle3)
        self.assertEqual(circle3.zValue(), 0)
        self.assertEqual(circle1.zValue(), 1)
        self.assertEqual(circle2.zValue(), 2)
        self.assertEqual(circle4.zValue(), 3)

        self.hmi_component.move_forward(circle1)
        self.assertEqual(circle3.zValue(), 0)
        self.assertEqual(circle2.zValue(), 1)
        self.assertEqual(circle1.zValue(), 2)
        self.assertEqual(circle4.zValue(), 3)

        self.hmi_component.move_to_front(circle2)
        self.assertEqual(circle3.zValue(), 0)
        self.assertEqual(circle1.zValue(), 1)
        self.assertEqual(circle4.zValue(), 2)
        self.assertEqual(circle2.zValue(), 3)

        self.hmi_component.move_to_back(circle4)
        self.assertEqual(circle4.zValue(), 0)
        self.assertEqual(circle3.zValue(), 1)
        self.assertEqual(circle1.zValue(), 2)
        self.assertEqual(circle2.zValue(), 3)

    def test_register_with_visibility(self):
        self.app_interface.watchable_registry.write_content({
            sdk.WatchableType.Variable: {
                '/var/aaa': sdk.BriefWatchableConfiguration(sdk.WatchableType.Variable, sdk.EmbeddedDataType.float32, enum=None),
                '/var/bbb': sdk.BriefWatchableConfiguration(sdk.WatchableType.Variable, sdk.EmbeddedDataType.float32, enum=None)
            }
        })
        display = NumericalDisplayHMIWidget(self.app_interface)
        self.hmi_component.add_hmi_widget(display)

        self.assertEqual(self.app_interface.watchable_registry.node_watcher_count(sdk.WatchableType.Variable, '/var/aaa'), 0)
        display.configure_vslot_watchable('val', WatchableRegistry.FQN.make(sdk.WatchableType.Variable, '/var/aaa'), 'test')
        self.assertEqual(self.app_interface.watchable_registry.node_watcher_count(sdk.WatchableType.Variable, '/var/aaa'), 1)
        self.hmi_component.visibilityChanged(False)
        self.assertEqual(self.app_interface.watchable_registry.node_watcher_count(sdk.WatchableType.Variable, '/var/aaa'), 0)
        self.hmi_component.visibilityChanged(True)
        self.assertEqual(self.app_interface.watchable_registry.node_watcher_count(sdk.WatchableType.Variable, '/var/aaa'), 1)


class TestHMIComponent(HMIComponentBaseTest):
    def test_serialize_and_reload_state(self):
        circle1 = CircleHMIWidget(self.app_interface)
        rect2 = RectangleHMIWidget(self.app_interface)
        line3 = LineHMIWidget(self.app_interface)
        label4 = TextLabelHMIWidget(self.app_interface)

        self.hmi_component.add_hmi_widget(circle1)
        self.hmi_component.add_hmi_widget(rect2)
        self.hmi_component.add_hmi_widget(line3)
        self.hmi_component.add_hmi_widget(label4)

        self.hmi_component.move_to_front(rect2)

        self.assertEqual(circle1.zValue(), 0)
        self.assertEqual(line3.zValue(), 1)
        self.assertEqual(label4.zValue(), 2)
        self.assertEqual(rect2.zValue(), 3)

        circle1.setPos(16, 32)
        rect2.setPos(32, 48)
        line3.setPos(48, 64)
        label4.setPos(64, 80)

        circle1.set_size(QSize(64, 48))
        rect2.set_size(QSize(48, 64))
        line3.set_size(QSize(32, 16))
        label4.set_size(QSize(16, 32))

        state = self.hmi_component.get_state()
        for widget in list(self.hmi_component.iterate_hmi_widgets()):
            self.hmi_component.delete_hmi_widget(widget)
        self.assertEqual(self.hmi_component.hmi_widget_count(), 0)
        self.hmi_component.load_state(state)

        self.assertEqual(self.hmi_component.hmi_widget_count(), 4)

        new_circle: Optional[CircleHMIWidget] = None
        new_rect: Optional[RectangleHMIWidget] = None
        new_line: Optional[LineHMIWidget] = None
        new_label: Optional[TextLabelHMIWidget] = None

        for widget in self.hmi_component.iterate_hmi_widgets():
            if isinstance(widget, CircleHMIWidget):
                new_circle = widget
            elif isinstance(widget, RectangleHMIWidget):
                new_rect = widget
            elif isinstance(widget, LineHMIWidget):
                new_line = widget
            elif isinstance(widget, TextLabelHMIWidget):
                new_label = widget

        self.assertIsNotNone(new_circle)
        self.assertIsNotNone(new_rect)
        self.assertIsNotNone(new_line)
        self.assertIsNotNone(new_label)

        self.assertEqual(new_circle.pos(), circle1.pos())
        self.assertEqual(new_circle.get_size(), circle1.get_size())
        self.assertEqual(new_circle.zValue(), circle1.zValue())

        self.assertEqual(new_rect.pos(), rect2.pos())
        self.assertEqual(new_rect.get_size(), rect2.get_size())
        self.assertEqual(new_rect.zValue(), rect2.zValue())

        self.assertEqual(new_line.pos(), line3.pos())
        self.assertEqual(new_line.get_size(), line3.get_size())
        self.assertEqual(new_line.zValue(), line3.zValue())

        self.assertEqual(new_label.pos(), label4.pos())
        self.assertEqual(new_label.get_size(), label4.get_size())
        self.assertEqual(new_label.zValue(), label4.zValue())
