"""Import and export of the legacy .ovl profile format.

Legacy .ovl layout (delimited by ``#$#``):
    Line 1: PORT #$# BAUD #$# PREFIX #$# DELIMITER
    Line 2: column index header (1..19)
    Line 3: column name header
    Line 4+: one field per line, 19 columns:
        FName, FType, FValue, HasLabel, Label, LabelPos, FHPos, FVPos,
        Fvisible, FontName, FFont, FontColor, LFont, LFontColor,
        FBgnd, FBgndC, LBgnd, LBgndC, Fields

FType: 1=static 2=date 3=time 4=serial 5=image 6=text_file
For image rows (FType 5) FFont stores the image width and LFont the height.
The "Fields" column (last) stores the 1-based serial position used by the
legacy app for serial fields.
"""
from __future__ import annotations

import os
from typing import List, Optional

from .models import (
    Field, Profile, SerialConfig, SerialStringFormat,
    LEGACY_TYPE_MAP, LEGACY_LABELPOS_MAP, TYPE_IMAGE, TYPE_SERIAL,
    TYPE_TEXTFILE, TYPE_TO_LEGACY, LABELPOS_TO_LEGACY,
    TYPE_STATIC, TYPE_DATE, TYPE_TIME,
)

DELIM = "#$#"

# Legacy colour codes seen in the sample files are VB list indexes and cannot
# be decoded exactly. We map the common ones to sensible broadcast colours and
# default everything else to white. All colours remain fully editable in the UI.
LEGACY_COLOR_MAP = {
    "164": [255, 255, 255],   # white  (labels / static)
    "166": [255, 255, 0],     # yellow (live serial values)
    "150": [255, 255, 255],
    "78": [0, 0, 0],          # background black
    "16": [255, 255, 255],
    "35": [0, 90, 160],       # dark blue background accent
    "0": [255, 255, 255],
    "217": [255, 255, 255],
    "114": [255, 255, 255],
}

# The legacy serial position (last column) maps a field onto a $NAV position.
# From analysis of the sample profiles: 2=EAST 3=NORTH 4=KP 5=HEADING
# 6=DCC 7=ALTITUDE 8=DEPTH 9=CP. Position 1 is the prefix token.
LEGACY_SERIAL_POSITION = {
    "2": "EAST",
    "3": "NORTH",
    "4": "KP",
    "5": "HEADING",
    "6": "DCC",
    "7": "ALTITUDE",
    "8": "DEPTH",
    "9": "CP",
    "10": "LAT",
    "11": "LONG",
    "12": "PITCH",
    "13": "ROLL",
}

# Reverse, for serial_field -> position
SERIAL_FIELD_TO_POSITION = {v: k for k, v in LEGACY_SERIAL_POSITION.items()}


def _color(code: str) -> List[int]:
    return list(LEGACY_COLOR_MAP.get(code.strip(), [255, 255, 255]))


def _to_int(v: str, default: int = 0) -> int:
    try:
        return int(float(v.strip()))
    except (ValueError, AttributeError):
        return default


def import_ovl(path: str) -> Profile:
    """Parse a legacy .ovl file and return a Profile."""
    with open(path, "r", encoding="latin-1") as fh:
        lines = [ln.rstrip("\n").rstrip("\r") for ln in fh if ln.strip()]

    if not lines:
        raise ValueError("Empty .ovl file")

    header = lines[0].split(DELIM)
    port = header[0].strip() if len(header) > 0 else ""
    baud = _to_int(header[1], 9600) if len(header) > 1 else 9600
    prefix = header[2].strip() if len(header) > 2 else "$NAV"
    delimiter = header[3] if len(header) > 3 else ","
    if delimiter == "":
        delimiter = ","

    fields: List[Field] = []
    max_position = 0

    # Field rows start after the two header lines (index 1 and 2)
    for line in lines[3:]:
        cols = line.split(DELIM)
        if len(cols) < 9:
            continue
        # pad to 19
        while len(cols) < 19:
            cols.append("0")

        fname = cols[0].strip()
        ftype = LEGACY_TYPE_MAP.get(cols[1].strip(), TYPE_STATIC)
        fvalue = cols[2]
        has_label = cols[3].strip() == "1"
        label = cols[4]
        label_pos = LEGACY_LABELPOS_MAP.get(cols[5].strip(), "left")
        x = _to_int(cols[6], 0)
        y = _to_int(cols[7], 0)
        visible = cols[8].strip() == "1"
        font_name = cols[9].strip() or "Arial"
        ffont = _to_int(cols[10], 26)
        font_color = _color(cols[11])
        lfont = _to_int(cols[12], 16)
        label_color = _color(cols[13])
        bg_enabled = cols[14].strip() == "1"
        bg_color = _color(cols[15])
        serial_pos = cols[18].strip() if len(cols) > 18 else "0"

        f = Field(
            name=fname,
            type=ftype,
            value=fvalue,
            label=label if has_label else label,  # keep label text regardless
            label_position=label_pos if has_label else "none",
            x=x, y=y,
            visible=visible,
            font_name=font_name,
            font_size=ffont,
            font_color=font_color,
            label_font_size=lfont,
            label_color=label_color,
            bg_enabled=bg_enabled,
            bg_color=bg_color,
        )

        if ftype == TYPE_IMAGE:
            # FFont col = width, LFont col = height, FValue = path
            f.width = ffont
            f.height = lfont
            f.image_path = fvalue
            f.font_size = 26
            # try to relocate logo path to local resources folder by filename
            f.image_path = _localize_logo(fvalue)
        elif ftype == TYPE_SERIAL:
            f.serial_field = LEGACY_SERIAL_POSITION.get(serial_pos, _guess_serial_field(fname))
            f.format_string = fvalue or "#0.00"
            if serial_pos.isdigit():
                max_position = max(max_position, int(serial_pos))
        elif ftype == TYPE_TEXTFILE:
            f.value = fvalue  # path to text file

        fields.append(f)

    # Build the field_map (ordered list by position) for the serial format
    field_map: List[str] = ["IGNORE"] * (max_position + 1 if max_position else 0)
    if field_map:
        field_map[0] = "PREFIX"
    for f in fields:
        if f.type == TYPE_SERIAL and f.serial_field:
            pos = SERIAL_FIELD_TO_POSITION.get(f.serial_field)
            if pos and pos.isdigit() and int(pos) < len(field_map):
                field_map[int(pos)] = f.serial_field

    raw_format = delimiter.join([prefix] + [m for m in field_map[1:]]) if field_map else prefix

    serial_fmt = SerialStringFormat(
        name="Imported",
        prefix=prefix,
        delimiter=delimiter,
        field_map=field_map,
        raw_format=raw_format,
    )
    serial_cfg = SerialConfig(port=port, baud=baud, formats=[serial_fmt])

    name = os.path.splitext(os.path.basename(path))[0]
    client, job = _infer_meta(name, fields)

    return Profile(
        profile_name=name,
        client=client,
        job_type=job,
        vessel=_find_custom(fields, "VESSEL") or "",
        rov=_find_custom(fields, "ROV") or "",
        contractor="DEEPTECH",
        serial=serial_cfg,
        fields=fields,
    )


