"""Interactive editor canvas.

Provides a scaled overlay preview plus a full interaction layer on top of the
existing field rendering:

* Multi-select (click / shift-click / marquee-less empty-click to clear)
* 8 resize handles around the selection (single field or group bounding box)
* Solid drag-and-drop with semi-transparent preview and move cursor
* Smart alignment guides (red snap lines) against every other field
* Optional 5px snap-to-grid
* Live WxH tooltip while resizing

All field positions/sizes are stored in *design* (real output) coordinates.
The canvas scales those down to fit the widget; handle drawing happens in
widget/screen coordinates and interaction is converted back to design coords.
"""
from __future__ import annotations

from typing import List, Optional, Dict, Tuple

from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QCursor, QFont
from PyQt6.QtWidgets import QWidget

from .models import Field, TYPE_IMAGE
from . import render


# Handle indices (0..7) around a bounding box
#   0 TL   1 TM   2 TR
#   7 LM          3 RM
#   6 BL   5 BM   4 BR
_HANDLE_COUNT = 8
# For each handle: which edges it moves (left, top, right, bottom)
_HANDLE_EDGES = {
    0: (True, True, False, False),    # top-left
    1: (False, True, False, False),   # top-mid
    2: (False, True, True, False),    # top-right
    3: (False, False, True, False),   # right-mid
    4: (False, False, True, True),    # bottom-right
    5: (False, False, False, True),   # bottom-mid
    6: (True, False, False, True),    # bottom-left
    7: (True, False, False, False),   # left-mid
}
# Cursor shapes per handle
_HANDLE_CURSORS = {
    0: Qt.CursorShape.SizeFDiagCursor,
    1: Qt.CursorShape.SizeVerCursor,
    2: Qt.CursorShape.SizeBDiagCursor,
    3: Qt.CursorShape.SizeHorCursor,
    4: Qt.CursorShape.SizeFDiagCursor,
    5: Qt.CursorShape.SizeVerCursor,
    6: Qt.CursorShape.SizeBDiagCursor,
    7: Qt.CursorShape.SizeHorCursor,
}

HANDLE_PX = 10          # on-screen handle size (square side)
SNAP_TOLERANCE = 8      # design px tolerance for alignment snapping
GRID_SIZE = 5           # design px grid when snap-to-grid enabled
MIN_SIZE = 20           # minimum field width/height in design px


