from enum import Enum
from dataclasses import dataclass
from typing import Optional


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GPUInfo:
    index: int
    name: str
    memory_used: int
    memory_total: int
    utilization: int
    status: str  # "idle" | "busy" | "error"

    @property
    def is_idle(self) -> bool:
        return self.status == "idle"


@dataclass
class TaskAssignment:
    task_id: int
    server: str
    gpu_ids: list[int]
