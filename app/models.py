"""Data models for the ROV Video Overlay application.

Defines the Field and Profile data structures plus JSON (de)serialisation.
The design coordinate space is the overlay output resolution (default
1280 x 1024). Every field X/Y is stored in that coordinate space so that
profiles are independent of the preview scale.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

# ---------------------------------------------------------------------------
# Field type constants (mirror the legacy .ovl FType numbers)
# ---------------------------------------------------------------------------
TYPE_STATIC = "static_text"   # legacy 1
TYPE_DATE = "date"            # legacy 2
TYPE_TIME = "time"            # legacy 3
TYPE_SERIAL = "serial_data"   # legacy 4
TYPE_IMAGE = "image"          # legacy 5
TYPE_TEXTFILE = "text_file"   # legacy 6

LEGACY_TYPE_MAP = {
    "1": TYPE_STATIC,
    "2": TYPE_DATE,
    "3": TYPE_TIME,
    "4": TYPE_SERIAL,
    "5": TYPE_IMAGE,
    "6": TYPE_TEXTFILE,
}
TYPE_TO_LEGACY = {v: k for k, v in LEGACY_TYPE_MAP.items()}

# Label positions
LABEL_NONE = "none"
LABEL_LEFT = "left"
LABEL_RIGHT = "right"
LABEL_ABOVE = "above"
LABEL_BELOW = "below"

# legacy LabelPos number -> our label position string
LEGACY_LABELPOS_MAP = {
    "1": LABEL_LEFT,
    "2": LABEL_RIGHT,
    "3": LABEL_ABOVE,
    "4": LABEL_BELOW,
    "0": LABEL_NONE,
}
LABELPOS_TO_LEGACY = {v: k for k, v in LEGACY_LABELPOS_MAP.items()}

# The mappable live serial fields.
SERIAL_FIELDS = [
    "EAST", "NORTH", "HEADING", "DEPTH", "ALTITUDE", "KP", "CP",
    "LAT", "LONG", "PITCH", "ROLL", "DCC",
]

DEFAULT_RESOLUTION = (1280, 1024)


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class Field:
    """A single overlay element."""
    name: str = "Field"
    type: str = TYPE_STATIC
    value: str = ""               # current value OR format string
    label: str = ""
    label_position: str = LABEL_LEFT
    x: int = 100
    y: int = 100
    visible: bool = True

    font_name: str = "Arial"
    font_size: int = 26
    font_color: List[int] = field(default_factory=lambda: [255, 255, 0])   # RGB
    bold: bool = True

    label_font_size: int = 20
    label_color: List[int] = field(default_factory=lambda: [255, 255, 255])

    bg_enabled: bool = False
    bg_color: List[int] = field(default_factory=lambda: [0, 0, 0])

    # Serial-specific
    serial_field: str = ""        # one of SERIAL_FIELDS
    format_string: str = "#0.00"  # number format

    # Image-specific
    image_path: str = ""
    width: int = 150
    height: int = 80

    # Internal, non-persistent runtime value (resolved live value shown on screen)
    id: str = field(default_factory=_new_id)

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Field":
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in d.items() if k in allowed}
        if "id" not in clean:
            clean["id"] = _new_id()
        return cls(**clean)


@dataclass
class SerialStringFormat:
    """A single user-defined serial string format rule."""
    name: str = "Default"
    prefix: str = "$NAV"
    delimiter: str = ","
    # ordered list of mapped names, one per comma position (may be "IGNORE")
    field_map: List[str] = field(default_factory=list)
    raw_format: str = ""   # the raw format text the user typed

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SerialStringFormat":
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in allowed})


@dataclass
class SerialConfig:
    port: str = ""
    baud: int = 9600
    formats: List[SerialStringFormat] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "port": self.port,
            "baud": self.baud,
            "formats": [f.to_dict() for f in self.formats],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SerialConfig":
        formats = [SerialStringFormat.from_dict(f) for f in d.get("formats", [])]
        if not formats:
            # Back-compat with the simple single-format schema
            fm = d.get("field_map", {})
            if isinstance(fm, dict):
                # convert {"0":"EAST"} -> ordered list
                ordered = []
                for i in range(len(fm)):
                    ordered.append(fm.get(str(i), "IGNORE"))
                field_list = ordered
            else:
                field_list = list(fm)
            formats = [SerialStringFormat(
                name="Default",
                prefix=d.get("prefix", "$NAV"),
                delimiter=d.get("delimiter", ","),
                field_map=field_list,
            )]
        return cls(port=d.get("port", ""), baud=int(d.get("baud", 9600)), formats=formats)


@dataclass
class Profile:
    profile_name: str = "New Profile"
    client: str = ""
    job_type: str = "GVI"
    vessel: str = ""
    rov: str = ""
    contractor: str = "DEEPTECH"
    resolution: List[int] = field(default_factory=lambda: list(DEFAULT_RESOLUTION))
    serial: SerialConfig = field(default_factory=SerialConfig)
    fields: List[Field] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_name": self.profile_name,
            "client": self.client,
            "job_type": self.job_type,
            "vessel": self.vessel,
            "rov": self.rov,
            "contractor": self.contractor,
            "resolution": list(self.resolution),
            "serial": self.serial.to_dict(),
            "fields": [f.to_dict() for f in self.fields],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Profile":
        return cls(
            profile_name=d.get("profile_name", "New Profile"),
            client=d.get("client", ""),
            job_type=d.get("job_type", "GVI"),
            vessel=d.get("vessel", ""),
            rov=d.get("rov", ""),
            contractor=d.get("contractor", "DEEPTECH"),
            resolution=d.get("resolution", list(DEFAULT_RESOLUTION)),
            serial=SerialConfig.from_dict(d.get("serial", {})),
            fields=[Field.from_dict(f) for f in d.get("fields", [])],
        )

    @classmethod
    def from_json(cls, text: str) -> "Profile":
        return cls.from_dict(json.loads(text))

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    @classmethod
    def load(cls, path: str) -> "Profile":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_json(fh.read())
