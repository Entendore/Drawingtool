import sys
import math
import os
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, 
    QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsSvgItem, 
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsPolygonItem,
    QGraphicsItemGroup, QGraphicsItem, QGraphicsDropShadowEffect,
    QToolBar, QPushButton, QColorDialog, QSpinBox, QDoubleSpinBox, QFileDialog, 
    QMenu, QStatusBar, QLabel, QSlider, QComboBox, QUndoStack, QUndoCommand,
    QDockWidget, QWidget, QFormLayout, QHBoxLayout, QVBoxLayout, QCheckBox, QFrame,
    QListWidget, QListWidgetItem, QAbstractItemView, QToolButton, QSizePolicy, QGroupBox
)
from PySide6.QtCore import Qt, QPointF, QPoint, QRectF, QLineF, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPen, QColor, QBrush, QPainterPath, QPixmap, QAction, QKeySequence, QPainter, QImage, QFont, QTransform, QCursor, QPageSize, QPolygonF
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtSvg import QSvgGenerator

# Custom data role for storing item names
NAME_ROLE = Qt.UserRole + 1

# --- CUSTOM ITEMS ---
class RoundedRectItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self._radius = 0.0

    def setRadius(self, r):
        self._radius = max(0.0, r)
        self.update()

    def radius(self):
        return self._radius

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        if self._radius > 0:
            path = QPainterPath()
            path.addRoundedRect(self.rect(), self._radius, self._radius)
            painter.setPen(self.pen())
            painter.setBrush(self.brush())
            painter.drawPath(path)
        else:
            super().paint(painter, option, widget)
            
    def shape(self):
        path = QPainterPath()
        if self._radius > 0:
            path.addRoundedRect(self.rect(), self._radius, self._radius)
        else:
            path.addRect(self.rect())
        return path

class ArrowPathItem(QGraphicsPathItem):
    """ A unified path item that can dynamically draw arrowheads at either end. """
    def __init__(self):
        super().__init__()
        self._start_arrow = False
        self._end_arrow = False
        self._base_path = QPainterPath()

    def setBasePath(self, path):
        self._base_path = path
        self.update_arrow_path()

    def setStartArrow(self, val):
        self._start_arrow = val
        self.update_arrow_path()

    def setEndArrow(self, val):
        self._end_arrow = val
        self.update_arrow_path()

    def startArrow(self): return self._start_arrow
    def endArrow(self): return self._end_arrow
    def base_path(self): return self._base_path

    def update_arrow_path(self):
        pen = self.pen()
        self.setBrush(QBrush(pen.color()))
        
        full_path = QPainterPath(self._base_path)
        
        if self._base_path.length() > 0.1:
            if self._end_arrow:
                self._add_head(full_path, 1.0, pen.width())
            if self._start_arrow:
                self._add_head(full_path, 0.0, pen.width(), reverse=True)
            
        super().setPath(full_path)

    def _add_head(self, path, t, pen_width, reverse=False):
        size = max(10, pen_width * 3.5)
        
        p_curr = self._base_path.pointAtPercent(t)
        
        # Use Qt's built-in angleAtPercent for perfect tangent calculation
        try:
            angle_deg = self._base_path.angleAtPercent(t)
            angle = math.radians(angle_deg)
        except:
            # Fallback if path is somehow invalid
            t_prev = max(0.0, t - 0.01) if not reverse else min(1.0, t + 0.01)
            p_prev = self._base_path.pointAtPercent(t_prev)
            dx = p_curr.x() - p_prev.x()
            dy = p_curr.y() - p_prev.y()
            if dx == 0 and dy == 0: return
            angle = math.atan2(dy, dx)
            
        if reverse:
            angle += math.pi

        base_x = p_curr.x() - size * math.cos(angle)
        base_y = p_curr.y() - size * math.sin(angle)
        
        l_angle = angle + math.pi / 2
        r_angle = angle - math.pi / 2
        
        p1 = QPointF(base_x + (size/2) * math.cos(l_angle), base_y + (size/2) * math.sin(l_angle))
        p2 = QPointF(base_x + (size/2) * math.cos(r_angle), base_y + (size/2) * math.sin(r_angle))
        
        head_path = QPainterPath()
        head_path.moveTo(p_curr)
        head_path.lineTo(p1)
        head_path.lineTo(p2)
        head_path.closeSubpath()
        
        path.addPath(head_path)

class PolygonItem(QGraphicsPolygonItem):
    def __init__(self):
        super().__init__()
        self._sides = 5
        self._rect = QRectF()

    def setSides(self, sides):
        self._sides = max(3, sides)
        self.update_geometry()

    def sides(self):
        return self._sides

    def setRect(self, rect):
        self._rect = rect
        self.update_geometry()

    def rect(self):
        return self._rect

    def update_geometry(self):
        r = self._rect
        cx = r.center().x()
        cy = r.center().y()
        rx = r.width() / 2
        ry = r.height() / 2
        
        points = []
        for i in range(self._sides):
            angle = (2 * math.pi * i / self._sides) - math.pi / 2
            points.append(QPointF(cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
        super().setPolygon(QPolygonF(points))


# --- UNDO COMMANDS ---
class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item):
        super().__init__("Add Item")
        self.scene = scene
        self.item = item
    def undo(self): self.scene.removeItem(self.item)
    def redo(self): self.scene.addItem(self.item)

class DeleteItemsCommand(QUndoCommand):
    def __init__(self, scene, items):
        super().__init__("Delete Items")
        self.scene = scene
        self.items = items
    def undo(self):
        for item in self.items: self.scene.addItem(item)
    def redo(self):
        for item in self.items: self.scene.removeItem(item)

class MoveItemsCommand(QUndoCommand):
    def __init__(self, items, old_positions, new_positions):
        super().__init__("Move Items")
        self.items = items
        self.old_positions = old_positions
        self.new_positions = new_positions
    def undo(self):
        for item, pos in zip(self.items, self.old_positions): item.setPos(pos)
    def redo(self):
        for item, pos in zip(self.items, self.new_positions): item.setPos(pos)

class BooleanCommand(QUndoCommand):
    def __init__(self, scene, old_items, new_item):
        super().__init__("Boolean Operation")
        self.scene = scene
        self.old_items = old_items
        self.new_item = new_item
    def undo(self):
        self.scene.removeItem(self.new_item)
        for i in self.old_items: self.scene.addItem(i)
    def redo(self):
        for i in self.old_items: self.scene.removeItem(i)
        self.scene.addItem(self.new_item)


class CanvasView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.space_pressed = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self.space_pressed = True
            self.setCursor(Qt.OpenHandCursor)
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            return
            
        items = self.scene().selectedItems()
        if items:
            step = 10 if event.modifiers() & Qt.ShiftModifier else 1
            if event.key() == Qt.Key_Up:
                for item in items: item.moveBy(0, -step)
                self.window().sync_properties_panel()
                return
            elif event.key() == Qt.Key_Down:
                for item in items: item.moveBy(0, step)
                self.window().sync_properties_panel()
                return
            elif event.key() == Qt.Key_Left:
                for item in items: item.moveBy(-step, 0)
                self.window().sync_properties_panel()
                return
            elif event.key() == Qt.Key_Right:
                for item in items: item.moveBy(step, 0)
                self.window().sync_properties_panel()
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self.space_pressed = False
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.window().update_cursor()
        super().keyReleaseEvent(event)

    def wheelEvent(self, event):
        zoom_factor = 1.15
        current_zoom = self.transform().m11()
        if event.angleDelta().y() > 0 and current_zoom < 10.0:
            self.scale(zoom_factor, zoom_factor)
        elif event.angleDelta().y() < 0 and current_zoom > 0.1:
            self.scale(1 / zoom_factor, 1 / zoom_factor)
        self.window().update_status_bar()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            fake_event = QMouseEvent(event.type(), event.position(), Qt.LeftButton, Qt.LeftButton, event.modifiers())
            super().mousePressEvent(fake_event)
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            fake_event = QMouseEvent(event.type(), event.position(), Qt.LeftButton, Qt.LeftButton, event.modifiers())
            super().mouseReleaseEvent(fake_event)
            if not self.space_pressed:
                self.setDragMode(QGraphicsView.RubberBandDrag)
            return
        super().mouseReleaseEvent(event)

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor("#ffffff"))
        pen = QPen(QColor("#f0f0f0"))
        pen.setWidth(1)
        painter.setPen(pen)
        grid_size = 25
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        for x in range(left, int(rect.right()), grid_size):
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()), grid_size):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)