def _guess_serial_field(name: str) -> str:
    n = name.upper()
    mapping = {
        "EAST": "EAST", "NORTH": "NORTH", "HEAD": "HEADING", "DEPTH": "DEPTH",
        "ALT": "ALTITUDE", "KP": "KP", "CP": "CP", "LAT": "LAT", "LONG": "LONG",
        "PITCH": "PITCH", "ROLL": "ROLL", "DCC": "DCC",
    }
    for key, val in mapping.items():
        if key in n:
            return val
    return ""


def _localize_logo(original_path: str) -> str:
    """Convert an absolute Windows logo path to a bundled resource filename."""
    base = os.path.basename(original_path.replace("\\", "/"))
    return base  # resolved at render time against the logos directory


def _infer_meta(name: str, fields: List[Field]):
    n = name.upper()
    client = ""
    for c in ["BP", "BURULLUS", "PHPC", "MCS", "ESSO", "TP"]:
        if c in n:
            client = c
            break
    job = "GVI"
    for j, key in [("Intervention", "INTERVENTION"), ("Drill Support", "DRILL"),
                   ("Pipeline Survey", "PIPELINE"), ("EMAT", "EMAT"),
                   ("GVI", "GVI")]:
        if key in n:
            job = j
            break
    return client, job


def _find_custom(fields: List[Field], keyword: str) -> Optional[str]:
    for f in fields:
        if keyword.upper() in f.label.upper() and f.value.strip():
            return f.value.strip()
    return None


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_ovl(profile: Profile, path: str) -> None:
    """Write a Profile back to the legacy .ovl format."""
    fmt = profile.serial.formats[0] if profile.serial.formats else SerialStringFormat()
    lines = []
    lines.append(DELIM.join([
        profile.serial.port or "COM1",
        str(profile.serial.baud),
        fmt.prefix or "$NAV",
        fmt.delimiter or ",",
    ]))
    lines.append(DELIM.join(str(i) for i in range(1, 20)))
    lines.append(DELIM.join([
        "FName", "FType", "FValue", "HasLabel", "Label", "LabelPos",
        "FHPos", "FVPos", "Fvisible", "FontName", "FFont", "FontColor",
        "LFont", "FontColor", "FBgnd", "FBgndC", "LBgnd", "LBgndC", "Fields",
    ]))

    for f in profile.fields:
        has_label = "1" if (f.label and f.label_position != "none") else "0"
        label_pos = LABELPOS_TO_LEGACY.get(f.label_position, "1")
        if f.type == TYPE_IMAGE:
            ffont = str(f.width)
            lfont = str(f.height)
            fvalue = f.image_path
        else:
            ffont = str(f.font_size)
            lfont = str(f.label_font_size)
            fvalue = f.value
        serial_pos = SERIAL_FIELD_TO_POSITION.get(f.serial_field, "0") if f.type == TYPE_SERIAL else "0"
        row = [
            f.name,
            TYPE_TO_LEGACY.get(f.type, "1"),
            fvalue,
            has_label,
            f.label,
            label_pos,
            str(int(f.x)),
            str(int(f.y)),
            "1" if f.visible else "0",
            f.font_name,
            ffont,
            "166" if f.type == TYPE_SERIAL else "164",
            lfont,
            "164",
            "1" if f.bg_enabled else "0",
            "78" if f.bg_enabled else "0",
            "0",
            "0",
            serial_pos,
        ]
        lines.append(DELIM.join(row))

    with open(path, "w", encoding="latin-1", errors="replace") as fh:
        fh.write("\n".join(lines))
