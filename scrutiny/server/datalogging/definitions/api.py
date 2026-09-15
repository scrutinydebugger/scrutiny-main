#    api.py
#        Contains the definitions related to the datalogging feature on the API side. Shared
#        between the API and the DataloggingManager
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2023 Scrutiny Debugger

__all__ = [
    'XAxisType',
    'SamplingRate',
    'APIAcquisitionRequestCompletionCallback',
    'TriggerConditionID',
    'TriggerConditionOperandType',
    'TriggerConditionOperand',
    'TriggerCondition',
    'SignalDefinition',
    'SignalDefinitionWithAxis',
    'MathSignalDefinition',
    'MathSignalDefinitionWithAxis',
    'AcquisitionRequest',
    'AxisDefinition',
    'DataloggingAcquisition',
    'DataloggingState'
]

from enum import Enum
from dataclasses import dataclass

from scrutiny.core.datalogging import DataloggingAcquisition, AxisDefinition, DataloggingState
from scrutiny.core.basic_types import MathWatchable, Watchable
from scrutiny.server.device.device_info import ExecLoopType
from scrutiny.server.datastore.datastore_entry import DatastoreEntry
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.tools.typing import *


class XAxisType(Enum):
    """Represent a type of X-Axis that a user can select"""
    IdealTime = 0
    MeasuredTime = 1
    Signal = 2
    Indexed = 3


@dataclass(frozen=True, slots=True)
class SamplingRate:
    """Represent a sampling rate that a user can select"""
    name: str
    frequency: Optional[float]
    rate_type: ExecLoopType
    device_identifier: int


APIAcquisitionRequestCompletionCallback = Callable[[bool, str, Optional[DataloggingAcquisition]], None]

TriggerConditionID = device_datalogging.TriggerConditionID


class TriggerConditionOperandType(Enum):
    LITERAL = 0
    WATCHABLE = 1


@dataclass(frozen=True, slots=True)
class TriggerConditionOperand:
    type: TriggerConditionOperandType
    value: Union[float, int, bool, DatastoreEntry]


@dataclass(slots=True)
class TriggerCondition:
    condition_id: TriggerConditionID
    operands: List[TriggerConditionOperand]


@dataclass(frozen=True, slots=True)
class SignalDefinition:
    name: Optional[str]
    entry: DatastoreEntry


@dataclass(frozen=True, slots=True)
class MathSignalDefinition:
    name: str
    expr: str
    variables: Dict[str, DatastoreEntry]

    def to_core_math_watchable(self) -> MathWatchable:
        return MathWatchable(
            expr=self.expr,
            watchables={name: Watchable(type=entry.get_type(), path=entry.get_display_path()) for name, entry in self.variables.items()}
        )


@dataclass(frozen=True, slots=True)
class SignalDefinitionWithAxis(SignalDefinition):
    axis: AxisDefinition


@dataclass(frozen=True, slots=True)
class MathSignalDefinitionWithAxis(MathSignalDefinition):
    axis: AxisDefinition


@dataclass(slots=True)
class AcquisitionRequest:
    name: Optional[str]
    rate_identifier: int
    decimation: int
    timeout: float
    probe_location: float
    trigger_hold_time: float
    trigger_condition: TriggerCondition
    x_axis_type: XAxisType
    x_axis_signal: Optional[SignalDefinition]
    signals: List[Union[SignalDefinitionWithAxis, MathSignalDefinitionWithAxis]]

    def get_yaxis_list(self) -> List[AxisDefinition]:
        axis_set: Set[AxisDefinition] = set()
        for signal in self.signals:
            axis_set.add(signal.axis)

        return list(axis_set)
