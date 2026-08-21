"""Application services and protocols."""

from .protocols import AutomationBackend, StatusProvider
from .task_manager import TaskManager

__all__ = ["AutomationBackend", "StatusProvider", "TaskManager"]