class CanvasScene(QGraphicsScene):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_mode = 'select'
        self.current_item = None
        self.start_pos = None
        self.last_draw_point = None
        
        self.brush_color = QColor("#000000")
        self.fill_color = QColor("#ffffff")
        self.brush_width = 5
        self.stroke_style = Qt.SolidLine
        self.cap_style = Qt.RoundCap
        self.join_style = Qt.RoundJoin
        
        self.undo_stack = QUndoStack()
        self.move_start_positions = {}

    def set_mode(self, mode):
        self.current_mode = mode
        self.views()[0].setDragMode(
            QGraphicsView.RubberBandDrag if mode == 'select' else QGraphicsView.NoDrag
        )

    def get_pen(self):
        return QPen(self.brush_color, self.brush_width, self.stroke_style, self.cap_style, self.join_style)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.scenePos()
            
            if self.current_mode == 'eyedropper':
                item = self.itemAt(event.scenePos(), self.views()[0].transform())
                if item:
                    if hasattr(item, 'pen'):
                        self.brush_color = item.pen().color()
                    elif hasattr(item, 'defaultTextColor'):
                        self.brush_color = item.defaultTextColor()
                        
                    if hasattr(item, 'brush'):
                        b = item.brush()
                        if b.style() != Qt.NoBrush:
                            self.fill_color = b.color()
                            
                    self.views()[0].window().update_color_swatches()
                    self.views()[0].window().set_mode('select')
                return
            
            if self.current_mode in ['draw', 'freehand_arrow']:
                if self.current_mode == 'draw':
                    self.current_item = QGraphicsPathItem()
                else:
                    self.current_item = ArrowPathItem()
                    self.current_item.setEndArrow(True)
                    
                self.current_item.setPen(self.get_pen())
                path = QPainterPath(self.start_pos)
                
                if self.current_mode == 'draw':
                    self.current_item.setPath(path)
                else:
                    self.current_item.setBasePath(path)
                    
                self.last_draw_point = self.start_pos
                self.addItem(self.current_item)
                return
                
            elif self.current_mode in ['arrow', 'line', 'curve', 'curved_arrow']:
                self.current_item = ArrowPathItem()
                self.current_item.setPen(self.get_pen())
                if self.current_mode in ['arrow', 'curved_arrow']:
                    self.current_item.setEndArrow(True)
                path = QPainterPath(self.start_pos)
                self.current_item.setBasePath(path)
                self.addItem(self.current_item)
                return
                
            elif self.current_mode == 'rect':
                self.current_item = RoundedRectItem(QRectF(self.start_pos, self.start_pos))
                self.current_item.setPen(self.get_pen())
                self.current_item.setBrush(self.fill_color)
                self.addItem(self.current_item)
                return
            elif self.current_mode == 'ellipse':
                self.current_item = QGraphicsEllipseItem(QRectF(self.start_pos, self.start_pos))
                self.current_item.setPen(self.get_pen())
                self.current_item.setBrush(self.fill_color)
                self.addItem(self.current_item)
                return
            elif self.current_mode == 'polygon':
                self.current_item = PolygonItem()
                self.current_item.setSides(self.views()[0].window().spin_poly_sides.value())
                self.current_item.setRect(QRectF(self.start_pos, self.start_pos))
                self.current_item.setPen(self.get_pen())
                self.current_item.setBrush(self.fill_color)
                self.addItem(self.current_item)
                return
            elif self.current_mode == 'text':
                text_item = QGraphicsTextItem("Text")
                text_item.setFont(QFont("Arial", 24))
                text_item.setDefaultTextColor(self.brush_color)
                text_item.setPos(self.start_pos)
                text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
                self._make_item_selectable(text_item)
                self.undo_stack.push(AddItemCommand(self, text_item))
                text_item.setFocus()
                self.current_item = None
                return
                
        if event.button() == Qt.RightButton:
            item = self.itemAt(event.scenePos(), self.views()[0].transform())
            if item:
                self.show_context_menu(event.screenPos(), item)
                return

        super().mousePressEvent(event)
        if self.current_mode == 'select':
            self.move_start_positions = {id(item): item.pos() for item in self.selectedItems()}
            self.views()[0].window().sync_properties_panel()

    def mouseMoveEvent(self, event):
        self.window().update_status_bar(event.scenePos())
            
        if event.buttons() & Qt.LeftButton and self.current_item and self.start_pos:
            end_pos = event.scenePos()
            
            if self.current_mode in ['draw', 'freehand_arrow']:
                # THRESHOLD: Ignore tiny movements to prevent jagged overlapping points
                dist = math.hypot(end_pos.x() - self.last_draw_point.x(), end_pos.y() - self.last_draw_point.y())
                if dist < 2.0:
                    return
                    
                # QUADRATIC BEZIER MIDPOINT SMOOTHING
                mid_point = QPointF((self.last_draw_point.x() + end_pos.x())/2,
                                    (self.last_draw_point.y() + end_pos.y())/2)
                
                if self.current_mode == 'draw':
                    path = self.current_item.path()
                    path.quadTo(self.last_draw_point, mid_point)
                    self.current_item.setPath(path)
                else: # freehand_arrow
                    path = self.current_item.base_path()
                    path.quadTo(self.last_draw_point, mid_point)
                    self.current_item.setBasePath(path)
                    
                self.last_draw_point = end_pos
                
            elif self.current_mode in ['arrow', 'line']:
                start = self.start_pos
                end = end_pos
                if event.modifiers() & Qt.ShiftModifier:
                    angle = math.atan2(end.y() - start.y(), end.x() - start.x())
                    step = math.pi / 4
                    angle = round(angle / step) * step
                    length = math.hypot(end.x() - start.x(), end.y() - start.y())
                    end = QPointF(start.x() + math.cos(angle) * length, start.y() + math.sin(angle) * length)
                path = QPainterPath(start)
                path.lineTo(end)
                self.current_item.setBasePath(path)
                
            elif self.current_mode in ['curve', 'curved_arrow']:
                dx = end_pos.x() - self.start_pos.x()
                dy = end_pos.y() - self.start_pos.y()
                dist = math.hypot(dx, dy)
                if dist > 0:
                    nx = -dy / dist
                    ny = dx / dist
                    offset = dist * 0.25
                    ctrl_x = self.start_pos.x() + dx/2 + nx * offset
                    ctrl_y = self.start_pos.y() + dy/2 + ny * offset
                    ctrl_point = QPointF(ctrl_x, ctrl_y)
                    path = QPainterPath(self.start_pos)
                    path.quadTo(ctrl_point, end_pos)
                    self.current_item.setBasePath(path)
                    
            elif self.current_mode in ['rect', 'ellipse', 'polygon']:
                start = self.start_pos
                end = end_pos
                if event.modifiers() & Qt.AltModifier:
                    dx = end.x() - start.x()
                    dy = end.y() - start.y()
                    start = QPointF(self.start_pos.x() - dx, self.start_pos.y() - dy)
                    end = QPointF(self.start_pos.x() + dx, self.start_pos.y() + dy)
                if event.modifiers() & Qt.ShiftModifier:
                    dx = end.x() - start.x()
                    dy = end.y() - start.y()
                    size = max(abs(dx), abs(dy))
                    end = QPointF(start.x() + size if dx > 0 else start.x() - size,
                                  start.y() + size if dy > 0 else start.y() - size)
                
                r = QRectF(start, end).normalized()
                self.current_item.setRect(r)
            return
                
        super().mouseMoveEvent(event)
        if self.current_mode == 'select' and self.selectedItems():
            self.views()[0].window().sync_properties_panel()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.current_item:
            if self.current_mode in ['draw', 'freehand_arrow']:
                if self.current_mode == 'draw':
                    path = self.current_item.path()
                    path.lineTo(event.scenePos())
                    self.current_item.setPath(path)
                    self.current_item.setPath(self.current_item.path().simplified())
                else:
                    path = self.current_item.base_path()
                    path.lineTo(event.scenePos())
                    self.current_item.setBasePath(path)
                    self.current_item.setBasePath(self.current_item.base_path().simplified())
                    
                    if self.current_item.base_path().length() < 5.0:
                        self.removeItem(self.current_item)
                        self.current_item = None
                        self.start_pos = None
                        return
                        
            elif isinstance(self.current_item, ArrowPathItem):
                if self.current_item.base_path().length() < 1.0:
                    self.removeItem(self.current_item)
                    self.current_item = None
                    self.start_pos = None
                    return
                    
            self._make_item_selectable(self.current_item)
            self.undo_stack.push(AddItemCommand(self, self.current_item))
            self.current_item = None
            self.start_pos = None
            return
            
        elif event.button() == Qt.LeftButton and self.current_mode == 'select':
            if event.modifiers() & Qt.ControlModifier:
                grid_size = 25
                for item in self.selectedItems():
                    x = round(item.pos().x() / grid_size) * grid_size
                    y = round(item.pos().y() / grid_size) * grid_size
                    item.setPos(x, y)
            
            items = self.selectedItems()
            if items:
                old_positions = [self.move_start_positions.get(id(item), item.pos()) for item in items]
                new_positions = [item.pos() for item in items]
                moved = any(old != new for old, new in zip(old_positions, new_positions))
                if moved:
                    self.undo_stack.push(MoveItemsCommand(items, old_positions, new_positions))
            
        super().mouseReleaseEvent(event)
        self.views()[0].window().sync_properties_panel()

    def _make_item_selectable(self, item):
        item.setFlag(QGraphicsItem.ItemIsSelectable)
        item.setFlag(QGraphicsItem.ItemIsMovable)
        item.setFlag(QGraphicsItem.ItemIsRotatable)

    def show_context_menu(self, screen_pos, item):
        menu = QMenu()
        menu.addAction("Bring Forward (Ctrl+])", self.window().bring_forward)
        menu.addAction("Send Backward (Ctrl+[)", self.window().send_backward)
        menu.addAction("Bring to Front (Ctrl+Shift+])", self.window().bring_to_front)
        menu.addAction("Send to Back (Ctrl+Shift+[)", self.window().send_to_back)
        menu.addSeparator()
        
        if len(self.selectedItems()) >= 2:
            bool_menu = menu.addMenu("Pathfinder")
            bool_menu.addAction("Unite", self.window().boolean_unite)
            bool_menu.addAction("Subtract", self.window().boolean_subtract)
            bool_menu.addAction("Intersect", self.window().boolean_intersect)
            menu.addSeparator()
            
        menu.addAction("Copy (Ctrl+C)", self.window().copy_selected)
        menu.addAction("Duplicate (Ctrl+D)", self.window().duplicate_selected)
        menu.addAction("Duplicate in Place (Ctrl+Shift+D)", self.window().duplicate_in_place)
        menu.addAction("Copy Style (Ctrl+Shift+C)", self.window().copy_style)
        menu.addAction("Paste Style (Ctrl+Shift+V)", self.window().paste_style)
        menu.addSeparator()
        if len(self.selectedItems()) > 1:
            menu.addAction("Group (Ctrl+G)", self.window().group_selected)
        if isinstance(item, QGraphicsItemGroup):
            menu.addAction("Ungroup (Ctrl+Shift+G)", self.window().ungroup_selected)
        menu.addSeparator()
        menu.addAction("Delete", self.window().delete_selected)
        menu.exec(screen_pos)

    def delete_selected(self):
        items = self.selectedItems()
        if items:
            self.undo_stack.push(DeleteItemsCommand(self, items))
            self.clearSelection()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Canvas Studio Pro")
        self.resize(1600, 900)

        self.scene = CanvasScene()
        self.scene.setSceneRect(-10000, -10000, 20000, 20000)
        
        self.view = CanvasView(self.scene)
        self.setCentralWidget(self.view)
        
        self.clipboard_items = []
        self.style_clipboard = None

        self._setup_toolbar()
        self._setup_layers_panel()
        self._setup_properties_panel()
        self._setup_shortcuts()
        self._setup_status_bar()
        
        self.scene.undo_stack.indexChanged.connect(self.refresh_layers)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.list_layers.itemChanged.connect(self.on_layer_item_changed)
        
        self.update_cursor()
        self.sync_properties_panel()
        self.refresh_layers()

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        # --- Modes ---
        self.btn_select = QPushButton("🖱️ Select (V)")
        self.btn_draw = QPushButton("✏️ Draw (B)")
        self.btn_free_arrow = QPushButton("✍️ Free Arrow (F)")
        self.btn_arrow = QPushButton("↗️ Straight Arrow (A)")
        self.btn_curved_arrow = QPushButton("➰ Curved Arrow (Q)")
        self.btn_curve = QPushButton("〰️ Curve (C)")
        self.btn_rect = QPushButton("⬜ Rect (R)")
        self.btn_ellipse = QPushButton("⭕ Ellipse (O)")
        self.btn_polygon = QPushButton("⬠ Polygon (P)")
        self.btn_line = QPushButton("↔️ Line (L)")
        self.btn_text = QPushButton("🔤 Text (T)")
        self.btn_eyedropper = QPushButton("💧 Pick (I)")
        
        self.mode_buttons = [self.btn_select, self.btn_draw, self.btn_free_arrow, self.btn_arrow, self.btn_curved_arrow, self.btn_curve, self.btn_rect, self.btn_ellipse, self.btn_polygon, self.btn_line, self.btn_text, self.btn_eyedropper]
        for btn in self.mode_buttons:
            btn.setCheckable(True)
            toolbar.addWidget(btn)
            
        self.btn_select.setChecked(True)
        self.btn_select.clicked.connect(lambda: self.set_mode('select'))
        self.btn_draw.clicked.connect(lambda: self.set_mode('draw'))
        self.btn_free_arrow.clicked.connect(lambda: self.set_mode('freehand_arrow'))
        self.btn_arrow.clicked.connect(lambda: self.set_mode('arrow'))
        self.btn_curved_arrow.clicked.connect(lambda: self.set_mode('curved_arrow'))
        self.btn_curve.clicked.connect(lambda: self.set_mode('curve'))
        self.btn_rect.clicked.connect(lambda: self.set_mode('rect'))
        self.btn_ellipse.clicked.connect(lambda: self.set_mode('ellipse'))
        self.btn_polygon.clicked.connect(lambda: self.set_mode('polygon'))
        self.btn_line.clicked.connect(lambda: self.set_mode('line'))
        self.btn_text.clicked.connect(lambda: self.set_mode('text'))
        self.btn_eyedropper.clicked.connect(lambda: self.set_mode('eyedropper'))
        toolbar.addSeparator()

        # --- Project Operations ---
        self.btn_save_proj = QPushButton("💾 Save Pro (Ctrl+Shift+J)")
        self.btn_save_proj.clicked.connect(self.save_project)
        toolbar.addWidget(self.btn_save_proj)
        
        self.btn_load_proj = QPushButton("📂 Load Pro (Ctrl+J)")
        self.btn_load_proj.clicked.connect(self.load_project)
        toolbar.addWidget(self.btn_load_proj)
        toolbar.addSeparator()

        # --- File Operations ---
        self.btn_import_img = QPushButton("🖼️ Img (Ctrl+I)")
        self.btn_import_img.clicked.connect(self.import_image_file)
        toolbar.addWidget(self.btn_import_img)

        self.btn_import_svg = QPushButton("🌟 SVG (Ctrl+Shift+I)")
        self.btn_import_svg.clicked.connect(self.import_svg_file)
        toolbar.addWidget(self.btn_import_svg)

        self.btn_export_png = QPushButton("🖼️ PNG (Ctrl+S)")
        self.btn_export_png.clicked.connect(self.export_canvas_png)
        toolbar.addWidget(self.btn_export_png)
        
        self.btn_export_svg = QPushButton("📄 SVG (Ctrl+Shift+S)")
        self.btn_export_svg.clicked.connect(self.export_canvas_svg)
        toolbar.addWidget(self.btn_export_svg)

        self.btn_export_pdf = QPushButton("📕 PDF (Ctrl+Shift+P)")
        self.btn_export_pdf.clicked.connect(self.export_canvas_pdf)
        toolbar.addWidget(self.btn_export_pdf)
        toolbar.addSeparator()

        # --- History & View ---
        self.btn_undo = QPushButton("↩️ Undo (Ctrl+Z)")
        self.btn_undo.clicked.connect(self.scene.undo_stack.undo)
        toolbar.addWidget(self.btn_undo)
        
        self.btn_redo = QPushButton("↪️ Redo (Ctrl+Y)")
        self.btn_redo.clicked.connect(self.scene.undo_stack.redo)
        toolbar.addWidget(self.btn_redo)

        self.btn_fit = QPushButton("🔍 Fit (Ctrl+0)")
        self.btn_fit.clicked.connect(self.fit_to_view)
        toolbar.addWidget(self.btn_fit)
        
        self.btn_100 = QPushButton("100% (Ctrl+1)")
        self.btn_100.clicked.connect(self.zoom_100)
        toolbar.addWidget(self.btn_100)

        self.btn_fullscreen = QPushButton("⛶ Fullscreen (F11)")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        toolbar.addWidget(self.btn_fullscreen)

    def _setup_layers_panel(self):
        self.layers_dock = QDockWidget("Layers", self)
        self.layers_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        panel_widget = QWidget()
        layout = QVBoxLayout(panel_widget)
        
        self.list_layers = QListWidget()
        self.list_layers.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_layers.itemSelectionChanged.connect(self.layers_selection_changed)
        self.list_layers.setEditTriggers(QAbstractItemView.DoubleClicked)
        layout.addWidget(self.list_layers)
        
        btn_layout = QHBoxLayout()
        self.btn_fwd = QPushButton("⬆️ Fwd")
        self.btn_bwd = QPushButton("⬇️ Bwd")
        self.btn_front = QPushButton("⏫ Front")
        self.btn_back = QPushButton("⏬ Back")
        
        self.btn_fwd.clicked.connect(self.bring_forward)
        self.btn_bwd.clicked.connect(self.send_backward)
        self.btn_front.clicked.connect(self.bring_to_front)
        self.btn_back.clicked.connect(self.send_to_back)
        
        for btn in [self.btn_fwd, self.btn_bwd, self.btn_front, self.btn_back]:
            btn_layout.addWidget(btn)
            
        layout.addLayout(btn_layout)
        self.layers_dock.setWidget(panel_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layers_dock)

    def _setup_properties_panel(self):
        self.dock = QDockWidget("Properties", self)
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        panel_widget = QWidget()
        layout = QVBoxLayout(panel_widget)
        
        # --- Transform Group ---
        trans_box = QGroupBox("Transform")
        trans_layout = QFormLayout(trans_box)
        
        w_h_layout = QHBoxLayout()
        self.spin_x = QDoubleSpinBox()
        self.spin_y = QDoubleSpinBox()
        self.spin_w = QDoubleSpinBox()
        self.spin_h = QDoubleSpinBox()
        self.spin_rot = QDoubleSpinBox()
        self.spin_rot.setRange(-360.0, 360.0)
        
        self.spin_x.valueChanged.connect(self.update_item_x)
        self.spin_y.valueChanged.connect(self.update_item_y)
        self.spin_w.valueChanged.connect(self.update_item_w)
        self.spin_h.valueChanged.connect(self.update_item_h)
        self.spin_rot.valueChanged.connect(self.update_item_rotation)
        
        self.chk_lock_ratio = QCheckBox("🔒")
        self.chk_lock_ratio.setToolTip("Lock Aspect Ratio")
        
        w_h_layout.addWidget(self.spin_w)
        w_h_layout.addWidget(self.spin_h)
        w_h_layout.addWidget(self.chk_lock_ratio)
        
        trans_layout.addRow("X:", self.spin_x)
        trans_layout.addRow("Y:", self.spin_y)
        trans_layout.addRow("W/H:", w_h_layout)
        
        scale_layout = QHBoxLayout()
        self.spin_scale_w = QDoubleSpinBox()
        self.spin_scale_h = QDoubleSpinBox()
        self.spin_scale_w.setRange(1, 1000)
        self.spin_scale_h.setRange(1, 1000)
        self.spin_scale_w.setValue(100)
        self.spin_scale_h.setValue(100)
        self.spin_scale_w.setSuffix("%")
        self.spin_scale_h.setSuffix("%")
        self.spin_scale_w.valueChanged.connect(self.update_item_scale_w)
        self.spin_scale_h.valueChanged.connect(self.update_item_scale_h)
        scale_layout.addWidget(self.spin_scale_w)
        scale_layout.addWidget(self.spin_scale_h)
        trans_layout.addRow("Scale:", scale_layout)
        trans_layout.addRow("Rotation:", self.spin_rot)
        layout.addWidget(trans_box)
        
        # --- Align Group ---
        align_box = QGroupBox("Align & Distribute")
        align_main_layout = QVBoxLayout(align_box)
        
        align_layout = QHBoxLayout()
        self.btn_align_left = QPushButton("⬅")
        self.btn_align_h = QPushButton("↔")
        self.btn_align_right = QPushButton("➡")
        self.btn_align_top = QPushButton("⬆")
        self.btn_align_v = QPushButton("↕")
        self.btn_align_bottom = QPushButton("⬇")
        for btn in [self.btn_align_left, self.btn_align_h, self.btn_align_right, self.btn_align_top, self.btn_align_v, self.btn_align_bottom]:
            btn.setFixedWidth(40)
            align_layout.addWidget(btn)
        self.btn_align_left.clicked.connect(lambda: self.align_items('left'))
        self.btn_align_h.clicked.connect(lambda: self.align_items('hcenter'))
        self.btn_align_right.clicked.connect(lambda: self.align_items('right'))
        self.btn_align_top.clicked.connect(lambda: self.align_items('top'))
        self.btn_align_v.clicked.connect(lambda: self.align_items('vcenter'))
        self.btn_align_bottom.clicked.connect(lambda: self.align_items('bottom'))
        align_main_layout.addLayout(align_layout)

        dist_layout = QHBoxLayout()
        self.btn_dist_h = QPushButton("⇆ Dist H")
        self.btn_dist_v = QPushButton("⇅ Dist V")
        self.btn_dist_h.clicked.connect(self.distribute_h)
        self.btn_dist_v.clicked.connect(self.distribute_v)
        dist_layout.addWidget(self.btn_dist_h)
        dist_layout.addWidget(self.btn_dist_v)
        align_main_layout.addLayout(dist_layout)
        
        flip_layout = QHBoxLayout()
        self.btn_flip_h = QPushButton("Flip H")
        self.btn_flip_v = QPushButton("Flip V")
        self.btn_lock = QPushButton("🔒 Lock")
        self.btn_lock.setCheckable(True)
        flip_layout.addWidget(self.btn_flip_h)
        flip_layout.addWidget(self.btn_flip_v)
        flip_layout.addWidget(self.btn_lock)
        self.btn_flip_h.clicked.connect(lambda: self.flip_selected('h'))
        self.btn_flip_v.clicked.connect(lambda: self.flip_selected('v'))
        self.btn_lock.clicked.connect(self.toggle_lock)
        align_main_layout.addLayout(flip_layout)
        
        layout.addWidget(align_box)

        # --- Appearance Group ---
        appear_box = QGroupBox("Appearance")
        appear_layout = QFormLayout(appear_box)
        
        stroke_layout = QHBoxLayout()
        self.chk_stroke = QCheckBox()
        self.chk_stroke.setChecked(True)
        self.chk_stroke.toggled.connect(self.toggle_stroke)
        self.btn_color = QPushButton("🎨")
        self.btn_color.setFixedWidth(40)
        self.btn_color.clicked.connect(self.pick_stroke_color)
        stroke_layout.addWidget(self.chk_stroke)
        stroke_layout.addWidget(self.btn_color)
        appear_layout.addRow("Stroke:", stroke_layout)

        fill_layout = QHBoxLayout()
        self.chk_fill = QCheckBox()
        self.chk_fill.setChecked(True)
        self.chk_fill.toggled.connect(self.toggle_fill)
        self.btn_fill_color = QPushButton("🪣")
        self.btn_fill_color.setFixedWidth(40)
        self.btn_fill_color.clicked.connect(self.pick_fill_color)
        fill_layout.addWidget(self.chk_fill)
        fill_layout.addWidget(self.btn_fill_color)
        appear_layout.addRow("Fill:", fill_layout)

        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 100)
        self.spin_width.setValue(5)
        self.spin_width.valueChanged.connect(self.change_width)
        appear_layout.addRow("Stroke W:", self.spin_width)

        self.combo_style = QComboBox()
        self.combo_style.addItems(["Solid", "Dash", "Dot", "Dash Dot"])
        self.combo_style.currentIndexChanged.connect(self.change_stroke_style)
        appear_layout.addRow("Style:", self.combo_style)
        
        self.combo_caps = QComboBox()
        self.combo_caps.addItems(["Flat Cap", "Round Cap", "Square Cap"])
        self.combo_caps.currentIndexChanged.connect(self.change_cap_style)
        appear_layout.addRow("Caps:", self.combo_caps)
        
        self.combo_joins = QComboBox()
        self.combo_joins.addItems(["Miter Join", "Round Join", "Bevel Join"])
        self.combo_joins.currentIndexChanged.connect(self.change_join_style)
        appear_layout.addRow("Joins:", self.combo_joins)

        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.valueChanged.connect(self.change_opacity)
        appear_layout.addRow("Opacity:", self.slider_opacity)
        
        self.spin_radius = QDoubleSpinBox()
        self.spin_radius.setRange(0, 9999)
        self.spin_radius.valueChanged.connect(self.change_radius)
        appear_layout.addRow("Corner R:", self.spin_radius)
        
        self.spin_poly_sides = QSpinBox()
        self.spin_poly_sides.setRange(3, 12)
        self.spin_poly_sides.setValue(5)
        self.spin_poly_sides.valueChanged.connect(self.change_poly_sides)
        appear_layout.addRow("Poly Sides:", self.spin_poly_sides)
        
        self.combo_line_heads = QComboBox()
        self.combo_line_heads.addItems(["None", "Start", "End", "Both"])
        self.combo_line_heads.currentIndexChanged.connect(self.change_line_heads)
        appear_layout.addRow("Arrows:", self.combo_line_heads)
        
        self.chk_shadow = QCheckBox("Drop Shadow")
        self.chk_shadow.toggled.connect(self.toggle_shadow)
        appear_layout.addRow(self.chk_shadow)
        
        layout.addWidget(appear_box)
        
        # --- Export Group ---
        exp_box = QGroupBox("Export Options")
        exp_layout = QVBoxLayout(exp_box)
        self.chk_transparent = QCheckBox("Transparent Background (PNG)")
        exp_layout.addWidget(self.chk_transparent)
        self.chk_export_sel = QCheckBox("Export Selected Only")
        exp_layout.addWidget(self.chk_export_sel)
        
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Export Scale:"))
        self.spin_export_scale = QSpinBox()
        self.spin_export_scale.setRange(1, 8)
        self.spin_export_scale.setValue(1)
        scale_layout.addWidget(self.spin_export_scale)
        exp_layout.addLayout(scale_layout)
        layout.addWidget(exp_box)
        
        layout.addStretch()

        self.dock.setWidget(panel_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        
        self.update_color_swatches()

    def _setup_shortcuts(self):
        QAction(QKeySequence("V"), self, triggered=lambda: self.set_mode('select'))
        QAction(QKeySequence("B"), self, triggered=lambda: self.set_mode('draw'))
        QAction(QKeySequence("F"), self, triggered=lambda: self.set_mode('freehand_arrow'))
        QAction(QKeySequence("A"), self, triggered=lambda: self.set_mode('arrow'))
        QAction(QKeySequence("Q"), self, triggered=lambda: self.set_mode('curved_arrow'))
        QAction(QKeySequence("C"), self, triggered=lambda: self.set_mode('curve'))
        QAction(QKeySequence("R"), self, triggered=lambda: self.set_mode('rect'))
        QAction(QKeySequence("O"), self, triggered=lambda: self.set_mode('ellipse'))
        QAction(QKeySequence("P"), self, triggered=lambda: self.set_mode('polygon'))
        QAction(QKeySequence("L"), self, triggered=lambda: self.set_mode('line'))
        QAction(QKeySequence("T"), self, triggered=lambda: self.set_mode('text'))
        QAction(QKeySequence("I"), self, triggered=lambda: self.set_mode('eyedropper'))
        
        QAction(QKeySequence("F11"), self, triggered=self.toggle_fullscreen)
        QAction(QKeySequence("Delete"), self, triggered=self.scene.delete_selected)
        QAction(QKeySequence("Backspace"), self, triggered=self.scene.delete_selected)
        
        QAction(QKeySequence("Ctrl+I"), self, triggered=self.import_image_file)
        QAction(QKeySequence("Ctrl+Shift+I"), self, triggered=self.import_svg_file)
        QAction(QKeySequence("Ctrl+S"), self, triggered=self.export_canvas_png)
        QAction(QKeySequence("Ctrl+Shift+S"), self, triggered=self.export_canvas_svg)
        QAction(QKeySequence("Ctrl+Shift+P"), self, triggered=self.export_canvas_pdf)
        QAction(QKeySequence("Ctrl+Shift+J"), self, triggered=self.save_project)
        QAction(QKeySequence("Ctrl+J"), self, triggered=self.load_project)
        
        QAction(QKeySequence("Ctrl+Z"), self, triggered=self.scene.undo_stack.undo)
        QAction(QKeySequence("Ctrl+Y"), self, triggered=self.scene.undo_stack.redo)
        QAction(QKeySequence("Ctrl+Shift+Z"), self, triggered=self.scene.undo_stack.redo)
        
        QAction(QKeySequence("Ctrl+C"), self, triggered=self.copy_selected)
        QAction(QKeySequence("Ctrl+X"), self, triggered=self.cut_selected)
        QAction(QKeySequence("Ctrl+V"), self, triggered=self.paste_items)
        QAction(QKeySequence("Ctrl+D"), self, triggered=self.duplicate_selected)
        QAction(QKeySequence("Ctrl+Shift+D"), self, triggered=self.duplicate_in_place)
        QAction(QKeySequence("Ctrl+G"), self, triggered=self.group_selected)
        QAction(QKeySequence("Ctrl+Shift+G"), self, triggered=self.ungroup_selected)
        
        QAction(QKeySequence("Ctrl+Shift+C"), self, triggered=self.copy_style)
        QAction(QKeySequence("Ctrl+Shift+V"), self, triggered=self.paste_style)
        
        QAction(QKeySequence("Ctrl+]"), self, triggered=self.bring_forward)
        QAction(QKeySequence("Ctrl+["), self, triggered=self.send_backward)
        QAction(QKeySequence("Ctrl+Shift+]"), self, triggered=self.bring_to_front)
        QAction(QKeySequence("Ctrl+Shift+["), self, triggered=self.send_to_back)
        QAction(QKeySequence("Ctrl+0"), self, triggered=self.fit_to_view)
        QAction(QKeySequence("Ctrl+1"), self, triggered=self.zoom_100)
        QAction(QKeySequence("Escape"), self, triggered=self.escape_pressed)

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_mode = QLabel("Mode: Select")
        self.lbl_zoom = QLabel("Zoom: 100%")
        self.lbl_coords = QLabel("X: 0, Y: 0")
        self.lbl_metrics = QLabel("Items: 0 | Selected: 0")
        self.lbl_hint = QLabel("Tip: B=Smooth Draw | F=Freehand Arrow | Shift=Constrain")
        self.status_bar.addWidget(self.lbl_mode)
        self.status_bar.addWidget(self.lbl_hint)
        self.status_bar.addPermanentWidget(self.lbl_metrics)
        self.status_bar.addPermanentWidget(self.lbl_coords)
        self.status_bar.addPermanentWidget(self.lbl_zoom)

    def update_status_bar(self, scene_pos=None):
        zoom = int(self.view.transform().m11() * 100)
        self.lbl_zoom.setText(f"Zoom: {zoom}%")
        mode_text = self.scene.current_mode.capitalize()
        self.lbl_mode.setText(f"Mode: {mode_text}")
        
        item_count = len(self.scene.items())
        sel_count = len(self.scene.selectedItems())
        self.lbl_metrics.setText(f"Items: {item_count} | Selected: {sel_count}")
        
        if scene_pos:
            self.lbl_coords.setText(f"X: {int(scene_pos.x())}, Y: {int(scene_pos.y())}")
        else:
            self.lbl_coords.setText("X: 0, Y: 0")

    def update_cursor(self):
        if self.scene.current_mode == 'eyedropper':
            self.view.setCursor(Qt.CrossCursor)
        elif self.scene.current_mode != 'select':
            self.view.setCursor(Qt.CrossCursor)
        else:
            self.view.setCursor(Qt.ArrowCursor)

    def set_mode(self, mode):
        self.scene.set_mode(mode)
        for btn in self.mode_buttons:
            btn.setChecked(False)
        if mode == 'select': self.btn_select.setChecked(True)
        elif mode == 'draw': self.btn_draw.setChecked(True)
        elif mode == 'freehand_arrow': self.btn_free_arrow.setChecked(True)
        elif mode == 'arrow': self.btn_arrow.setChecked(True)
        elif mode == 'curved_arrow': self.btn_curved_arrow.setChecked(True)
        elif mode == 'curve': self.btn_curve.setChecked(True)
        elif mode == 'rect': self.btn_rect.setChecked(True)
        elif mode == 'ellipse': self.btn_ellipse.setChecked(True)
        elif mode == 'polygon': self.btn_polygon.setChecked(True)
        elif mode == 'line': self.btn_line.setChecked(True)
        elif mode == 'text': self.btn_text.setChecked(True)
        elif mode == 'eyedropper': self.btn_eyedropper.setChecked(True)
        self.update_cursor()
        self.update_status_bar()

    def escape_pressed(self):
        self.scene.clearSelection()
        self.set_mode('select')

    # --- Layers Panel Logic ---
    def refresh_layers(self):
        self.list_layers.blockSignals(True)
        self.list_layers.clear()
        
        for i, item in enumerate(reversed(self.scene.items())):
            custom_name = item.data(NAME_ROLE)
            if custom_name:
                text = custom_name
            else:
                text = f"Item {i}"
                if isinstance(item, RoundedRectItem): text = f"Rectangle {i}"
                elif isinstance(item, QGraphicsEllipseItem): text = f"Ellipse {i}"
                elif isinstance(item, PolygonItem): text = f"Polygon {i}"
                elif isinstance(item, ArrowPathItem): text = f"Arrow/Line {i}"
                elif isinstance(item, QGraphicsPathItem): text = f"Path {i}"
                elif isinstance(item, QGraphicsTextItem): text = f"Text: {item.toPlainText()[:15]}"
                elif isinstance(item, QGraphicsPixmapItem): text = f"Image {i}"
                elif isinstance(item, QGraphicsSvgItem): text = f"SVG {i}"
                elif isinstance(item, QGraphicsItemGroup): text = f"Group {i}"
            
            lw_item = QListWidgetItem(text)
            lw_item.setData(Qt.UserRole, item)
            lw_item.setData(NAME_ROLE, text)
            lw_item.setFlags(lw_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
            
            if item.isVisible():
                lw_item.setCheckState(Qt.Checked)
            else:
                lw_item.setCheckState(Qt.Unchecked)
                
            if item.isSelected():
                lw_item.setSelected(True)
            self.list_layers.insertItem(0, lw_item)
            
        self.list_layers.blockSignals(False)
        self.update_status_bar()

    def on_layer_item_changed(self, lw_item):
        item = lw_item.data(Qt.UserRole)
        if item:
            if lw_item.checkState() == Qt.Checked:
                item.setVisible(True)
            else:
                item.setVisible(False)
            
            new_name = lw_item.text()
            old_name = lw_item.data(NAME_ROLE)
            if new_name != old_name:
                item.setData(NAME_ROLE, new_name)
                lw_item.setData(NAME_ROLE, new_name)

    def layers_selection_changed(self):
        self.scene.blockSignals(True)
        self.scene.clearSelection()
        for lw_item in self.list_layers.selectedItems():
            item = lw_item.data(Qt.UserRole)
            if item: item.setSelected(True)
        self.scene.blockSignals(False)
        self.sync_properties_panel()

    def on_selection_changed(self):
        self.list_layers.blockSignals(True)
        self.list_layers.clearSelection()
        for item in self.scene.selectedItems():
            for i in range(self.list_layers.count()):
                lw_item = self.list_layers.item(i)
                if lw_item.data(Qt.UserRole) == item:
                    lw_item.setSelected(True)
        self.list_layers.blockSignals(False)
        self.sync_properties_panel()
        self.update_status_bar()

    # --- Properties Panel Syncing ---
    def sync_properties_panel(self):
        items = self.scene.selectedItems()
        single = len(items) == 1
        
        is_rect = single and isinstance(items[0], RoundedRectItem)
        is_line = single and isinstance(items[0], ArrowPathItem)
        is_poly = single and isinstance(items[0], PolygonItem)
        is_shape = single and isinstance(items[0], (RoundedRectItem, QGraphicsEllipseItem, PolygonItem))
        
        self.spin_x.setEnabled(single)
        self.spin_y.setEnabled(single)
        self.spin_w.setEnabled(is_shape)
        self.spin_h.setEnabled(is_shape)
        self.chk_lock_ratio.setEnabled(is_shape)
        self.spin_scale_w.setEnabled(single)
        self.spin_scale_h.setEnabled(single)
        self.spin_rot.setEnabled(single)
        self.btn_lock.setEnabled(single)
        self.chk_shadow.setEnabled(single)
        self.spin_radius.setEnabled(is_rect)
        self.spin_poly_sides.setEnabled(is_poly)
        self.combo_line_heads.setEnabled(is_line)
        
        if single:
            item = items[0]
            self.spin_x.blockSignals(True)
            self.spin_y.blockSignals(True)
            self.spin_w.blockSignals(True)
            self.spin_h.blockSignals(True)
            self.spin_scale_w.blockSignals(True)
            self.spin_scale_h.blockSignals(True)
            self.spin_rot.blockSignals(True)
            self.chk_shadow.blockSignals(True)
            self.spin_radius.blockSignals(True)
            self.spin_poly_sides.blockSignals(True)
            self.combo_line_heads.blockSignals(True)
            
            self.spin_x.setValue(item.pos().x())
            self.spin_y.setValue(item.pos().y())
            self.spin_rot.setValue(item.rotation())
            self.btn_lock.setChecked(not item.flags() & QGraphicsItem.ItemIsMovable)
            self.chk_shadow.setChecked(isinstance(item.graphicsEffect(), QGraphicsDropShadowEffect))
            
            self.spin_scale_w.setValue(item.scale() * 100 if item.scale() != 0 else 100)
            self.spin_scale_h.setValue(item.scale() * 100 if item.scale() != 0 else 100)
            
            if is_rect:
                self.spin_radius.setValue(items[0].radius())
            if is_poly:
                self.spin_poly_sides.setValue(items[0].sides())
                
            if is_line:
                if items[0].startArrow() and items[0].endArrow(): self.combo_line_heads.setCurrentIndex(3)
                elif items[0].startArrow(): self.combo_line_heads.setCurrentIndex(1)
                elif items[0].endArrow(): self.combo_line_heads.setCurrentIndex(2)
                else: self.combo_line_heads.setCurrentIndex(0)
            
            if is_shape:
                r = item.rect()
                self.spin_w.setValue(r.width())
                self.spin_h.setValue(r.height())
            
            self.spin_x.blockSignals(False)
            self.spin_y.blockSignals(False)
            self.spin_w.blockSignals(False)
            self.spin_h.blockSignals(False)
            self.spin_scale_w.blockSignals(False)
            self.spin_scale_h.blockSignals(False)
            self.spin_rot.blockSignals(False)
            self.chk_shadow.blockSignals(False)
            self.spin_radius.blockSignals(False)
            self.spin_poly_sides.blockSignals(False)
            self.combo_line_heads.blockSignals(False)
            
            if hasattr(item, 'pen'):
                self.spin_width.blockSignals(True)
                self.combo_style.blockSignals(True)
                self.combo_caps.blockSignals(True)
                self.combo_joins.blockSignals(True)
                self.slider_opacity.blockSignals(True)
                self.chk_stroke.blockSignals(True)
                self.chk_fill.blockSignals(True)
                
                pen = item.pen()
                self.spin_width.setValue(pen.width())
                styles = [Qt.SolidLine, Qt.DashLine, Qt.DotLine, Qt.DashDotLine]
                self.combo_style.setCurrentIndex(styles.index(pen.style()))
                
                caps = [Qt.FlatCap, Qt.RoundCap, Qt.SquareCap]
                self.combo_caps.setCurrentIndex(caps.index(pen.capStyle()))
                
                joins = [Qt.MiterJoin, Qt.RoundJoin, Qt.BevelJoin]
                self.combo_joins.setCurrentIndex(joins.index(pen.joinStyle()))
                
                self.slider_opacity.setValue(item.opacity() * 100)
                
                is_no_pen = (pen.style() == Qt.NoPen)
                self.chk_stroke.setChecked(not is_no_pen)
                
                is_no_brush = (item.brush().style() == Qt.NoBrush)
                self.chk_fill.setChecked(not is_no_brush)
                
                self.spin_width.blockSignals(False)
                self.combo_style.blockSignals(False)
                self.combo_caps.blockSignals(False)
                self.combo_joins.blockSignals(False)
                self.slider_opacity.blockSignals(False)
                self.chk_stroke.blockSignals(False)
                self.chk_fill.blockSignals(False)

    def update_color_swatches(self):
        self.btn_color.setStyleSheet(f"background-color: {self.scene.brush_color.name()};")
        self.btn_fill_color.setStyleSheet(f"background-color: {self.scene.fill_color.name()};")

    def update_item_x(self, val):
        if self.scene.selectedItems(): self.scene.selectedItems()[0].setX(val)

    def update_item_y(self, val):
        if self.scene.selectedItems(): self.scene.selectedItems()[0].setY(val)

    def update_item_w(self, val):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], (RoundedRectItem, QGraphicsEllipseItem, PolygonItem)):
            r = items[0].rect()
            old_w = r.width()
            if old_w == 0: return
            r.setWidth(val)
            if self.chk_lock_ratio.isChecked():
                ratio = r.height() / old_w
                r.setHeight(val * ratio)
            items[0].setRect(r)
            self.sync_properties_panel()

    def update_item_h(self, val):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], (RoundedRectItem, QGraphicsEllipseItem, PolygonItem)):
            r = items[0].rect()
            old_h = r.height()
            if old_h == 0: return
            r.setHeight(val)
            if self.chk_lock_ratio.isChecked():
                ratio = r.width() / old_h
                r.setWidth(val * ratio)
            items[0].setRect(r)
            self.sync_properties_panel()

    def update_item_scale_w(self, val):
        items = self.scene.selectedItems()
        if items:
            items[0].setScale(val / 100.0)

    def update_item_scale_h(self, val):
        items = self.scene.selectedItems()
        if items:
            items[0].setScale(val / 100.0)

    def update_item_rotation(self, val):
        if self.scene.selectedItems(): self.scene.selectedItems()[0].setRotation(val)

    def toggle_lock(self):
        item = self.scene.selectedItems()
        if item:
            locked = not self.btn_lock.isChecked()
            item[0].setFlag(QGraphicsItem.ItemIsMovable, locked)

    def toggle_shadow(self, enabled):
        for item in self.scene.selectedItems():
            if enabled:
                if not isinstance(item.graphicsEffect(), QGraphicsDropShadowEffect):
                    effect = QGraphicsDropShadowEffect()
                    effect.setBlurRadius(15)
                    effect.setColor(QColor(0, 0, 0, 150))
                    effect.setOffset(5, 5)
                    item.setGraphicsEffect(effect)
            else:
                item.setGraphicsEffect(None)

    def toggle_stroke(self, enabled):
        for item in self.scene.selectedItems():
            if hasattr(item, 'setPen'):
                pen = item.pen()
                if enabled:
                    pen.setStyle(self.scene.stroke_style)
                else:
                    pen.setStyle(Qt.NoPen)
                item.setPen(pen)
                if isinstance(item, ArrowPathItem):
                    item.update_arrow_path()

    def toggle_fill(self, enabled):
        for item in self.scene.selectedItems():
            if hasattr(item, 'setBrush'):
                if enabled:
                    item.setBrush(self.scene.fill_color)
                else:
                    item.setBrush(Qt.NoBrush)

    def change_radius(self, val):
        for item in self.scene.selectedItems():
            if isinstance(item, RoundedRectItem):
                item.setRadius(val)

    def change_poly_sides(self, val):
        for item in self.scene.selectedItems():
            if isinstance(item, PolygonItem):
                item.setSides(val)

    def change_line_heads(self, index):
        for item in self.scene.selectedItems():
            if isinstance(item, ArrowPathItem):
                if index == 0: item.setStartArrow(False); item.setEndArrow(False)
                elif index == 1: item.setStartArrow(True); item.setEndArrow(False)
                elif index == 2: item.setStartArrow(False); item.setEndArrow(True)
                elif index == 3: item.setStartArrow(True); item.setEndArrow(True)

    def change_cap_style(self, index):
        caps = [Qt.FlatCap, Qt.RoundCap, Qt.SquareCap]
        self.scene.cap_style = caps[index]
        for item in self.scene.selectedItems():
            if hasattr(item, 'setPen'):
                pen = item.pen()
                pen.setCapStyle(caps[index])
                item.setPen(pen)
                if isinstance(item, ArrowPathItem):
                    item.update_arrow_path()

    def change_join_style(self, index):
        joins = [Qt.MiterJoin, Qt.RoundJoin, Qt.BevelJoin]
        self.scene.join_style = joins[index]
        for item in self.scene.selectedItems():
            if hasattr(item, 'setPen'):
                pen = item.pen()
                pen.setJoinStyle(joins[index])
                item.setPen(pen)
                if isinstance(item, ArrowPathItem):
                    item.update_arrow_path()

    # --- Pathfinder (Boolean Operations) ---
    def boolean_unite(self):
        items = self.scene.selectedItems()
        if len(items) < 2: return
        paths = [i.mapToScene(i.shape()) for i in items]
        united = paths[0]
        for p in paths[1:]:
            united = united.united(p)
            
        new_item = QGraphicsPathItem(united)
        new_item.setPen(items[0].pen())
        new_item.setBrush(items[0].brush())
        new_item.setPos(0,0)
        self.scene._make_item_selectable(new_item)
        self.scene.undo_stack.push(BooleanCommand(self.scene, items, new_item))
        self.scene.clearSelection()
        new_item.setSelected(True)

    def boolean_subtract(self):
        items = self.scene.selectedItems()
        if len(items) < 2: return
        items.sort(key=lambda x: x.zValue(), reverse=True)
        paths = [i.mapToScene(i.shape()) for i in items]
        result = paths[0]
        for p in paths[1:]:
            result = result.subtracted(p)
            
        new_item = QGraphicsPathItem(result)
        new_item.setPen(items[-1].pen())
        new_item.setBrush(items[-1].brush())
        new_item.setPos(0,0)
        self.scene._make_item_selectable(new_item)
        self.scene.undo_stack.push(BooleanCommand(self.scene, items, new_item))
        self.scene.clearSelection()
        new_item.setSelected(True)

    def boolean_intersect(self):
        items = self.scene.selectedItems()
        if len(items) < 2: return
        paths = [i.mapToScene(i.shape()) for i in items]
        result = paths[0]
        for p in paths[1:]:
            result = result.intersected(p)
            
        new_item = QGraphicsPathItem(result)
        new_item.setPen(items[0].pen())
        new_item.setBrush(items[0].brush())
        new_item.setPos(0,0)
        self.scene._make_item_selectable(new_item)
        self.scene.undo_stack.push(BooleanCommand(self.scene, items, new_item))
        self.scene.clearSelection()
        new_item.setSelected(True)

    # --- Align, Distribute & Flip ---
    def align_items(self, align_type):
        items = self.scene.selectedItems()
        if len(items) < 2: return
        
        rects = [i.sceneBoundingRect() for i in items]
        if align_type == 'left':
            min_x = min(r.x() for r in rects)
            for i, r in zip(items, rects): i.moveBy(min_x - r.x(), 0)
        elif align_type == 'right':
            max_x = max(r.x() + r.width() for r in rects)
            for i, r in zip(items, rects): i.moveBy(max_x - (r.x() + r.width()), 0)
        elif align_type == 'hcenter':
            min_x = min(r.x() for r in rects)
            max_x = max(r.x() + r.width() for r in rects)
            center = (min_x + max_x) / 2
            for i, r in zip(items, rects): i.moveBy(center - (r.x() + r.width()/2), 0)
        elif align_type == 'top':
            min_y = min(r.y() for r in rects)
            for i, r in zip(items, rects): i.moveBy(0, min_y - r.y())
        elif align_type == 'bottom':
            max_y = max(r.y() + r.height() for r in rects)
            for i, r in zip(items, rects): i.moveBy(0, max_y - (r.y() + r.height()))
        elif align_type == 'vcenter':
            min_y = min(r.y() for r in rects)
            max_y = max(r.y() + r.height() for r in rects)
            center = (min_y + max_y) / 2
            for i, r in zip(items, rects): i.moveBy(0, center - (r.y() + r.height()/2))
        self.sync_properties_panel()

    def distribute_h(self):
        items = self.scene.selectedItems()
        if len(items) < 3: return
        items.sort(key=lambda i: i.sceneBoundingRect().center().x())
        
        first = items[0].sceneBoundingRect()
        last = items[-1].sceneBoundingRect()
        total_span = last.right() - first.left()
        items_width = sum(i.sceneBoundingRect().width() for i in items)
        gap = (total_span - items_width) / (len(items) - 1)
        
        current_x = first.left()
        for i, item in enumerate(items):
            r = item.sceneBoundingRect()
            item.moveBy(current_x - r.left(), 0)
            current_x += r.width() + gap

    def distribute_v(self):
        items = self.scene.selectedItems()
        if len(items) < 3: return
        items.sort(key=lambda i: i.sceneBoundingRect().center().y())
        
        first = items[0].sceneBoundingRect()
        last = items[-1].sceneBoundingRect()
        total_span = last.bottom() - first.top()
        items_height = sum(i.sceneBoundingRect().height() for i in items)
        gap = (total_span - items_height) / (len(items) - 1)
        
        current_y = first.top()
        for i, item in enumerate(items):
            r = item.sceneBoundingRect()
            item.moveBy(0, current_y - r.top())
            current_y += r.height() + gap

    def flip_selected(self, axis):
        for item in self.scene.selectedItems():
            t = item.transform()
            if axis == 'h': t.scale(-1, 1)
            else: t.scale(1, -1)
            item.setTransform(t)

    # --- Appearance ---
    def pick_stroke_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.scene.brush_color = color
            self.update_color_swatches()
            for item in self.scene.selectedItems():
                if hasattr(item, 'setPen'):
                    pen = item.pen()
                    if pen.style() == Qt.NoPen: pen.setStyle(self.scene.stroke_style)
                    pen.setColor(color)
                    item.setPen(pen)
                    if isinstance(item, ArrowPathItem):
                        item.update_arrow_path()
                elif hasattr(item, 'setDefaultTextColor'):
                    item.setDefaultTextColor(color)

    def pick_fill_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.scene.fill_color = color
            self.update_color_swatches()
            for item in self.scene.selectedItems():
                if hasattr(item, 'setBrush'):
                    item.setBrush(color)
                    self.chk_fill.blockSignals(True)
                    self.chk_fill.setChecked(True)
                    self.chk_fill.blockSignals(False)

    def change_width(self, val):
        self.scene.brush_width = val
        for item in self.scene.selectedItems():
            if hasattr(item, 'setPen'):
                pen = item.pen()
                pen.setWidth(val)
                item.setPen(pen)
                if isinstance(item, ArrowPathItem):
                    item.update_arrow_path()

    def change_stroke_style(self, index):
        styles = [Qt.SolidLine, Qt.DashLine, Qt.DotLine, Qt.DashDotLine]
        self.scene.stroke_style = styles[index]
        for item in self.scene.selectedItems():
            if hasattr(item, 'setPen'):
                pen = item.pen()
                if pen.style() != Qt.NoPen:
                    pen.setStyle(styles[index])
                    item.setPen(pen)
                    if isinstance(item, ArrowPathItem):
                        item.update_arrow_path()

    def change_opacity(self, val):
        for item in self.scene.selectedItems(): item.setOpacity(val / 100.0)

    # --- Z-Ordering & Grouping ---
    def bring_forward(self):
        sel_items = sorted(self.scene.selectedItems(), key=lambda x: x.zValue())
        all_items = self.scene.items()
        for item in sel_items:
            idx = all_items.index(item)
            if idx > 0:
                item_above = all_items[idx-1]
                item_above.stackBefore(item)
        self.refresh_layers()

    def send_backward(self):
        sel_items = sorted(self.scene.selectedItems(), key=lambda x: x.zValue(), reverse=True)
        all_items = self.scene.items()
        for item in sel_items:
            idx = all_items.index(item)
            if idx < len(all_items) - 1:
                item_below = all_items[idx+1]
                item.stackBefore(item_below)
        self.refresh_layers()

    def bring_to_front(self):
        if self.scene.selectedItems():
            all_items = self.scene.items()
            max_z = max([i.zValue() for i in all_items] + [0])
            for item in self.scene.selectedItems():
                max_z += 1
                item.setZValue(max_z)
            self.refresh_layers()

    def send_to_back(self):
        if self.scene.selectedItems():
            all_items = self.scene.items()
            min_z = min([i.zValue() for i in all_items] + [0])
            for item in self.scene.selectedItems():
                min_z -= 1
                item.setZValue(min_z)
            self.refresh_layers()

    def group_selected(self):
        items = self.scene.selectedItems()
        if len(items) > 1:
            group = self.scene.createItemGroup(items)
            group.setFlag(QGraphicsItemGroup.ItemIsMovable)
            group.setFlag(QGraphicsItemGroup.ItemIsSelectable)
            group.setFlag(QGraphicsItemGroup.ItemIsRotatable)
            self.scene.clearSelection()
            group.setSelected(True)
            self.refresh_layers()

    def ungroup_selected(self):
        items = self.scene.selectedItems()
        for item in items:
            if isinstance(item, QGraphicsItemGroup):
                self.scene.destroyItemGroup(item)
        self.refresh_layers()

    # --- Clipboard & Styles ---
    def copy_selected(self):
        self.clipboard_items = [item.clone() for item in self.scene.selectedItems()]

    def cut_selected(self):
        self.copy_selected()
        self.scene.delete_selected()

    def paste_items(self, offset=20):
        self.scene.clearSelection()
        new_items = []
        for item in self.clipboard_items:
            new_item = item.clone()
            new_item.setPos(item.pos() + QPointF(offset, offset))
            new_item.setFlag(QGraphicsItem.ItemIsSelectable)
            new_item.setFlag(QGraphicsItem.ItemIsMovable)
            new_item.setFlag(QGraphicsItem.ItemIsRotatable)
            self.scene.undo_stack.push(AddItemCommand(self.scene, new_item))
            new_items.append(new_item)
        
        self.clipboard_items = [item.clone() for item in new_items]
        for ni in new_items: ni.setSelected(True)
        self.sync_properties_panel()

    def duplicate_selected(self):
        self.copy_selected()
        self.paste_items(20)

    def duplicate_in_place(self):
        self.copy_selected()
        self.paste_items(0)

    def copy_style(self):
        items = self.scene.selectedItems()
        if items:
            item = items[0]
            self.style_clipboard = {
                'pen': item.pen() if hasattr(item, 'pen') else None,
                'brush': item.brush() if hasattr(item, 'brush') else None,
                'opacity': item.opacity(),
                'font': item.font() if hasattr(item, 'font') else None,
                'text_color': item.defaultTextColor() if hasattr(item, 'defaultTextColor') else None
            }

    def paste_style(self):
        if not self.style_clipboard: return
        for item in self.scene.selectedItems():
            if self.style_clipboard['pen'] and hasattr(item, 'setPen'):
                item.setPen(self.style_clipboard['pen'])
                if isinstance(item, ArrowPathItem):
                    item.update_arrow_path()
            if self.style_clipboard['brush'] and hasattr(item, 'setBrush'):
                item.setBrush(self.style_clipboard['brush'])
            if self.style_clipboard['font'] and hasattr(item, 'setFont'):
                item.setFont(self.style_clipboard['font'])
            if self.style_clipboard['text_color'] and hasattr(item, 'setDefaultTextColor'):
                item.setDefaultTextColor(self.style_clipboard['text_color'])
            item.setOpacity(self.style_clipboard['opacity'])
        self.sync_properties_panel()

    # --- Project Save/Load ---
    def serialize_item(self, item):
        data = {
            'type': item.__class__.__name__,
            'pos': {'x': item.pos().x(), 'y': item.pos().y()},
            'rotation': item.rotation(),
            'scale': item.scale(),
            'opacity': item.opacity(),
            'z': item.zValue(),
            'name': item.data(NAME_ROLE)
        }
        if hasattr(item, 'pen'):
            p = item.pen()
            data['pen'] = {'color': p.color().name(), 'width': p.width(), 'style': int(p.style()), 'cap': int(p.capStyle()), 'join': int(p.joinStyle())}
        if hasattr(item, 'brush'):
            b = item.brush()
            data['brush'] = {'color': b.color().name(), 'style': int(b.style())}
        if isinstance(item, RoundedRectItem):
            data['rect'] = {'x': item.rect().x(), 'y': item.rect().y(), 'w': item.rect().width(), 'h': item.rect().height()}
            data['radius'] = item.radius()
        elif isinstance(item, (QGraphicsEllipseItem, PolygonItem)):
            data['rect'] = {'x': item.rect().x(), 'y': item.rect().y(), 'w': item.rect().width(), 'h': item.rect().height()}
            if isinstance(item, PolygonItem):
                data['sides'] = item.sides()
        elif isinstance(item, ArrowPathItem):
            polys = item.base_path().toSubpathPolygons(item.transform())
            data['path_polys'] = [[[p.x(), p.y()] for p in poly] for poly in polys]
            data['start_arrow'] = item.startArrow()
            data['end_arrow'] = item.endArrow()
        elif isinstance(item, QGraphicsPathItem):
            polys = item.path().toSubpathPolygons(item.transform())
            data['path_polys'] = [[[p.x(), p.y()] for p in poly] for poly in polys]
        elif isinstance(item, QGraphicsTextItem):
            data['text'] = item.toPlainText()
            data['font'] = {'family': item.font().family(), 'size': item.font().pointSize()}
        elif isinstance(item, QGraphicsPixmapItem):
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            item.pixmap().save(buffer, "PNG")
            data['pixmap'] = byte_array.toBase64().data().decode()
            
        return data

    def save_project(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project", "project.json", "JSON File (*.json)")
        if file_path:
            data = [self.serialize_item(item) for item in self.scene.items()]
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)

    def load_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "JSON File (*.json)")
        if file_path:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            self.scene.clear()
            for d in data:
                if d['type'] == 'RoundedRectItem':
                    item = RoundedRectItem(QRectF(d['rect']['x'], d['rect']['y'], d['rect']['w'], d['rect']['h']))
                    item.setRadius(d['radius'])
                elif d['type'] == 'QGraphicsEllipseItem':
                    item = QGraphicsEllipseItem(QRectF(d['rect']['x'], d['rect']['y'], d['rect']['w'], d['rect']['h']))
                elif d['type'] == 'PolygonItem':
                    item = PolygonItem()
                    item.setSides(d.get('sides', 5))
                    item.setRect(QRectF(d['rect']['x'], d['rect']['y'], d['rect']['w'], d['rect']['h']))
                elif d['type'] == 'ArrowPathItem':
                    item = ArrowPathItem()
                    path = QPainterPath()
                    for poly in d.get('path_polys', []):
                        if len(poly) > 0:
                            path.moveTo(poly[0][0], poly[0][1])
                            for p in poly[1:]:
                                path.lineTo(p[0], p[1])
                    item.setBasePath(path)
                    item.setStartArrow(d.get('start_arrow', False))
                    item.setEndArrow(d.get('end_arrow', False))
                elif d['type'] == 'QGraphicsPathItem':
                    item = QGraphicsPathItem()
                    path = QPainterPath()
                    for poly in d.get('path_polys', []):
                        if len(poly) > 0:
                            path.moveTo(poly[0][0], poly[0][1])
                            for p in poly[1:]:
                                path.lineTo(p[0], p[1])
                    item.setPath(path)
                elif d['type'] == 'QGraphicsTextItem':
                    item = QGraphicsTextItem(d['text'])
                    item.setFont(QFont(d['font']['family'], d['font']['size']))
                elif d['type'] == 'QGraphicsPixmapItem':
                    if 'pixmap' in d:
                        byte_array = QByteArray.fromBase64(d['pixmap'].encode())
                        pixmap = QPixmap()
                        pixmap.loadFromData(byte_array, "PNG")
                        item = QGraphicsPixmapItem(pixmap)
                    else:
                        continue
                else:
                    continue
                    
                item.setPos(d['pos']['x'], d['pos']['y'])
                item.setRotation(d['rotation'])
                item.setScale(d['scale'])
                item.setOpacity(d['opacity'])
                item.setZValue(d['z'])
                if d.get('name'): item.setData(NAME_ROLE, d['name'])
                
                if 'pen' in d:
                    p = QPen(QColor(d['pen']['color']), d['pen']['width'], Qt.PenStyle(d['pen']['style']), Qt.PenCapStyle(d['pen']['cap']), Qt.PenJoinStyle(d['pen']['join']))
                    item.setPen(p)
                if 'brush' in d:
                    item.setBrush(QBrush(QColor(d['brush']['color']), Qt.BrushStyle(d['brush']['style'])))
                    
                self.scene._make_item_selectable(item)
                self.scene.addItem(item)
            self.refresh_layers()

    # --- Import/Export ---
    def import_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                item = QGraphicsPixmapItem(pixmap)
                item.setFlag(QGraphicsPixmapItem.ItemIsMovable)
                item.setFlag(QGraphicsPixmapItem.ItemIsSelectable)
                item.setFlag(QGraphicsPixmapItem.ItemIsRotatable)
                center = self.view.mapToScene(self.view.viewport().rect().center())
                item.setPos(center.x() - pixmap.width()/2, center.y() - pixmap.height()/2)
                self.scene.undo_stack.push(AddItemCommand(self.scene, item))
                self.set_mode('select')

    def import_svg_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open SVG", "", "SVG Files (*.svg)")
        if file_path:
            item = QGraphicsSvgItem(file_path)
            item.setFlag(QGraphicsSvgItem.ItemIsMovable)
            item.setFlag(QGraphicsSvgItem.ItemIsSelectable)
            item.setFlag(QGraphicsSvgItem.ItemIsRotatable)
            center = self.view.mapToScene(self.view.viewport().rect().center())
            item.setPos(center.x() - 50, center.y() - 50)
            self.scene.undo_stack.push(AddItemCommand(self.scene, item))
            self.set_mode('select')

    def export_canvas_png(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Canvas as PNG", "canvas_export.png", "PNG Image (*.png)")
        if file_path:
            if self.chk_export_sel.isChecked() and self.scene.selectedItems():
                rects = [i.sceneBoundingRect() for i in self.scene.selectedItems()]
                items_rect = rects[0]
                for r in rects[1:]:
                    items_rect = items_rect.united(r)
            else:
                items_rect = self.scene.itemsBoundingRect()
                
            if items_rect.isNull(): return
            rect = items_rect.adjusted(-20, -20, 20, 20)
            
            scale = self.spin_export_scale.value()
            img_size = rect.size().toSize() * scale
            image = QImage(img_size, QImage.Format_ARGB32)
            
            if self.chk_transparent.isChecked():
                image.fill(Qt.transparent)
            else:
                image.fill(Qt.white)
                
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.scale(scale, scale)
            target_rect = QRectF(0, 0, rect.width(), rect.height())
            self.scene.render(painter, target_rect, rect)
            painter.end()
            image.save(file_path)

    def export_canvas_svg(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Canvas as SVG", "canvas_export.svg", "SVG File (*.svg)")
        if file_path:
            if self.chk_export_sel.isChecked() and self.scene.selectedItems():
                rects = [i.sceneBoundingRect() for i in self.scene.selectedItems()]
                items_rect = rects[0]
                for r in rects[1:]:
                    items_rect = items_rect.united(r)
            else:
                items_rect = self.scene.itemsBoundingRect()
                
            if items_rect.isNull(): return
            rect = items_rect.adjusted(-20, -20, 20, 20)
            
            generator = QSvgGenerator()
            generator.setFileName(file_path)
            generator.setSize(rect.size().toSize())
            generator.setViewBox(rect)
            generator.setTitle("Canvas Export")
            
            painter = QPainter(generator)
            painter.setRenderHint(QPainter.Antialiasing)
            self.scene.render(painter, QRectF(generator.viewBox()), rect)
            painter.end()

    def export_canvas_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Canvas as PDF", "canvas_export.pdf", "PDF File (*.pdf)")
        if file_path:
            if self.chk_export_sel.isChecked() and self.scene.selectedItems():
                rects = [i.sceneBoundingRect() for i in self.scene.selectedItems()]
                items_rect = rects[0]
                for r in rects[1:]:
                    items_rect = items_rect.united(r)
            else:
                items_rect = self.scene.itemsBoundingRect()
                
            if items_rect.isNull(): return
            rect = items_rect.adjusted(-20, -20, 20, 20)
            
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(file_path)
            printer.setPageSize(QPageSize(rect.size().toSize(), QPageSize.Point))
            
            painter = QPainter(printer)
            painter.setRenderHint(QPainter.Antialiasing)
            self.scene.render(painter, QRectF(), rect)
            painter.end()

    def fit_to_view(self):
        rect = self.scene.itemsBoundingRect()
        if not rect.isNull():
            self.view.fitInView(rect, Qt.KeepAspectRatio)
            self.update_status_bar()

    def zoom_100(self):
        self.view.resetTransform()
        self.update_status_bar()

    def clear_canvas(self):
        self.scene.clear()
        self.refresh_layers()

    def toggle_fullscreen(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())