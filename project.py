# project.py – Project model helper

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Project:
    project_id: str
    project_name: str
    project_desc: str = ""
    members_list: List[str] = field(default_factory=list)
    num_of_hardware_sets: int = 0
    hardware_set_id: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "project_desc": self.project_desc,
            "members_list": list(self.members_list),
            "num_of_hardware_sets": int(self.num_of_hardware_sets or 0),
            "hardware_set_id": list(self.hardware_set_id),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        project_id = (data.get("project_id") or "").strip()
        project_name = (data.get("project_name") or "").strip()
        project_desc = (data.get("project_desc") or "").strip()

        members = data.get("members_list") or []
        if isinstance(members, str):
            members = [m.strip() for m in members.split(",") if m.strip()]

        hw = data.get("hardware_set_id") or []
        if isinstance(hw, str):
            hw = [h.strip() for h in hw.split(",") if h.strip()]

        num_hw = data.get("num_of_hardware_sets")
        try:
            num_of_hardware_sets = int(num_hw) if num_hw is not None else len(hw)
        except (TypeError, ValueError):
            num_of_hardware_sets = len(hw)

        return cls(
            project_id=project_id,
            project_name=project_name,
            project_desc=project_desc,
            members_list=list(members),
            num_of_hardware_sets=num_of_hardware_sets,
            hardware_set_id=list(hw),
        )