class EditorCanvas(QWidget):
    """Scaled overlay preview with select / move / resize / align tooling."""

    field_selected = pyqtSignal(object)   # primary Field or None
    field_moved = pyqtSignal(object)      # Field whose geometry changed
    field_changed = pyqtSignal()          # generic "something changed" request

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fields: List[Field] = []
        self.serial_values: Dict[str, str] = {}
        self.design_size = (1280, 1024)

        # selection is a list for multi-select; primary = last item
        self.selected_fields: List[Field] = []

        # interaction state
        self._mode: Optional[str] = None       # None | 'drag' | 'resize'
        self._active_handle: Optional[int] = None
        self._drag_start_design = QPointF(0, 0)
        self._orig_geom: Dict[str, Tuple[float, float, float, float, int]] = {}
        self._orig_bbox: Optional[Tuple[float, float, float, float]] = None
        self._press_pos = QPointF(0, 0)
        self._moved_since_press = False
        self.snap_to_grid = False

        # computed each paint
        self._field_rects: Dict[str, QRectF] = {}          # id -> widget rect
        self._field_design_rects: Dict[str, QRectF] = {}   # id -> design rect
        self._handle_rects: Dict[int, QRectF] = {}         # idx -> widget rect
        self._guides_v: List[float] = []   # widget x positions
        self._guides_h: List[float] = []   # widget y positions
        self._tooltip: Optional[Tuple[str, QPointF]] = None

        self.setMinimumSize(640, 512)
        self.setMouseTracking(True)
        self.setStyleSheet("background:#000;")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_fields(self, fields: List[Field]):
        self.fields = fields
        # drop stale selections
        self.selected_fields = [f for f in self.selected_fields if f in fields]
        self.update()

    def set_design_size(self, w: int, h: int):
        self.design_size = (w, h)
        self.update()

    def set_serial_values(self, values: Dict[str, str]):
        self.serial_values = values
        self.update()

    @property
    def selected(self) -> Optional[Field]:
        """Primary selected field (backwards-compatible single accessor)."""
        return self.selected_fields[-1] if self.selected_fields else None

    def select_field(self, f: Optional[Field]):
        """Select a single field (or clear with None)."""
        self.selected_fields = [f] if f is not None else []
        self.field_selected.emit(self.selected)
        self.update()

    def set_snap_to_grid(self, on: bool):
        self.snap_to_grid = bool(on)

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------
    def _scale(self) -> float:
        dw, dh = self.design_size
        return min(self.width() / dw, self.height() / dh)

    def _offset(self, scale) -> Tuple[float, float]:
        dw, dh = self.design_size
        ox = (self.width() - dw * scale) / 2
        oy = (self.height() - dh * scale) / 2
        return ox, oy

    def _to_widget(self, x: float, y: float) -> QPointF:
        scale = self._scale()
        ox, oy = self._offset(scale)
        return QPointF(ox + x * scale, oy + y * scale)

    def _to_design(self, px: float, py: float) -> QPointF:
        scale = self._scale()
        ox, oy = self._offset(scale)
        return QPointF((px - ox) / scale, (py - oy) / scale)

    def design_rect(self, f: Field) -> QRectF:
        """Return a field's bounding rect in design coordinates."""
        r = self._field_design_rects.get(f.id)
        if r is not None and r.width() > 0 and r.height() > 0:
            return QRectF(r)
        if f.type == TYPE_IMAGE:
            return QRectF(f.x, f.y, max(f.width, 1), max(f.height, 1))
        w, h = render.field_bounds(None, f, self.serial_values)
        return QRectF(f.x, f.y, max(w, 1), max(h, 1))

    def _selection_bbox(self) -> Optional[QRectF]:
        if not self.selected_fields:
            return None
        rects = [self.design_rect(f) for f in self.selected_fields]
        left = min(r.left() for r in rects)
        top = min(r.top() for r in rects)
        right = max(r.right() for r in rects)
        bottom = max(r.bottom() for r in rects)
        return QRectF(left, top, right - left, bottom - top)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(self.rect(), QColor(20, 20, 20))

        scale = self._scale()
        ox, oy = self._offset(scale)
        dw, dh = self.design_size

        painter.save()
        painter.translate(ox, oy)
        painter.scale(scale, scale)
        painter.fillRect(QRectF(0, 0, dw, dh), QColor(0, 0, 0))
        painter.setPen(QPen(QColor(60, 60, 90), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, dw, dh))

        self._field_rects = {}
        self._field_design_rects = {}
        for f in self.fields:
            is_dragged = (self._mode == 'drag' and f in self.selected_fields)
            if is_dragged:
                painter.setOpacity(0.55)
            rect = render.paint_field(painter, f, self.serial_values)
            if is_dragged:
                painter.setOpacity(1.0)
            drect = QRectF(rect.x(), rect.y(),
                           max(rect.width(), 10), max(rect.height(), 10))
            self._field_design_rects[f.id] = drect
            wr = QRectF(ox + drect.x() * scale, oy + drect.y() * scale,
                        drect.width() * scale, drect.height() * scale)
            self._field_rects[f.id] = wr
        painter.restore()

        # Alignment guide lines (widget coords, drawn across whole design area)
        if self._mode == 'drag' and (self._guides_v or self._guides_h):
            gpen = QPen(QColor(255, 45, 45), 1)
            painter.setPen(gpen)
            top = oy
            bottom = oy + dh * scale
            left = ox
            right = ox + dw * scale
            for gx in self._guides_v:
                painter.drawLine(QPointF(gx, top), QPointF(gx, bottom))
            for gy in self._guides_h:
                painter.drawLine(QPointF(left, gy), QPointF(right, gy))

        # Selection outline + handles
        bbox = self._selection_bbox()
        if bbox is not None:
            tl = self._to_widget(bbox.left(), bbox.top())
            br = self._to_widget(bbox.right(), bbox.bottom())
            wrect = QRectF(tl, br)

            # individual outlines when multiple selected
            if len(self.selected_fields) > 1:
                painter.setPen(QPen(QColor(0, 160, 255, 140), 1, Qt.PenStyle.DotLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for f in self.selected_fields:
                    dr = self.design_rect(f)
                    a = self._to_widget(dr.left(), dr.top())
                    b = self._to_widget(dr.right(), dr.bottom())
                    painter.drawRect(QRectF(a, b))

            painter.setPen(QPen(QColor(0, 160, 255), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(wrect.adjusted(-2, -2, 2, 2))

            # 8 handles
            self._handle_rects = self._compute_handle_rects(wrect)
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setBrush(QBrush(QColor(0, 140, 255)))
            for hr in self._handle_rects.values():
                painter.drawRect(hr)
        else:
            self._handle_rects = {}

        # Resize tooltip
        if self._tooltip is not None:
            text, pos = self._tooltip
            painter.setFont(QFont("Arial", 9))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(text) + 10
            th = fm.height() + 6
            tx = min(pos.x() + 14, self.width() - tw - 2)
            ty = max(pos.y() - th - 6, 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 200))
            painter.drawRect(QRectF(tx, ty, tw, th))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(QRectF(tx, ty, tw, th),
                             Qt.AlignmentFlag.AlignCenter, text)

        painter.end()

    def _compute_handle_rects(self, wrect: QRectF) -> Dict[int, QRectF]:
        hs = HANDLE_PX
        cx = wrect.center().x()
        cy = wrect.center().y()
        pts = {
            0: (wrect.left(), wrect.top()),
            1: (cx, wrect.top()),
            2: (wrect.right(), wrect.top()),
            3: (wrect.right(), cy),
            4: (wrect.right(), wrect.bottom()),
            5: (cx, wrect.bottom()),
            6: (wrect.left(), wrect.bottom()),
            7: (wrect.left(), cy),
        }
        return {i: QRectF(x - hs / 2, y - hs / 2, hs, hs)
                for i, (x, y) in pts.items()}

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------
    def _handle_at(self, pos: QPointF) -> Optional[int]:
        for i, hr in self._handle_rects.items():
            if hr.adjusted(-3, -3, 3, 3).contains(pos):
                return i
        return None

    def _field_at(self, pos: QPointF) -> Optional[Field]:
        for f in reversed(self.fields):      # top-most first
            r = self._field_rects.get(f.id)
            if r and r.adjusted(-3, -3, 3, 3).contains(pos):
                return f
        return None

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        self._press_pos = pos
        self._moved_since_press = False

        # 1) a resize handle?
        if self.selected_fields:
            h = self._handle_at(pos)
            if h is not None:
                self._begin_resize(h, pos)
                return

        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        f = self._field_at(pos)

        if f is None:
            if not shift:
                self.select_field(None)
            return

        if shift:
            if f in self.selected_fields:
                self.selected_fields.remove(f)
            else:
                self.selected_fields.append(f)
            self.field_selected.emit(self.selected)
            self.update()
            # allow dragging the group right away if still selected
            if f in self.selected_fields:
                self._begin_drag(pos)
            return

        # plain click: if already part of a multi-selection keep it (move group)
        if f not in self.selected_fields:
            self.selected_fields = [f]
            self.field_selected.emit(self.selected)
        self._begin_drag(pos)
        self.update()

    def _begin_drag(self, pos: QPointF):
        self._mode = 'drag'
        self._drag_start_design = self._to_design(pos.x(), pos.y())
        self._capture_orig_geom()

    def _begin_resize(self, handle: int, pos: QPointF):
        self._mode = 'resize'
        self._active_handle = handle
        self._capture_orig_geom()
        bbox = self._selection_bbox()
        if bbox is not None:
            self._orig_bbox = (bbox.left(), bbox.top(),
                               bbox.right(), bbox.bottom())

    def _capture_orig_geom(self):
        self._orig_geom = {}
        for f in self.selected_fields:
            dr = self.design_rect(f)
            self._orig_geom[f.id] = (float(f.x), float(f.y),
                                     dr.width(), dr.height(),
                                     int(f.font_size))

    def mouseMoveEvent(self, event):
        pos = event.position()

        if self._mode == 'drag':
            self._moved_since_press = True
            self._do_drag(pos)
            return
        if self._mode == 'resize':
            self._moved_since_press = True
            self._do_resize(pos)
            return

        # hover: update cursor
        self._update_hover_cursor(pos)

    def _update_hover_cursor(self, pos: QPointF):
        if self.selected_fields:
            h = self._handle_at(pos)
            if h is not None:
                self.setCursor(QCursor(_HANDLE_CURSORS[h]))
                return
        if self._field_at(pos) is not None:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    # ------------------------------------------------------------------
    # Drag logic (with alignment snapping)
    # ------------------------------------------------------------------
    def _do_drag(self, pos: QPointF):
        if not self.selected_fields:
            return
        cur = self._to_design(pos.x(), pos.y())
        dx = cur.x() - self._drag_start_design.x()
        dy = cur.y() - self._drag_start_design.y()

        # proposed new positions
        new_pos = {}
        for f in self.selected_fields:
            ox, oy, _, _, _ = self._orig_geom[f.id]
            new_pos[f.id] = [ox + dx, oy + dy]

        # group bbox at proposed position
        rects = []
        for f in self.selected_fields:
            ox, oy, w, h, _ = self._orig_geom[f.id]
            nx, ny = new_pos[f.id]
            rects.append((nx, ny, w, h))
        g_left = min(r[0] for r in rects)
        g_top = min(r[1] for r in rects)
        g_right = max(r[0] + r[2] for r in rects)
        g_bottom = max(r[1] + r[3] for r in rects)
        g_cx = (g_left + g_right) / 2
        g_cy = (g_top + g_bottom) / 2

        # snap against other fields
        snap_dx, guide_xs = self._compute_snap_x(g_left, g_cx, g_right)
        snap_dy, guide_ys = self._compute_snap_y(g_top, g_cy, g_bottom)

        if snap_dx is not None:
            dx += snap_dx
        if snap_dy is not None:
            dy += snap_dy

        # grid snap (only if no alignment snap took over that axis)
        dw, dh = self.design_size
        for f in self.selected_fields:
            ox, oy, w, h, _ = self._orig_geom[f.id]
            nx = ox + dx
            ny = oy + dy
            if self.snap_to_grid:
                if snap_dx is None:
                    nx = round(nx / GRID_SIZE) * GRID_SIZE
                if snap_dy is None:
                    ny = round(ny / GRID_SIZE) * GRID_SIZE
            nx = max(0, min(dw, nx))
            ny = max(0, min(dh, ny))
            f.x = int(round(nx))
            f.y = int(round(ny))

        # convert guide design coords -> widget coords for drawing
        self._guides_v = [self._to_widget(gx, 0).x() for gx in guide_xs]
        self._guides_h = [self._to_widget(0, gy).y() for gy in guide_ys]

        self.field_moved.emit(self.selected)
        self.update()

    def _other_rects(self) -> List[QRectF]:
        sel_ids = {f.id for f in self.selected_fields}
        return [self.design_rect(f) for f in self.fields
                if f.id not in sel_ids and f.visible]

    def _compute_snap_x(self, left, cx, right):
        """Return (delta_x_to_apply, [guide design x positions])."""
        best = None
        guides = []
        candidates = []   # (edge_value, design_x_target)
        for r in self._other_rects():
            for tx in (r.left(), r.center().x(), r.right()):
                for ev in (left, cx, right):
                    d = tx - ev
                    if abs(d) <= SNAP_TOLERANCE:
                        candidates.append((abs(d), d, tx))
        if candidates:
            candidates.sort(key=lambda c: c[0])
            best = candidates[0][1]
            snap_target = candidates[0][2]
            # collect all guides at the chosen snap distance
            for ad, d, tx in candidates:
                if abs(d - best) < 0.5:
                    guides.append(tx)
            guides = sorted(set(guides))
            return best, guides
        return None, []

    def _compute_snap_y(self, top, cy, bottom):
        best = None
        guides = []
        candidates = []
        for r in self._other_rects():
            for ty in (r.top(), r.center().y(), r.bottom()):
                for ev in (top, cy, bottom):
                    d = ty - ev
                    if abs(d) <= SNAP_TOLERANCE:
                        candidates.append((abs(d), d, ty))
        if candidates:
            candidates.sort(key=lambda c: c[0])
            best = candidates[0][1]
            for ad, d, ty in candidates:
                if abs(d - best) < 0.5:
                    guides.append(ty)
            guides = sorted(set(guides))
            return best, guides
        return None, []

    # ------------------------------------------------------------------
    # Resize logic
    # ------------------------------------------------------------------
    def _do_resize(self, pos: QPointF):
        if self._orig_bbox is None or self._active_handle is None:
            return
        ox0, oy0, ox1, oy1 = self._orig_bbox
        m = self._to_design(pos.x(), pos.y())
        ml, mt, mr, mb = _HANDLE_EDGES[self._active_handle]

        nx0, ny0, nx1, ny1 = ox0, oy0, ox1, oy1
        if ml:
            nx0 = m.x()
        if mr:
            nx1 = m.x()
        if mt:
            ny0 = m.y()
        if mb:
            ny1 = m.y()

        # keep proper ordering + minimum size, anchored on the fixed edge
        if nx1 - nx0 < MIN_SIZE:
            if ml:
                nx0 = nx1 - MIN_SIZE
            else:
                nx1 = nx0 + MIN_SIZE
        if ny1 - ny0 < MIN_SIZE:
            if mt:
                ny0 = ny1 - MIN_SIZE
            else:
                ny1 = ny0 + MIN_SIZE

        ow = max(ox1 - ox0, 1e-6)
        oh = max(oy1 - oy0, 1e-6)
        sx = (nx1 - nx0) / ow if (ml or mr) else 1.0
        sy = (ny1 - ny0) / oh if (mt or mb) else 1.0

        # anchor = the edge that stays put
        anchor_x = ox1 if ml else ox0
        anchor_y = oy1 if mt else oy0
        new_anchor_x = nx1 if ml else nx0
        new_anchor_y = ny1 if mt else ny0

        for f in self.selected_fields:
            fx, fy, fw, fh, ofs = self._orig_geom[f.id]
            # map top-left through the scale about the anchor
            f.x = int(round(new_anchor_x + (fx - anchor_x) * sx))
            f.y = int(round(new_anchor_y + (fy - anchor_y) * sy))
            if f.type == TYPE_IMAGE:
                f.width = max(MIN_SIZE, int(round(fw * sx)))
                f.height = max(MIN_SIZE, int(round(fh * sy)))
            else:
                # text: auto-adjust font size (uniform), record box size
                scale_font = sy if (mt or mb) else sx
                if (ml or mr) and (mt or mb):
                    scale_font = min(sx, sy)
                new_fs = max(6, int(round(ofs * scale_font)))
                f.font_size = new_fs
                f.width = max(MIN_SIZE, int(round(fw * sx)))
                f.height = max(MIN_SIZE, int(round(fh * sy)))

        # tooltip shows the resulting bbox size
        bw = int(round(nx1 - nx0))
        bh = int(round(ny1 - ny0))
        self._tooltip = (f"{bw} x {bh}", pos)

        render.clear_pixmap_cache()
        self.field_moved.emit(self.selected)
        self.update()

    # ------------------------------------------------------------------
    def mouseReleaseEvent(self, event):
        was = self._mode
        self._mode = None
        self._active_handle = None
        self._orig_bbox = None
        self._guides_v = []
        self._guides_h = []
        self._tooltip = None
        if was in ('drag', 'resize'):
            self.field_changed.emit()
        self.update()

    # ------------------------------------------------------------------
    # Alignment / distribution operations (operate on selected_fields)
    # ------------------------------------------------------------------
    def _apply_positions(self):
        render.clear_pixmap_cache()
        self.field_changed.emit()
        self.update()

    def align_left(self):
        if len(self.selected_fields) < 2:
            return
        target = min(self.design_rect(f).left() for f in self.selected_fields)
        for f in self.selected_fields:
            f.x = int(round(target))
        self._apply_positions()

    def align_right(self):
        if len(self.selected_fields) < 2:
            return
        target = max(self.design_rect(f).right() for f in self.selected_fields)
        for f in self.selected_fields:
            w = self.design_rect(f).width()
            f.x = int(round(target - w))
        self._apply_positions()

    def align_top(self):
        if len(self.selected_fields) < 2:
            return
        target = min(self.design_rect(f).top() for f in self.selected_fields)
        for f in self.selected_fields:
            f.y = int(round(target))
        self._apply_positions()

    def align_bottom(self):
        if len(self.selected_fields) < 2:
            return
        target = max(self.design_rect(f).bottom() for f in self.selected_fields)
        for f in self.selected_fields:
            h = self.design_rect(f).height()
            f.y = int(round(target - h))
        self._apply_positions()

    def center_horizontal(self):
        """Center each selected field horizontally within the canvas."""
        if not self.selected_fields:
            return
        dw, _ = self.design_size
        for f in self.selected_fields:
            w = self.design_rect(f).width()
            f.x = int(round((dw - w) / 2))
        self._apply_positions()

    def center_vertical(self):
        if not self.selected_fields:
            return
        _, dh = self.design_size
        for f in self.selected_fields:
            h = self.design_rect(f).height()
            f.y = int(round((dh - h) / 2))
        self._apply_positions()

    def distribute_h(self):
        if len(self.selected_fields) < 3:
            return
        items = sorted(self.selected_fields,
                       key=lambda f: self.design_rect(f).left())
        left = self.design_rect(items[0]).left()
        right = self.design_rect(items[-1]).right()
        total_w = sum(self.design_rect(f).width() for f in items)
        gap = (right - left - total_w) / (len(items) - 1)
        cursor = left
        for f in items:
            f.x = int(round(cursor))
            cursor += self.design_rect(f).width() + gap
        self._apply_positions()

    def distribute_v(self):
        if len(self.selected_fields) < 3:
            return
        items = sorted(self.selected_fields,
                       key=lambda f: self.design_rect(f).top())
        top = self.design_rect(items[0]).top()
        bottom = self.design_rect(items[-1]).bottom()
        total_h = sum(self.design_rect(f).height() for f in items)
        gap = (bottom - top - total_h) / (len(items) - 1)
        cursor = top
        for f in items:
            f.y = int(round(cursor))
            cursor += self.design_rect(f).height() + gap
        self._apply_positions()
