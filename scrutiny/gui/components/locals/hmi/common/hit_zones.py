#    hit_zones.py
#        Hit test logic for various shapes. Contains shared logic between HMI widgets
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from dataclasses import dataclass
from PySide6.QtCore import QPointF, QRectF

__all__ = ['BaseHitZone', 'EllipseHitZone', 'RectHitZone']


class BaseHitZone:
    def hit_test(self, pos: QPointF) -> bool:
        raise NotImplementedError("Virtual method")


@dataclass(slots=True)
class EllipseHitZone(BaseHitZone):
    center: QPointF
    radius_w: float
    radius_h: float

    def hit_test(self, pos: QPointF) -> bool:
        if self.radius_w <= 0 or self.radius_h <= 0:
            return False

        term1 = (pos.x() - self.center.x())**2 / self.radius_w**2
        term2 = (pos.y() - self.center.y())**2 / self.radius_h**2
        return (term1 + term2 <= 1)


@dataclass(slots=True)
class RectHitZone(BaseHitZone):
    rect: QRectF

    def hit_test(self, pos: QPointF) -> bool:
        return self.rect.contains(pos)
