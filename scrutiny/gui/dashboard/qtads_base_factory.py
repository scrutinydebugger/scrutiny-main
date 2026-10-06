import PySide6QtAds as QtAds
import shiboken6
from scrutiny.tools.typing import *

class QtADSBaseFactory(QtAds.CDockComponentsFactory):
    instance:Any

    @classmethod
    def make(cls) -> Self:
        # The goal of this helper is to keep the factory
        # alive in Python until it is deleted by the dock manager
        # otherwise double free can happen in the dockmanager destructor.
        if not hasattr(cls, 'instance'):
            cls.instance = cls()
        elif not shiboken6.isValid(cls.instance):
            cls.instance = cls()
        return cls.instance # type: ignore
