from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional
import re

@dataclass
class ChatMessage:
    """Represents a message in the chat history."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    # Example validation (could be more robust)
    def __post_init__(self):
        if self.role not in ["user", "assistant", "system", "tool"]:
            raise ValueError(f"Invalid role: {self.role}. Must be one of 'user', 'assistant', 'system', 'tool'.")

@dataclass
class ResourceMetric:
    """Represents a specific resource metric datapoint."""
    resource_id: str
    metric_name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    unit: Optional[str] = None
    # Example validation
    def __post_init__(self):
        if not isinstance(self.value, (int, float)):
             raise ValueError(f"Invalid value type: {type(self.value)}. Must be numeric.")

@dataclass
class Alert:
    """Represents an alert generated based on metrics."""
    resource_id: str
    alert_type: str
    severity: Literal["info", "warning", "critical"]
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    # Example validation
    def __post_init__(self):
        if self.severity not in ["info", "warning", "critical"]:
            raise ValueError(f"Invalid severity: {self.severity}. Must be one of 'info', 'warning', 'critical'.") 