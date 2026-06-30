import io
import os
import re
import subprocess
import sys
import tempfile
import uuid
from copy import deepcopy


from PIL import Image, ImageDraw, ImageFilter
from PyQt6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QImage,
    QKeyEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
    QMenu
)


class Layer:
    """Representa uma camada de imagem"""

    def __init__(self, name="Layer", image=None, x=0, y=0):
        self.id = str(uuid.uuid4())
        self.name = name
        self.image = image  # PIL Image (RGBA)
        self.x = x  # Posição X no canvas
        self.y = y  # Posição Y no canvas
        self.visible = True
        self.locked = False
        self.opacity = 255  # 0-255

    def copy(self):
        """Cria uma cópia do layer"""
        new_layer = Layer(
            self.name, self.image.copy() if self.image else None, self.x, self.y
        )
        new_layer.visible = self.visible
        new_layer.locked = self.locked
        new_layer.opacity = self.opacity
        return new_layer


class LayerWidget(QFrame):


    selected = pyqtSignal(str)  # Emite o ID do layer
    visibilityChanged = pyqtSignal(str, bool)  # ID e estado de visibilidade
    opacityChanged = pyqtSignal(str, int)  # ID e valor de opacidade

    def __init__(self, layer, is_main=False, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.is_main = is_main
        self.is_selected = False

        self.setFixedHeight(50)
        self.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QFrame:hover {
                background-color: #454545;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Checkbox de visibilidade
        self.chk_visible = QCheckBox()
        self.chk_visible.setChecked(layer.visible)
        self.chk_visible.setFixedWidth(20)
        self.chk_visible.stateChanged.connect(self.on_visibility_changed)
        layout.addWidget(self.chk_visible)

        # Thumbnail
        # self.lbl_thumbnail = QLabel()
        # self.lbl_thumbnail.setFixedSize(40, 40)
        # self.lbl_thumbnail.setStyleSheet(
            # "background-color: #222; border: 1px solid #444;"
        # )
        # self.lbl_thumbnail.setScaledContents(True)
        # self.update_thumbnail()
        # layout.addWidget(self.lbl_thumbnail)

        # Nome do layer
        name_text = f"🔒 {layer.name}" if is_main else layer.name
        self.lbl_name = QLabel(name_text)
        self.lbl_name.setStyleSheet("color: white; font-size: 11px;")
        layout.addWidget(self.lbl_name, 1)

        # Indicador de Main
        if is_main:
            lbl_main = QLabel("MAIN")
            lbl_main.setStyleSheet("color: #ffa500; font-size: 9px; font-weight: bold;")
            layout.addWidget(lbl_main)

    # def update_thumbnail(self):
    
        # if self.layer.image:
     
            # thumb = self.layer.image.copy()
            # thumb.thumbnail((40, 40), Image.NEAREST)

 
            # if thumb.mode != "RGBA":
                # thumb = thumb.convert("RGBA")
            # data = thumb.tobytes("raw", "RGBA")
            # qimage = QImage(
                # data, thumb.width, thumb.height, QImage.Format.Format_RGBA8888
            # )
            # pixmap = QPixmap.fromImage(qimage)
            # self.lbl_thumbnail.setPixmap(pixmap)
        # else:
            # self.lbl_thumbnail.clear()

    def set_selected(self, selected):
        """Define se este layer está selecionado"""
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                QFrame {
                    background-color: #007acc;
                    border: 2px solid #0099ff;
                    border-radius: 3px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #3a3a3a;
                    border: 1px solid #555;
                    border-radius: 3px;
                }
                QFrame:hover {
                    background-color: #454545;
                }
            """)

    def on_visibility_changed(self, state):

        self.layer.visible = state == Qt.CheckState.Checked.value
        self.visibilityChanged.emit(self.layer.id, self.layer.visible)

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.layer.id)
        super().mousePressEvent(event)


class DraggableLayerItem(QGraphicsPixmapItem):


    def __init__(self, layer, parent_widget):
        super().__init__()
        self.layer = layer
        self.parent_widget = parent_widget
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(
            QGraphicsPixmapItem.GraphicsItemFlag.ItemSendsGeometryChanges, True
        )
        self.setAcceptHoverEvents(True)

    def itemChange(self, change, value):
        if change == QGraphicsPixmapItem.GraphicsItemChange.ItemPositionChange:
            # Atualiza a posição do layer
            new_pos = value
            self.layer.x = int(new_pos.x())
            self.layer.y = int(new_pos.y())
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        if not self.layer.locked:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)


if getattr(sys, 'frozen', False):
    _base_path = os.path.dirname(sys.executable)
else:
    _base_path = os.path.dirname(os.path.abspath(__file__))

try:
    import numpy as np
    import torch
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    ESRGAN_AVAILABLE = True
except ImportError:
    ESRGAN_AVAILABLE = False

WAIFU_EXE = os.path.join(_base_path, "data", "upscale2.exe")
WAIFU_AVAILABLE = os.path.isfile(WAIFU_EXE)



class GridOverlay(QGraphicsObject):
    positionChanged = pyqtSignal(int, int)

    def __init__(self, cell_size=32, rows=1, cols=1, subdivisions=False):
        super().__init__()
        self.cell_size = cell_size
        self.rows = rows
        self.cols = cols
        self.subdivisions = subdivisions
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(10)

    def boundingRect(self):
        width = self.cols * self.cell_size
        height = self.rows * self.cell_size
        return QRectF(0, 0, width, height)

    def paint(self, painter, option, widget):
        width = self.cols * self.cell_size
        height = self.rows * self.cell_size

        pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRect(0, 0, width, height)

        if self.subdivisions or (self.rows > 1 or self.cols > 1):
            for c in range(1, self.cols):
                x = c * self.cell_size
                painter.drawLine(x, 0, x, height)

            for r in range(1, self.rows):
                y = r * self.cell_size
                painter.drawLine(0, y, width, y)

        painter.fillRect(0, 0, width, height, QColor(255, 255, 255, 30))

    def itemChange(self, change, value):
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            self.positionChanged.emit(int(new_pos.x()), int(new_pos.y()))
        return super().itemChange(change, value)

    def update_grid(self, rows, cols, subdivisions, cell_size=None):
        self.rows = rows
        self.cols = cols
        self.subdivisions = subdivisions
        if cell_size is not None:
            self.cell_size = cell_size
        self.prepareGeometryChange()
        self.update()


class FineGridOverlay(QGraphicsObject):
    def __init__(self, image_rect, grid_spacing=4):
        super().__init__()
        self.image_rect = image_rect
        self.grid_spacing = grid_spacing
        self.setZValue(5)
        self.visible = False

    def boundingRect(self):
        return self.image_rect.adjusted(-1, -1, 1, 1)

    def paint(self, painter, option, widget):
        if not self.visible:
            return

        rect = self.image_rect

        # Grid fino
        pen = QPen(QColor(255, 255, 255, 40), 1, Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        painter.setPen(pen)

        # Linhas verticais
        x = 0
        while x <= rect.width():
            painter.drawLine(int(x), 0, int(x), int(rect.height()))
            x += self.grid_spacing

        # Linhas horizontais
        y = 0
        while y <= rect.height():
            painter.drawLine(0, int(y), int(rect.width()), int(y))
            y += self.grid_spacing

        # Borda da imagem em vermelho
        border_pen = QPen(QColor(255, 100, 100, 200), 3, Qt.PenStyle.SolidLine)
        border_pen.setCosmetic(True)
        painter.setPen(border_pen)
        painter.drawRect(rect)

    def set_visible(self, visible):
        self.visible = visible
        self.update()

    def update_rect(self, new_rect):
        self.prepareGeometryChange()
        self.image_rect = new_rect
        self.update()

    def set_spacing(self, spacing):
        self.grid_spacing = spacing
        self.update()


class SelectionRectangle(QGraphicsRectItem):
    def __init__(self):
        super().__init__()
        self.setFlag(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False
        )  # Desabilitado por padrão
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(15)

        pen = QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(0, 150, 255, 30)))

        self.setAcceptHoverEvents(True)

        # Armazena a imagem selecionada como um pixmap item
        self.selected_pixmap_item = None
        self.original_rect = None

    def set_rect(self, rect):
        """Define o retângulo de seleção"""
        self.setRect(rect)
        self.original_rect = rect

    def hoverEnterEvent(self, event):
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Restaura o cursor ao sair da seleção"""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Restaura o cursor após arrastar"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().mouseReleaseEvent(event)
        
        
class EraserOverlay(QGraphicsObject):

    def __init__(self):
        super().__init__()
        self.size = 10
        self.position = QPointF(0, 0)
        self.visible = False
        self.setZValue(100)  # Mantém sempre no topo
        
    def boundingRect(self):
        radius = self.size / 2
        return QRectF(-radius, -radius, self.size, self.size)
    
    def paint(self, painter, option, widget):
        if not self.visible:
            return
        
        radius = self.size / 2
        
        # Borda simples (removemos a mira e o preenchimento para não borrar pincéis pequenos)
        pen = QPen(QColor(255, 100, 100, 200), 1, Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, 0), radius, radius)
    
    def setSize(self, size):
        self.prepareGeometryChange()
        self.size = size
        self.update()
    
    def setVisible(self, visible):
        self.visible = visible
        self.update()
    
    def updatePosition(self, pos):
        self.setPos(pos)
        


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.zoom_factor = 1.0

    def wheelEvent(self, event: QWheelEvent):
        modifiers = QApplication.keyboardModifiers()

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            zoom_in_factor = 1.15
            zoom_out_factor = 1 / zoom_in_factor

            old_pos = self.mapToScene(event.position().toPoint())

            if event.angleDelta().y() > 0:
                factor = zoom_in_factor
                self.zoom_factor *= zoom_in_factor
            else:
                factor = zoom_out_factor
                self.zoom_factor *= zoom_out_factor

            if 0.1 <= self.zoom_factor <= 50.0:
                self.scale(factor, factor)

                new_pos = self.mapToScene(event.position().toPoint())
                delta = new_pos - old_pos
                self.translate(delta.x(), delta.y())

                if hasattr(self.parent(), "update_zoom_label"):
                    self.parent().update_zoom_label(int(self.zoom_factor * 100))
            else:
                self.zoom_factor /= factor

            event.accept()
        else:
            super().wheelEvent(event)


class SliceWindow(QWidget):
    
    sprites_imported = pyqtSignal(list)    
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sprite Editor - Made by Sherrat")
        self.resize(900, 600)

        self.setWindowIcon(QIcon("editor.ico"))

        self.setStyleSheet("background-color: #494949; color: white;")
        self.original_image_pil = None
        self.current_image_pil = None
        self.sliced_images = []
        self.cell_size = 32
        self.color_picker_mode = False
        self.paint_color_picker_mode = False

        # Eraser tool
        self.eraser_mode = False
        self.eraser_size = 10
        self.eraser_feathering = 0  # NOVA VARIÁVEL
        self.last_eraser_point = None
        
        self.cut_size_mode = False
        self.rotate_fine_angle = 0             
        self.cut_rect_item = None
        self.is_drawing_cut_rect = False
        self.cut_start_pos = None        

        self.paint_mode = False
        self.paint_size = 5
        self.paint_color = QColor(0, 0, 0, 255)
        self.last_paint_point = None
        self.paint_feathering = 0

        self.brush_type = "Circle"
        self.spray_density = 0.3  # 0–1, fração de pontos pintados no círculo
        self.texture_brush_image = None  # PIL.Image para textura do pincel

        self.outline_color = QColor(0, 0, 0, 255)  # Preto por padrão

        self.selection_mode = False
        self.selection_start = None
        self.selection_rect_item = None
        self.is_drawing_selection = False
        self.selected_image_data = None

        self.is_moving_selection = False
        self.move_start_pos = None
        self.selection_image_backup = None  # Backup da área original
        self.floating_selection_pixmap = None

        # Fine Grid
        self.fine_grid_item = None
        self.fine_grid_enabled = False
        self.fine_grid_spacing = 32

        # === LAYERS SYSTEM ===
        self.layers = []  # Lista de Layer objects
        self.active_layer_id = None  # ID do layer ativo
        self.layer_widgets = {}  # Mapeamento de ID -> LayerWidget
        self.layer_graphics_items = {}  # Mapeamento de ID -> DraggableLayerItem
        self.is_dragging_layer = False
        self.layer_drag_start = None

        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_steps = 20

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet("background-color: #333; border-bottom: 1px solid #222;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 5, 10, 5)

        btn_open = QPushButton("Open Image")
        btn_open.setStyleSheet("background-color: #555; padding: 5px;")
        btn_open.clicked.connect(self.open_image)
        tb_layout.addWidget(btn_open)

        btn_export_project = QPushButton("Export Imagem Completa ")
        btn_export_project.setStyleSheet(
            "background-color: #28a745; padding: 5px; font-weight: bold;"
        )
        btn_export_project.clicked.connect(self.export_full_project)
        tb_layout.addWidget(btn_export_project)

        tb_layout.addSpacing(20)

        lbl_zoom_title = QLabel("Zoom:")
        lbl_zoom_title.setStyleSheet("color: white; font-weight: bold;")
        tb_layout.addWidget(lbl_zoom_title)

        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(10, 5000)
        self.slider_zoom.setValue(100)
        self.slider_zoom.setFixedWidth(150)
        self.slider_zoom.setToolTip("Ctrl+Scroll também altera o Zoom")
        self.slider_zoom.valueChanged.connect(self.on_zoom_change)
        tb_layout.addWidget(self.slider_zoom)

        self.lbl_zoom_val = QLabel("100%")
        self.lbl_zoom_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_zoom_val.setFixedWidth(50)
        self.lbl_zoom_val.setStyleSheet("color: white;")
        tb_layout.addWidget(self.lbl_zoom_val)

        tb_layout.addStretch()

        btn_rot_r = QPushButton("Rot 90°")
        btn_rot_r.clicked.connect(lambda: self.transform_image("rotate_90"))
        tb_layout.addWidget(btn_rot_r)

        btn_flip_h = QPushButton("Flip H")
        btn_flip_h.clicked.connect(lambda: self.transform_image("flip_h"))
        tb_layout.addWidget(btn_flip_h)

        main_layout.addWidget(toolbar)

        # Splitter principal (vertical) para dividir canvas e painel de layers
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(self.main_splitter, 1)

        # Container para o conteúdo principal (canvas + painéis laterais)
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_splitter.addWidget(content_widget)

        left_panel = QFrame()
        left_panel.setFixedWidth(283)
        left_panel.setStyleSheet(
            "QFrame { background-color: #444; border-right: 1px solid #222; } QLabel { color: #ddd; }"
        )
        lp_layout = QVBoxLayout(left_panel)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #222; background: #444; }
            QTabBar::tab { background: #333; color: #ddd; padding: 4px; min-width: 58px; }
            QTabBar::tab:selected { background: #555; color: white; }
        """)

        tab_resize = QWidget()
        tab_resize_layout = QVBoxLayout(tab_resize)

        grp_resize = QGroupBox("Resize Image")
        resize_layout = QGridLayout()

        resize_layout.addWidget(QLabel("Width:"), 0, 0)
        self.spin_resize_width = QSpinBox()
        self.spin_resize_width.setRange(1, 9999)
        self.spin_resize_width.setValue(32)
        self.spin_resize_width.valueChanged.connect(self.on_resize_width_change)
        resize_layout.addWidget(self.spin_resize_width, 0, 1)

        resize_layout.addWidget(QLabel("Height:"), 1, 0)
        self.spin_resize_height = QSpinBox()
        self.spin_resize_height.setRange(1, 9999)
        self.spin_resize_height.setValue(32)
        self.spin_resize_height.valueChanged.connect(self.on_resize_height_change)
        resize_layout.addWidget(self.spin_resize_height, 1, 1)

        self.chk_keep_aspect = QCheckBox("Keep Aspect Ratio")
        self.chk_keep_aspect.setChecked(True)
        resize_layout.addWidget(self.chk_keep_aspect, 2, 0, 1, 2)

        resize_layout.addWidget(QLabel("Method:"), 3, 0)
        self.combo_resize_method = QComboBox()
        self.combo_resize_method.addItems(
            ["Nearest (Pixel Art)", "Bilinear", "Bicubic", "Lanczos"]
        )
        self.combo_resize_method.setCurrentIndex(0)
        resize_layout.addWidget(self.combo_resize_method, 3, 1)

        self.btn_apply_resize = QPushButton("Apply Resize")
        self.btn_apply_resize.setStyleSheet(
            "background-color: #007acc; font-weight: bold;"
        )
        self.btn_apply_resize.clicked.connect(self.apply_resize)
        self.btn_apply_resize.setEnabled(False)
        resize_layout.addWidget(self.btn_apply_resize, 4, 0, 1, 2)

        self.btn_reset_image = QPushButton("Reset Original")
        self.btn_reset_image.clicked.connect(self.reset_to_original)
        self.btn_reset_image.setEnabled(False)
        resize_layout.addWidget(self.btn_reset_image, 5, 0, 1, 2)

        self.btn_reset_image = QPushButton("Reset Original")
        self.btn_reset_image.clicked.connect(self.reset_to_original)
        self.btn_reset_image.setEnabled(False)
        resize_layout.addWidget(self.btn_reset_image, 5, 0, 1, 2)


        self.btn_add_blank = QPushButton("Add Blank Image")
        self.btn_add_blank.setStyleSheet(
            "background-color: #6c757d; font-weight: bold; color: white;"
        )
        self.btn_add_blank.clicked.connect(self.add_blank_image)

        self.btn_add_blank.setEnabled(True)
        resize_layout.addWidget(self.btn_add_blank, 6, 0, 1, 2)

        self.btn_cut_size = QPushButton("Cut Size")
        self.btn_cut_size.setStyleSheet(
            "background-color: #ff6b35; font-weight: bold; color: white;"
        )
        self.btn_cut_size.setCheckable(True)
        self.btn_cut_size.clicked.connect(self.toggle_cut_size_mode)
        self.btn_cut_size.setEnabled(False)
        resize_layout.addWidget(self.btn_cut_size, 7, 0, 1, 2)


        self.btn_apply_cut = QPushButton("Apply Cut")
        self.btn_apply_cut.setStyleSheet(
            "background-color: #28a745; font-weight: bold; color: white;"
        )
        self.btn_apply_cut.clicked.connect(self.apply_cut_size)
        self.btn_apply_cut.setEnabled(False)
        resize_layout.addWidget(self.btn_apply_cut, 8, 0, 1, 2)


        grp_resize.setLayout(resize_layout)
        tab_resize_layout.addWidget(grp_resize)

        # ===== PIXEL SNAP (AI → Pixel Art) =====
        grp_pixel_snap = QGroupBox("Pixel Snap (AI → Pixel Art)")
        pixel_snap_layout = QGridLayout()

        # Posterizar
        self.chk_snap_posterize = QCheckBox("Posterizar Cores")
        self.chk_snap_posterize.setChecked(True)
        self.chk_snap_posterize.setToolTip("Reduz gradientes suaves para cores chapadas")
        pixel_snap_layout.addWidget(self.chk_snap_posterize, 0, 0)

        pixel_snap_layout.addWidget(QLabel("Níveis:"), 0, 1)
        self.spin_snap_posterize = QSpinBox()
        self.spin_snap_posterize.setRange(2, 32)
        self.spin_snap_posterize.setValue(8)
        self.spin_snap_posterize.setToolTip("Níveis por canal (2=muito reduzido, 8=suave)")
        pixel_snap_layout.addWidget(self.spin_snap_posterize, 0, 2)

        # Limitar paleta
        self.chk_snap_quantize = QCheckBox("Limitar Paleta")
        self.chk_snap_quantize.setChecked(False)
        self.chk_snap_quantize.setToolTip("Reduz o total de cores (K-means)")
        pixel_snap_layout.addWidget(self.chk_snap_quantize, 1, 0)

        pixel_snap_layout.addWidget(QLabel("Cores:"), 1, 1)
        self.spin_snap_colors = QSpinBox()
        self.spin_snap_colors.setRange(2, 256)
        self.spin_snap_colors.setValue(32)
        pixel_snap_layout.addWidget(self.spin_snap_colors, 1, 2)

        # Snap alpha
        self.chk_snap_alpha = QCheckBox("Snap Alpha (bordas duras)")
        self.chk_snap_alpha.setChecked(True)
        self.chk_snap_alpha.setToolTip("Binariza o canal alpha para bordas 100% nítidas")
        pixel_snap_layout.addWidget(self.chk_snap_alpha, 2, 0, 1, 3)

        # Botão
        self.btn_apply_pixel_snap = QPushButton("🎮 Apply Pixel Snap")
        self.btn_apply_pixel_snap.setStyleSheet(
            "background-color: #e91e63; font-weight: bold; color: white;"
        )
        self.btn_apply_pixel_snap.clicked.connect(self.apply_pixel_snap)
        self.btn_apply_pixel_snap.setEnabled(False)
        pixel_snap_layout.addWidget(self.btn_apply_pixel_snap, 3, 0, 1, 3)

        grp_pixel_snap.setLayout(pixel_snap_layout)
        tab_resize_layout.addWidget(grp_pixel_snap)

        grp_edges = QGroupBox("Outline")
        edges_layout = QGridLayout()

        # Outline Tool
        edges_layout.addWidget(QLabel("Outline:"), 2, 0, 1, 2)

        edges_layout.addWidget(QLabel("Color:"), 3, 0)
        self.btn_outline_color = QPushButton("Choose")
        self.btn_outline_color.setStyleSheet("background-color: #555;")
        self.btn_outline_color.clicked.connect(self.choose_outline_color)
        self.btn_outline_color.setEnabled(False)
        edges_layout.addWidget(self.btn_outline_color, 3, 1)

        self.lbl_outline_color_preview = QLabel()
        self.lbl_outline_color_preview.setFixedHeight(25)
        self.lbl_outline_color_preview.setStyleSheet(
            "background-color: #000000; border: 1px solid #222;"
        )
        edges_layout.addWidget(self.lbl_outline_color_preview, 4, 0, 1, 2)

        edges_layout.addWidget(QLabel("Thickness:"), 5, 0)
        self.spin_outline_thickness = QDoubleSpinBox()
        self.spin_outline_thickness.setRange(0.01, 20.0)
        self.spin_outline_thickness.setValue(2.0)
        self.spin_outline_thickness.setSingleStep(0.01)
        self.spin_outline_thickness.setDecimals(2)
        self.spin_outline_thickness.setSuffix("px")
        edges_layout.addWidget(self.spin_outline_thickness, 5, 1)

        edges_layout.addWidget(QLabel("Feathering:"), 6, 0)
        self.spin_outline_feathering = QSpinBox()
        self.spin_outline_feathering.setRange(0, 100)
        self.spin_outline_feathering.setValue(0)
        self.spin_outline_feathering.setSuffix("%")
        self.spin_outline_feathering.setToolTip(
            "0% = bordas duras, 100% = máxima suavização"
        )
        edges_layout.addWidget(self.spin_outline_feathering, 6, 1)

        self.btn_apply_outline = QPushButton("Apply Outline")
        self.btn_apply_outline.setStyleSheet(
            "background-color: #17a2b8; font-weight: bold;"
        )
        self.btn_apply_outline.clicked.connect(self.apply_outline)
        self.btn_apply_outline.setEnabled(False)
        edges_layout.addWidget(self.btn_apply_outline, 7, 0, 1, 2)

        # Edge Eraser
        edges_layout.addWidget(QLabel("Edge Eraser:"), 8, 0, 1, 2)

        edges_layout.addWidget(QLabel("Distance:"), 9, 0)
        self.spin_edge_eraser_distance = QDoubleSpinBox()
        self.spin_edge_eraser_distance.setRange(0.01, 50.0)
        self.spin_edge_eraser_distance.setValue(5.0)
        self.spin_edge_eraser_distance.setSingleStep(0.01)
        self.spin_edge_eraser_distance.setDecimals(2)
        self.spin_edge_eraser_distance.setSuffix("px")
        self.spin_edge_eraser_distance.setToolTip("Distância das bordas para apagar (use valores decimais para ajustes finos)")
        edges_layout.addWidget(self.spin_edge_eraser_distance, 9, 1)

        edges_layout.addWidget(QLabel("Feathering:"), 10, 0)
        self.spin_edge_eraser_feathering = QSpinBox()
        self.spin_edge_eraser_feathering.setRange(0, 100)
        self.spin_edge_eraser_feathering.setValue(0)
        self.spin_edge_eraser_feathering.setSuffix("%")
        edges_layout.addWidget(self.spin_edge_eraser_feathering, 10, 1)

        self.btn_erase_edges = QPushButton("Erase Edges")
        self.btn_erase_edges.setStyleSheet(
            "background-color: #dc3545; font-weight: bold;"
        )
        self.btn_erase_edges.clicked.connect(self.erase_edges)
        self.btn_erase_edges.setEnabled(False)
        edges_layout.addWidget(self.btn_erase_edges, 11, 0, 1, 2)

        grp_edges.setLayout(edges_layout)
        tab_resize_layout.addWidget(grp_edges)

        grp_sharpen = QGroupBox("Sharpening")
        sharpen_layout = QGridLayout()

        sharpen_layout.addWidget(QLabel("Radius:"), 0, 0)
        self.spin_sharpen_radius = QDoubleSpinBox()
        self.spin_sharpen_radius.setRange(0.1, 10.0)
        self.spin_sharpen_radius.setValue(2.0)
        self.spin_sharpen_radius.setSingleStep(0.1)
        self.spin_sharpen_radius.setToolTip("Raio do Unsharp Mask")
        sharpen_layout.addWidget(self.spin_sharpen_radius, 0, 1)

        sharpen_layout.addWidget(QLabel("Percent:"), 1, 0)
        self.spin_sharpen_percent = QSpinBox()
        self.spin_sharpen_percent.setRange(1, 500)
        self.spin_sharpen_percent.setValue(150)
        self.spin_sharpen_percent.setSuffix("%")
        self.spin_sharpen_percent.setToolTip("Força da nitidez")
        sharpen_layout.addWidget(self.spin_sharpen_percent, 1, 1)

        self.btn_apply_sharpen = QPushButton("Apply Sharpen")
        self.btn_apply_sharpen.setStyleSheet("background-color: #007acc; font-weight: bold; color: white;")
        self.btn_apply_sharpen.clicked.connect(self.apply_sharpen)
        self.btn_apply_sharpen.setEnabled(False)
        sharpen_layout.addWidget(self.btn_apply_sharpen, 2, 0, 1, 2)

        grp_sharpen.setLayout(sharpen_layout)
        tab_resize_layout.addWidget(grp_sharpen)

        tab_resize_layout.addStretch()

        tab_transparency = QWidget()
        tab_transparency_layout = QVBoxLayout(tab_transparency)

        # GRUPO 1: Remove Color (já existente)
        grp_transparency = QGroupBox("Remove Color")
        transparency_layout = QGridLayout()

        transparency_layout.addWidget(QLabel("Hex Color:"), 0, 0)
        self.line_hex_color = QLineEdit()
        self.line_hex_color.setPlaceholderText("#dcff73")
        self.line_hex_color.setMaxLength(7)
        self.line_hex_color.textChanged.connect(self.update_color_preview)
        transparency_layout.addWidget(self.line_hex_color, 0, 1)

        transparency_layout.addWidget(QLabel("Tolerance:"), 1, 0)
        self.spin_tolerance = QSpinBox()
        self.spin_tolerance.setRange(0, 442)
        self.spin_tolerance.setValue(10)
        self.spin_tolerance.setToolTip(
            "0 = cor exata, valores maiores = cores similares"
        )
        transparency_layout.addWidget(self.spin_tolerance, 1, 1)

        transparency_layout.addWidget(QLabel("Smoothness:"), 2, 0)
        self.spin_smoothness = QSpinBox()
        self.spin_smoothness.setRange(0, 200)
        self.spin_smoothness.setValue(10)
        self.spin_smoothness.setToolTip("Suaviza as bordas ao remover a cor")
        transparency_layout.addWidget(self.spin_smoothness, 2, 1)

        self.btn_pick_color = QPushButton("Pick Color from Image")
        self.btn_pick_color.setStyleSheet("background-color: #555;")
        self.btn_pick_color.clicked.connect(self.enable_color_picker)
        self.btn_pick_color.setEnabled(False)
        transparency_layout.addWidget(self.btn_pick_color, 3, 0, 1, 2)

        self.lbl_preview_color = QLabel()
        self.lbl_preview_color.setFixedHeight(30)
        self.lbl_preview_color.setStyleSheet(
            "background-color: #dcff73; border: 1px solid #222;"
        )
        transparency_layout.addWidget(self.lbl_preview_color, 4, 0, 1, 2)

        self.btn_remove_color = QPushButton("Remove Color")
        self.btn_remove_color.setStyleSheet(
            "background-color: #dc3545; font-weight: bold; color: white;"
        )
        self.btn_remove_color.clicked.connect(self.remove_color_to_transparent)
        self.btn_remove_color.setEnabled(False)
        transparency_layout.addWidget(self.btn_remove_color, 5, 0, 1, 2)

        grp_transparency.setLayout(transparency_layout)
        tab_transparency_layout.addWidget(grp_transparency)

        transparency_layout.addWidget(QLabel("Max Opacity to Remove (%):"), 7, 0)
        self.spin_remove_opacity = QSpinBox()
        self.spin_remove_opacity.setRange(0, 100)
        self.spin_remove_opacity.setValue(95)
        self.spin_remove_opacity.setSuffix("%")
        self.spin_remove_opacity.setToolTip("Remove todos os pixels com opacidade menor ou igual ao valor")
        transparency_layout.addWidget(self.spin_remove_opacity, 7, 1)

        self.btn_remove_by_opacity = QPushButton("Remove by Opacity")
        self.btn_remove_by_opacity.setStyleSheet(
            "background-color: #dc3545; font-weight: bold; color: white;"
        )
        self.btn_remove_by_opacity.clicked.connect(self.remove_by_opacity)
        self.btn_remove_by_opacity.setEnabled(False)
        transparency_layout.addWidget(self.btn_remove_by_opacity, 8, 0, 1, 2)

        # GRUPO 2: Color Adjustments (NOVO)
        grp_color_adjust = QGroupBox("Color Adjustments")
        color_adjust_layout = QGridLayout()

        # Brightness
        color_adjust_layout.addWidget(QLabel("Brightness:"), 0, 0)
        self.slider_brightness = QSlider(Qt.Orientation.Horizontal)
        self.slider_brightness.setRange(-100, 100)
        self.slider_brightness.setValue(0)
        self.slider_brightness.valueChanged.connect(self.on_brightness_change)
        color_adjust_layout.addWidget(self.slider_brightness, 0, 1)
        self.lbl_brightness = QLabel("0")
        self.lbl_brightness.setFixedWidth(40)
        self.lbl_brightness.setAlignment(Qt.AlignmentFlag.AlignRight)
        color_adjust_layout.addWidget(self.lbl_brightness, 0, 2)

        # Contrast
        color_adjust_layout.addWidget(QLabel("Contrast:"), 1, 0)
        self.slider_contrast = QSlider(Qt.Orientation.Horizontal)
        self.slider_contrast.setRange(-100, 100)
        self.slider_contrast.setValue(0)
        self.slider_contrast.valueChanged.connect(self.on_contrast_change)
        color_adjust_layout.addWidget(self.slider_contrast, 1, 1)
        self.lbl_contrast = QLabel("0")
        self.lbl_contrast.setFixedWidth(40)
        self.lbl_contrast.setAlignment(Qt.AlignmentFlag.AlignRight)
        color_adjust_layout.addWidget(self.lbl_contrast, 1, 2)

        # Saturation
        color_adjust_layout.addWidget(QLabel("Saturation:"), 2, 0)
        self.slider_saturation = QSlider(Qt.Orientation.Horizontal)
        self.slider_saturation.setRange(-100, 100)
        self.slider_saturation.setValue(0)
        self.slider_saturation.valueChanged.connect(self.on_saturation_change)
        color_adjust_layout.addWidget(self.slider_saturation, 2, 1)
        self.lbl_saturation = QLabel("0")
        self.lbl_saturation.setFixedWidth(40)
        self.lbl_saturation.setAlignment(Qt.AlignmentFlag.AlignRight)
        color_adjust_layout.addWidget(self.lbl_saturation, 2, 2)

        # Separador visual
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #666;")
        color_adjust_layout.addWidget(separator, 3, 0, 1, 3)

        # Red
        color_adjust_layout.addWidget(QLabel("Red:"), 4, 0)
        self.slider_red = QSlider(Qt.Orientation.Horizontal)
        self.slider_red.setRange(-100, 100)
        self.slider_red.setValue(0)
        self.slider_red.valueChanged.connect(self.on_red_change)
        color_adjust_layout.addWidget(self.slider_red, 4, 1)
        self.lbl_red = QLabel("0")
        self.lbl_red.setFixedWidth(40)
        self.lbl_red.setAlignment(Qt.AlignmentFlag.AlignRight)
        color_adjust_layout.addWidget(self.lbl_red, 4, 2)

        # Green
        color_adjust_layout.addWidget(QLabel("Green:"), 5, 0)
        self.slider_green = QSlider(Qt.Orientation.Horizontal)
        self.slider_green.setRange(-100, 100)
        self.slider_green.setValue(0)
        self.slider_green.valueChanged.connect(self.on_green_change)
        color_adjust_layout.addWidget(self.slider_green, 5, 1)
        self.lbl_green = QLabel("0")
        self.lbl_green.setFixedWidth(40)
        self.lbl_green.setAlignment(Qt.AlignmentFlag.AlignRight)
        color_adjust_layout.addWidget(self.lbl_green, 5, 2)

        # Blue
        color_adjust_layout.addWidget(QLabel("Blue:"), 6, 0)
        self.slider_blue = QSlider(Qt.Orientation.Horizontal)
        self.slider_blue.setRange(-100, 100)
        self.slider_blue.setValue(0)
        self.slider_blue.valueChanged.connect(self.on_blue_change)
        color_adjust_layout.addWidget(self.slider_blue, 6, 1)
        self.lbl_blue = QLabel("0")
        self.lbl_blue.setFixedWidth(40)
        self.lbl_blue.setAlignment(Qt.AlignmentFlag.AlignRight)
        color_adjust_layout.addWidget(self.lbl_blue, 6, 2)

        # Botão Apply
        self.btn_apply_color = QPushButton("Apply")
        self.btn_apply_color.setStyleSheet(
            "background-color: #28a745; font-weight: bold; color: white;"
        )
        self.btn_apply_color.clicked.connect(self.apply_color_adjustments)
        self.btn_apply_color.setEnabled(False)
        color_adjust_layout.addWidget(self.btn_apply_color, 7, 0, 1, 3)

        # Botão Reset
        self.btn_reset_color = QPushButton("Reset")
        self.btn_reset_color.clicked.connect(self.reset_color_sliders)
        color_adjust_layout.addWidget(self.btn_reset_color, 8, 0, 1, 3)

        grp_color_adjust.setLayout(color_adjust_layout)
        tab_transparency_layout.addWidget(grp_color_adjust)

        tab_transparency_layout.addStretch()

        # GRUPO: Paint Brush (VERSÃO ATUALIZADA COM BRUSH TYPE)
        grp_paint = QGroupBox("Paint Brush")
        paint_layout = QGridLayout()

        # Brush Size
        paint_layout.addWidget(QLabel("Brush Size:"), 0, 0)
        self.spin_paint_size = QSpinBox()
        self.spin_paint_size.setRange(1, 100)
        self.spin_paint_size.setValue(5)
        self.spin_paint_size.valueChanged.connect(self.on_paint_size_change)
        paint_layout.addWidget(self.spin_paint_size, 0, 1)

        # Feathering (linha 1)
        paint_layout.addWidget(QLabel("Feathering:"), 1, 0)
        self.spin_paint_feathering = QSpinBox()
        self.spin_paint_feathering.setRange(0, 100)
        self.spin_paint_feathering.setValue(0)
        self.spin_paint_feathering.setSuffix("%")
        self.spin_paint_feathering.valueChanged.connect(self.on_paint_feathering_change)
        paint_layout.addWidget(self.spin_paint_feathering, 1, 1)

        # NOVO: Brush Type (linha 2)
        paint_layout.addWidget(QLabel("Brush Type:"), 2, 0)
        self.combo_brush_type = QComboBox()
        self.combo_brush_type.addItems(["Circle", "Square", "Hard Pixel", "Spray"])
        self.combo_brush_type.setCurrentText("Circle")
        self.combo_brush_type.currentTextChanged.connect(self.on_brush_type_change)
        paint_layout.addWidget(self.combo_brush_type, 2, 1)

        # Choose Color (linha 3)
        self.btn_choose_color = QPushButton("Choose Color")
        self.btn_choose_color.setStyleSheet("background-color: #555;")
        self.btn_choose_color.clicked.connect(self.choose_paint_color)
        self.btn_choose_color.setEnabled(False)
        paint_layout.addWidget(self.btn_choose_color, 3, 0, 1, 2)

        # Pick Color (linha 4)
        self.btn_pick_paint_color = QPushButton("Pick Color from Image")
        self.btn_pick_paint_color.setStyleSheet("background-color: #555;")
        self.btn_pick_paint_color.clicked.connect(self.enable_paint_color_picker)
        self.btn_pick_paint_color.setEnabled(False)
        paint_layout.addWidget(self.btn_pick_paint_color, 4, 0, 1, 2)

        # Color Preview (linha 5)
        self.lbl_paint_color_preview = QLabel()
        self.lbl_paint_color_preview.setFixedHeight(30)
        self.lbl_paint_color_preview.setStyleSheet(
            "background-color: #000000; border: 1px solid #222;"
        )
        paint_layout.addWidget(self.lbl_paint_color_preview, 5, 0, 1, 2)

        # Toggle Paint (linha 6)
        self.btn_toggle_paint = QPushButton("Enable Paint")
        self.btn_toggle_paint.setCheckable(True)
        self.btn_toggle_paint.setStyleSheet(
            "background-color: #9b59b6; font-weight: bold;"
        )
        self.btn_toggle_paint.clicked.connect(self.toggle_paint_mode)
        self.btn_toggle_paint.setEnabled(False)
        paint_layout.addWidget(self.btn_toggle_paint, 6, 0, 1, 2)

        grp_paint.setLayout(paint_layout)
        tab_transparency_layout.addWidget(grp_paint)

        tab_slice = QWidget()
        tab_slice_layout = QVBoxLayout(tab_slice)

        grp_cells = QGroupBox("Cells")
        grp_cells_layout = QGridLayout()
        self.chk_subdivisions = QCheckBox("Subdivisions")
        self.chk_subdivisions.toggled.connect(self.update_grid_visuals)
        self.chk_subdivisions.setVisible(False)       
        grp_cells_layout.addWidget(self.chk_subdivisions, 0, 0, 1, 2)   

        self.chk_empty = QCheckBox("Empty Sprites")
        self.chk_empty.setToolTip(
            "Se marcado, salva sprites mesmo se forem transparentes"
        )
        grp_cells_layout.addWidget(self.chk_empty, 1, 0, 1, 2)

        grp_cells_layout.addWidget(QLabel("Size:"), 2, 0)
        self.combo_cell_size = QComboBox()
        self.combo_cell_size.addItems(["32x32", "64x64", "128x128", "256x256", "512x512"])
        self.combo_cell_size.setCurrentIndex(0)
        self.combo_cell_size.currentTextChanged.connect(self.on_cell_size_change)
        grp_cells_layout.addWidget(self.combo_cell_size, 2, 1)

        grp_cells_layout.addWidget(QLabel("X:"), 3, 0)
        self.spin_x = QSpinBox()
        self.spin_x.setRange(0, 9999)
        self.spin_x.valueChanged.connect(self.on_spinbox_change)
        grp_cells_layout.addWidget(self.spin_x, 3, 1)

        grp_cells_layout.addWidget(QLabel("Y:"), 4, 0)
        self.spin_y = QSpinBox()
        self.spin_y.setRange(0, 9999)
        self.spin_y.valueChanged.connect(self.on_spinbox_change)
        grp_cells_layout.addWidget(self.spin_y, 4, 1)

        grp_cells_layout.addWidget(QLabel("Cols:"), 5, 0)
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 100)
        self.spin_cols.setValue(1)
        self.spin_cols.valueChanged.connect(self.update_grid_visuals)
        grp_cells_layout.addWidget(self.spin_cols, 5, 1)

        grp_cells_layout.addWidget(QLabel("Rows:"), 6, 0)
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 100)
        self.spin_rows.setValue(1)
        self.spin_rows.valueChanged.connect(self.update_grid_visuals)
        grp_cells_layout.addWidget(self.spin_rows, 6, 1)

        grp_cells.setLayout(grp_cells_layout)
        tab_slice_layout.addWidget(grp_cells)

        self.btn_cut = QPushButton("CUT IMAGE")
        self.btn_cut.setFixedHeight(40)
        self.btn_cut.setStyleSheet(
            "background-color: #007acc; font-weight: bold; color: white;"
        )
        self.btn_cut.clicked.connect(self.cut_image)
        tab_slice_layout.addWidget(self.btn_cut)

        grp_eraser = QGroupBox("Eraser Tool")
        eraser_layout = QGridLayout()

        eraser_layout.addWidget(QLabel("Brush Size:"), 0, 0)
        self.spin_eraser_size = QSpinBox()
        self.spin_eraser_size.setRange(1, 100)
        self.spin_eraser_size.setValue(10)
        self.spin_eraser_size.valueChanged.connect(self.on_eraser_size_change)
        eraser_layout.addWidget(self.spin_eraser_size, 0, 1)

        eraser_layout.addWidget(QLabel("Feathering:"), 1, 0)
        self.spin_eraser_feathering = QSpinBox()
        self.spin_eraser_feathering.setRange(0, 100)
        self.spin_eraser_feathering.setValue(0)
        self.spin_eraser_feathering.setSuffix("%")
        self.spin_eraser_feathering.setToolTip(
            "0% = bordas duras, 100% = máxima suavização"
        )
        self.spin_eraser_feathering.valueChanged.connect(
            self.on_eraser_feathering_change
        )
        eraser_layout.addWidget(self.spin_eraser_feathering, 1, 1)

        self.btn_toggle_eraser = QPushButton("Enable Eraser")
        self.btn_toggle_eraser.setCheckable(True)
        self.btn_toggle_eraser.setStyleSheet(
            "background-color: #ff6b6b; font-weight: bold;"
        )
        self.btn_toggle_eraser.clicked.connect(self.toggle_eraser_mode)
        self.btn_toggle_eraser.setEnabled(False)
        eraser_layout.addWidget(self.btn_toggle_eraser, 2, 0, 1, 2)  # Atualizar linha

        grp_eraser.setLayout(eraser_layout)
        tab_slice_layout.addWidget(grp_eraser)

        grp_selection = QGroupBox("Selection Tool")
        selection_layout = QGridLayout()

        self.btn_toggle_selection = QPushButton("Enable Selection")
        self.btn_toggle_selection.setCheckable(True)
        self.btn_toggle_selection.setStyleSheet(
            "background-color: #ffa500; font-weight: bold;"
        )
        self.btn_toggle_selection.clicked.connect(self.toggle_selection_mode)
        self.btn_toggle_selection.setEnabled(False)
        selection_layout.addWidget(self.btn_toggle_selection, 0, 0, 1, 2)

        self.btn_cut_selection = QPushButton("Cut Selection")
        self.btn_cut_selection.setStyleSheet(
            "background-color: #e74c3c; font-weight: bold;"
        )
        self.btn_cut_selection.clicked.connect(self.cut_selection)
        self.btn_cut_selection.setEnabled(False)
        selection_layout.addWidget(self.btn_cut_selection, 1, 0, 1, 2)

        self.btn_copy_selection = QPushButton("Copy Selection")
        self.btn_copy_selection.setStyleSheet(
            "background-color: #3498db; font-weight: bold;"
        )
        self.btn_copy_selection.clicked.connect(self.copy_selection)
        self.btn_copy_selection.setEnabled(False)
        self.btn_copy_selection.setVisible(False)
        selection_layout.addWidget(self.btn_copy_selection, 2, 0, 1, 2)

        self.btn_paste_selection = QPushButton("Paste")
        self.btn_paste_selection.setStyleSheet(
            "background-color: #2ecc71; font-weight: bold;"
        )
        self.btn_paste_selection.clicked.connect(self.paste_selection)
        self.btn_paste_selection.setEnabled(False)
        self.btn_paste_selection.setVisible(False)
        selection_layout.addWidget(self.btn_paste_selection, 3, 0, 1, 2)

        self.btn_clear_selection = QPushButton("Clear Selection")
        self.btn_clear_selection.clicked.connect(self.clear_selection)
        self.btn_clear_selection.setEnabled(False)
        selection_layout.addWidget(self.btn_clear_selection, 4, 0, 1, 2)

        grp_selection.setLayout(selection_layout)
        tab_slice_layout.addWidget(grp_selection)
                # GRUPO: Rotate Fine (NOVO)
        grp_rotate_fine = QGroupBox("Rotate Fine")
        rotate_fine_layout = QGridLayout()

        rotate_fine_layout.addWidget(QLabel("Angle:"), 0, 0)
        self.slider_rotate_fine = QSlider(Qt.Orientation.Horizontal)
        self.slider_rotate_fine.setRange(0, 360)
        self.slider_rotate_fine.setValue(0)
        self.slider_rotate_fine.valueChanged.connect(self.on_rotate_fine_change)
        rotate_fine_layout.addWidget(self.slider_rotate_fine, 0, 1)

        self.spin_rotate_fine = QSpinBox()
        self.spin_rotate_fine.setRange(0, 360)
        self.spin_rotate_fine.setValue(0)
        self.spin_rotate_fine.setSuffix("°")
        self.spin_rotate_fine.valueChanged.connect(self.on_rotate_fine_spin_change)
        rotate_fine_layout.addWidget(self.spin_rotate_fine, 0, 2)

        self.btn_apply_rotate_fine = QPushButton("Apply Rotate")
        self.btn_apply_rotate_fine.setStyleSheet(
            "background-color: #28a745; font-weight: bold; color: white;"
        )
        self.btn_apply_rotate_fine.clicked.connect(self.apply_rotate_fine)
        self.btn_apply_rotate_fine.setEnabled(False)
        rotate_fine_layout.addWidget(self.btn_apply_rotate_fine, 1, 0, 1, 3)

        self.btn_reset_rotate_fine = QPushButton("Reset")
        self.btn_reset_rotate_fine.clicked.connect(self.reset_rotate_fine)
        rotate_fine_layout.addWidget(self.btn_reset_rotate_fine, 2, 0, 1, 3)

        grp_rotate_fine.setLayout(rotate_fine_layout)
        tab_slice_layout.addWidget(grp_rotate_fine)
        

        tab_slice_layout.addStretch()

        # GRUPO: Fine Grid
        grp_fine_grid = QGroupBox("Fine Grid")
        fine_grid_layout = QGridLayout()

        self.chk_enable_fine_grid = QCheckBox("Enable Fine Grid")
        self.chk_enable_fine_grid.setToolTip("Mostra grid fino sobre toda a imagem")
        self.chk_enable_fine_grid.toggled.connect(self.toggle_fine_grid)
        self.chk_enable_fine_grid.setEnabled(False)
        fine_grid_layout.addWidget(self.chk_enable_fine_grid, 0, 0, 1, 2)

        fine_grid_layout.addWidget(QLabel("Spacing:"), 1, 0)
        self.spin_fine_grid_spacing = QSpinBox()
        self.spin_fine_grid_spacing.setRange(1, 32)
        self.spin_fine_grid_spacing.setValue(4)
        self.spin_fine_grid_spacing.setSuffix("px")
        self.spin_fine_grid_spacing.valueChanged.connect(
            self.on_fine_grid_spacing_change
        )
        fine_grid_layout.addWidget(self.spin_fine_grid_spacing, 1, 1)

        grp_fine_grid.setLayout(fine_grid_layout)
        tab_slice_layout.addWidget(grp_fine_grid)

        tab_upscale = QWidget()
        tab_upscale_layout = QVBoxLayout(tab_upscale)

        # GRUPO 1: Denoise (Waifu2x)
        grp_denoise = QGroupBox("Denoise (Waifu2x)")
        denoise_layout = QGridLayout()

        denoise_layout.addWidget(QLabel("Noise Level:"), 0, 0)
        self.combo_denoise_level = QComboBox()
        self.combo_denoise_level.addItems(["0", "1", "2", "3"])
        self.combo_denoise_level.setCurrentIndex(1)
        self.combo_denoise_level.setToolTip("0 = sem denoise, 3 = máximo")
        denoise_layout.addWidget(self.combo_denoise_level, 0, 1)

        self.btn_apply_denoise = QPushButton("Apply Denoise")
        self.btn_apply_denoise.setStyleSheet(
            "background-color: #17a2b8; font-weight: bold;"
        )
        self.btn_apply_denoise.clicked.connect(self.apply_denoise)
        self.btn_apply_denoise.setEnabled(False)
        if not WAIFU_AVAILABLE:
            self.btn_apply_denoise.setToolTip(f"upscale2.exe não encontrado em:\n{WAIFU_EXE}")
        denoise_layout.addWidget(self.btn_apply_denoise, 1, 0, 1, 2)

        grp_denoise.setLayout(denoise_layout)
        tab_upscale_layout.addWidget(grp_denoise)

        grp_upscale = QGroupBox("AI Upscale")
        upscale_layout = QGridLayout()

        upscale_layout.addWidget(QLabel("Method:"), 0, 0)
        self.combo_upscale_method = QComboBox()
        self.combo_upscale_method.addItems(["Waifu2x", "Real-ESRGAN"])
        self.combo_upscale_method.setCurrentIndex(0)
        self.combo_upscale_method.currentTextChanged.connect(self.on_upscale_method_changed)
        upscale_layout.addWidget(self.combo_upscale_method, 0, 1)

        upscale_layout.addWidget(QLabel("Scale Factor:"), 1, 0)
        self.combo_upscale_factor = QComboBox()
        self.combo_upscale_factor.addItems(["2x", "4x"])
        self.combo_upscale_factor.setCurrentIndex(0)
        upscale_layout.addWidget(self.combo_upscale_factor, 1, 1)

        self.lbl_upscale_noise = QLabel("Noise Level:")
        upscale_layout.addWidget(self.lbl_upscale_noise, 2, 0)
        self.combo_upscale_noise = QComboBox()
        self.combo_upscale_noise.addItems(["0", "1", "2", "3"])
        self.combo_upscale_noise.setCurrentIndex(1)
        self.combo_upscale_noise.setToolTip("Nível de denoise aplicado junto ao upscale")
        upscale_layout.addWidget(self.combo_upscale_noise, 2, 1)

        # Manter resolução original
        self.chk_keep_original_size = QCheckBox("Keep Original Resolution")
        self.chk_keep_original_size.setChecked(False)
        self.chk_keep_original_size.setToolTip(
            "Faz upscale para melhorar qualidade, depois redimensiona\n"
            "de volta para a resolução original (melhora detalhes)"
        )
        upscale_layout.addWidget(self.chk_keep_original_size, 3, 0, 1, 2)

        # Botão Apply
        self.btn_apply_upscale = QPushButton("Apply AI Upscale")
        self.btn_apply_upscale.setStyleSheet(
            "background-color: #28a745; font-weight: bold;"
        )
        self.btn_apply_upscale.clicked.connect(self.apply_ai_upscale)
        self.btn_apply_upscale.setEnabled(False)
        upscale_layout.addWidget(self.btn_apply_upscale, 4, 0, 1, 2)

        # Label de status
        self.lbl_upscale_status = QLabel("")
        self.lbl_upscale_status.setStyleSheet("color: #aaa; font-size: 10px;")
        self.lbl_upscale_status.setWordWrap(True)
        upscale_layout.addWidget(self.lbl_upscale_status, 5, 0, 1, 2)

        grp_upscale.setLayout(upscale_layout)
        tab_upscale_layout.addWidget(grp_upscale)

        tab_upscale_layout.addStretch()

        self.tab_widget.addTab(tab_resize, "Adjust")
        self.tab_widget.addTab(tab_transparency, "Color")
        self.tab_widget.addTab(tab_slice, "Tools")
        self.tab_widget.addTab(tab_upscale, "Upscale")

        lp_layout.addWidget(self.tab_widget)

        lp_layout.addStretch()
        content_layout.addWidget(left_panel)

        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QColor(50, 50, 50))
        
        self.eraser_overlay = EraserOverlay()
        self.scene.addItem(self.eraser_overlay)
        self.eraser_overlay.setVisible(False)        
  

        self.view = ZoomableGraphicsView(self.scene, self)
        self.view.setMouseTracking(True)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setStyleSheet("border: none;")

        self.view.mousePressEvent = self.view_mouse_press
        self.view.mouseMoveEvent = self.view_mouse_move
        self.view.mouseReleaseEvent = self.view_mouse_release

        content_layout.addWidget(self.view, 1)

        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)

        self.grid_item = GridOverlay()
        self.grid_item.positionChanged.connect(self.on_grid_moved_by_mouse)
        self.scene.addItem(self.grid_item)

        right_panel = QFrame()
        right_panel.setFixedWidth(300)
        right_panel.setStyleSheet(
            "background-color: #444; border-left: 1px solid #222;"
        )
        rp_layout = QVBoxLayout(right_panel)

        rp_layout.addWidget(QLabel("Sprites:"))
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(self.list_widget.size())
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list_widget.setStyleSheet(
            "QListWidget { background-color: #333; } QListWidget::item:selected { background-color: #007acc; }"
        )
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(32, 32))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.on_list_context_menu)
                
        
        rp_layout.addWidget(self.list_widget)

        self.btn_export = QPushButton("Export PNG (Cortado)")
        self.btn_export.setFixedHeight(30)
        self.btn_export.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold;"
        )
        self.btn_export.clicked.connect(self.export_sprites)
        self.btn_export.setEnabled(False)
        rp_layout.addWidget(self.btn_export)
        
        self.btn_import = QPushButton("Import SPR")
        self.btn_import.setFixedHeight(30)
        self.btn_import.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_import.clicked.connect(self.import_sprites)
        self.btn_import.setEnabled(False)
        self.btn_import.setVisible(False)  # não utilizado em StandAlone
        rp_layout.addWidget(self.btn_import)        
        
        

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self.clear_list)
        rp_layout.addWidget(btn_clear)

        content_layout.addWidget(right_panel)


        self.create_layers_panel()

    def on_list_context_menu(self, position):
        """Exibe menu de contexto ao clicar direito em sprite"""
        item = self.list_widget.itemAt(position)
        
        if not item:
            return
        
        index = self.list_widget.row(item)
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #dc3545;
            }
        """)
        
        delete_action = menu.addAction("🗑️ Delete")
        delete_action.triggered.connect(lambda: self.delete_sprite_from_list(index))
        
        menu.exec(self.list_widget.mapToGlobal(position))
            
        
    def delete_sprite_from_list(self, index):
        """Remove uma sprite específica da lista"""
        if index < 0 or index >= len(self.sliced_images):
            return
        
        self.sliced_images.pop(index)
        self.list_widget.takeItem(index)
        
        if len(self.sliced_images) == 0:
            self.btn_export.setEnabled(False)

        
        
    def toggle_cut_size_mode(self, checked):
        """Ativa/desativa o modo de recorte personalizado"""
        self.cut_size_mode = checked
        
        if checked:
            # Desativa outros modos
            if self.eraser_mode:
                self.btn_toggle_eraser.setChecked(False)
                self.toggle_eraser_mode(False)
            if self.paint_mode:
                self.btn_toggle_paint.setChecked(False)
                self.toggle_paint_mode(False)
            if self.selection_mode:
                self.btn_toggle_selection.setChecked(False)
                self.toggle_selection_mode(False)
            
            self.btn_cut_size.setText("Cancel Cut Size")
            self.btn_cut_size.setStyleSheet(
                "background-color: #dc3545; font-weight: bold; color: white;"
            )
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
            self.grid_item.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, False)
            
            # QMessageBox.information(
                # self,
                # "Cut Size Mode",
                # "Clique e arraste para criar um retângulo de recorte.\n"
                # "O projeto será cortado para o tamanho selecionado."
            # )
        else:
            self.btn_cut_size.setText("Cut Size")
            self.btn_cut_size.setStyleSheet(
                "background-color: #ff6b35; font-weight: bold; color: white;"
            )
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self.grid_item.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)
            self.clear_cut_rect()

    def clear_cut_rect(self):
        """Remove o retângulo de recorte"""
        if self.cut_rect_item:
            self.scene.removeItem(self.cut_rect_item)
            self.cut_rect_item = None
        self.btn_apply_cut.setEnabled(False)

    def create_cut_rect(self, rect):
        """Cria o retângulo visual de recorte"""
        if self.cut_rect_item:
            self.scene.removeItem(self.cut_rect_item)
        
        self.cut_rect_item = QGraphicsRectItem(rect)
        self.cut_rect_item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.cut_rect_item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.cut_rect_item.setZValue(20)
        
        # Estilo visual
        pen = QPen(QColor(255, 107, 53), 3, Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        self.cut_rect_item.setPen(pen)
        self.cut_rect_item.setBrush(QBrush(QColor(255, 107, 53, 50)))
        
        self.scene.addItem(self.cut_rect_item)
        self.btn_apply_cut.setEnabled(True)

    def apply_cut_size(self):
        """Aplica o corte baseado no retângulo desenhado"""
        if not self.cut_rect_item or not self.current_image_pil:
            return
        
        # Obtém as coordenadas do retângulo
        rect = self.cut_rect_item.rect()
        pos = self.cut_rect_item.pos()
        
        x = int(pos.x() + rect.x())
        y = int(pos.y() + rect.y())
        width = int(rect.width())
        height = int(rect.height())
        
        # Validação
        if width <= 0 or height <= 0:
            QMessageBox.warning(self, "Invalid Size", "O retângulo deve ter tamanho válido!")
            return
        
        # Confirma com o usuário
        reply = QMessageBox.question(
            self,
            "Confirm Cut",
            f"Cortar projeto para:\n"
            f"Position: ({x}, {y})\n"
            f"Size: {width}x{height}px\n\n"
            f"Esta ação irá redimensionar o projeto main.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.save_state()
        
        try:
            # Cria uma nova imagem com o tamanho do recorte
            new_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            
            # Calcula a área de colagem
            paste_x = max(0, -x)
            paste_y = max(0, -y)
            
            crop_x = max(0, x)
            crop_y = max(0, y)
            crop_w = min(self.current_image_pil.width - crop_x, width)
            crop_h = min(self.current_image_pil.height - crop_y, height)
            
            if crop_w > 0 and crop_h > 0:
                cropped = self.current_image_pil.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
                new_image.paste(cropped, (paste_x, paste_y))
            
            # Atualiza a imagem
            self.current_image_pil = new_image
            self.original_image_pil = new_image.copy()
            
            # Atualiza o layer main
            main_layer = self.get_main_layer()
            if main_layer:
                main_layer.image = new_image.copy()
                # if main_layer.id in self.layer_widgets:
                    # self.layer_widgets[main_layer.id].update_thumbnail()
            
            # Atualiza UI
            self.update_canvas_image()
            self.spin_resize_width.setValue(width)
            self.spin_resize_height.setValue(height)
            
            # Limpa o retângulo e desativa o modo
            self.clear_cut_rect()
            self.btn_cut_size.setChecked(False)
            self.toggle_cut_size_mode(False)
            
            QMessageBox.information(
                self,
                "Cut Complete",
                f"Projeto cortado para {width}x{height}px com sucesso!"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Erro ao cortar: {str(e)}")
        
        
        

    def on_brush_type_change(self, text):
        self.brush_type = text

    def toggle_fine_grid(self, checked):
        self.fine_grid_enabled = checked
        if self.fine_grid_item:
            self.fine_grid_item.set_visible(checked)

    def on_fine_grid_spacing_change(self, value):
        self.fine_grid_spacing = value
        if self.fine_grid_item:
            self.fine_grid_item.set_spacing(value)

    def create_fine_grid(self):
        if self.fine_grid_item:
            self.scene.removeItem(self.fine_grid_item)

        if self.current_image_pil:
            w = self.current_image_pil.width
            h = self.current_image_pil.height
            rect = QRectF(0, 0, w, h)
            self.fine_grid_item = FineGridOverlay(rect, self.fine_grid_spacing)
            self.scene.addItem(self.fine_grid_item)
            self.fine_grid_item.set_visible(self.fine_grid_enabled)



    def create_layers_panel(self):
        """Cria o painel de layers na parte inferior"""
        layers_panel = QFrame()
        layers_panel.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border-top: 2px solid #222;
            }
        """)
        layers_panel.setMinimumHeight(120)
        layers_panel.setMaximumHeight(200)

        layout = QVBoxLayout(layers_panel)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)

        # Header do painel
        header_layout = QHBoxLayout()

        lbl_title = QLabel("📑 LAYERS")
        lbl_title.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        # Botão adicionar layer
        self.btn_add_layer = QPushButton("+ Add Layer")
        self.btn_add_layer.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.btn_add_layer.clicked.connect(self.add_new_layer)
        self.btn_add_layer.setEnabled(False)
        header_layout.addWidget(self.btn_add_layer)

        # Botão remover layer
        self.btn_remove_layer = QPushButton("- Remove")
        self.btn_remove_layer.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.btn_remove_layer.clicked.connect(self.remove_selected_layer)
        self.btn_remove_layer.setEnabled(False)
        header_layout.addWidget(self.btn_remove_layer)

        # Botão mover para cima
        self.btn_layer_up = QPushButton("↑")
        self.btn_layer_up.setFixedWidth(30)
        self.btn_layer_up.setStyleSheet(
            "background-color: #555; color: white; font-weight: bold;"
        )
        self.btn_layer_up.clicked.connect(self.move_layer_up)
        self.btn_layer_up.setEnabled(False)
        header_layout.addWidget(self.btn_layer_up)

        # Botão mover para baixo
        self.btn_layer_down = QPushButton("↓")
        self.btn_layer_down.setFixedWidth(30)
        self.btn_layer_down.setStyleSheet(
            "background-color: #555; color: white; font-weight: bold;"
        )
        self.btn_layer_down.clicked.connect(self.move_layer_down)
        self.btn_layer_down.setEnabled(False)
        header_layout.addWidget(self.btn_layer_down)

        # Separador
        header_layout.addSpacing(10)

        # Label de opacidade
        lbl_opacity = QLabel("Opacity:")
        lbl_opacity.setStyleSheet("color: #ccc; font-size: 11px;")
        header_layout.addWidget(lbl_opacity)

        # Slider de opacidade
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.setFixedWidth(80)
        self.slider_opacity.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #555;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #007acc;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)
        self.slider_opacity.valueChanged.connect(self.on_opacity_slider_changed)
        self.slider_opacity.setEnabled(False)
        header_layout.addWidget(self.slider_opacity)

        # Label do valor de opacidade
        self.lbl_opacity_value = QLabel("100%")
        self.lbl_opacity_value.setFixedWidth(35)
        self.lbl_opacity_value.setStyleSheet("color: white; font-size: 11px;")
        header_layout.addWidget(self.lbl_opacity_value)

        header_layout.addSpacing(10)

        # Botão merge all
        self.btn_merge_layers = QPushButton("Merge All")
        self.btn_merge_layers.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.btn_merge_layers.clicked.connect(self.merge_all_layers)
        self.btn_merge_layers.setEnabled(False)
        header_layout.addWidget(self.btn_merge_layers)

        layout.addLayout(header_layout)

        # Área de scroll para a lista de layers
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 3px;
            }
        """)

        # Container para os widgets de layer
        self.layers_container = QWidget()
        self.layers_layout = QHBoxLayout(self.layers_container)
        self.layers_layout.setContentsMargins(5, 5, 5, 5)
        self.layers_layout.setSpacing(5)
        self.layers_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(self.layers_container)
        layout.addWidget(scroll_area)

        # Label de instrução
        self.lbl_layer_info = QLabel("Abra uma imagem para criar o Layer Main")
        self.lbl_layer_info.setStyleSheet("color: #888; font-size: 10px;")
        self.lbl_layer_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_layer_info)

        self.main_splitter.addWidget(layers_panel)

        # Define o tamanho inicial do splitter
        self.main_splitter.setSizes([500, 150])

    def add_main_layer(self):
        """Cria o layer principal (Main) com a imagem atual"""
        if not self.current_image_pil:
            return

        # Remove layers existentes
        self.clear_all_layers()

        # Cria o layer main
        main_layer = Layer("Main", self.current_image_pil.copy(), 0, 0)
        main_layer.locked = True  # Main layer não pode ser movido

        self.layers.append(main_layer)
        self.active_layer_id = main_layer.id

        # Cria o widget visual
        self.create_layer_widget(main_layer, is_main=True)

        # Atualiza a UI
        self.update_layers_ui()
        self.lbl_layer_info.setText(
            "Layer Main ativo. Adicione mais layers com o botão + Add Layer"
        )

    def add_new_layer(self):
        """Adiciona um novo layer a partir de uma imagem"""
        if not self.current_image_pil:
            QMessageBox.warning(self, "Aviso", "Abra uma imagem principal primeiro!")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar imagem para novo Layer",
            "",
            "Images (*.png *.bmp *.jpg *.jpeg *.gif)",
        )

        if not file_path:
            return

        try:
            new_image = Image.open(file_path).convert("RGBA")

            # Cria o novo layer
            layer_num = len(self.layers)
            new_layer = Layer(f"Layer {layer_num}", new_image, 0, 0)

            if len(self.layers) > 1:
                reply = QMessageBox.question(
                    self,
                    "Posição do Layer",
                    "Deseja adicionar o novo layer por baixo dos outros layers existentes (acima do Main)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.layers.insert(1, new_layer)
                else:
                    self.layers.append(new_layer)
            else:
                self.layers.append(new_layer)

            # Cria o widget visual
            self.create_layer_widget(new_layer, is_main=False)
            
            self.rebuild_layer_widgets()

            # Cria o item gráfico arrastável
            self.create_layer_graphics_item(new_layer)
            
            self.update_layer_z_order()

            # Seleciona o novo layer
            self.select_layer(new_layer.id)

            # Atualiza a UI
            self.update_layers_ui()
            self.compose_and_display_layers()

            # QMessageBox.information(
                # self,
                # "Layer Adicionado",
                # f"Layer '{new_layer.name}' adicionado!\n"
                # f"Arraste-o no canvas para posicioná-lo.",
            # )

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar imagem: {str(e)}")

    def create_layer_widget(self, layer, is_main=False):
        """Cria um widget visual para o layer"""
        widget = LayerWidget(layer, is_main=is_main)
        widget.selected.connect(self.select_layer)
        widget.visibilityChanged.connect(self.on_layer_visibility_changed)
        widget.opacityChanged.connect(self.on_layer_opacity_changed)

        self.layer_widgets[layer.id] = widget
        self.layers_layout.addWidget(widget)

    def create_layer_graphics_item(self, layer):
        """Cria um item gráfico arrastável para o layer"""
        if layer.image:
            item = DraggableLayerItem(layer, self)

            # Converte PIL para QPixmap
            qim = self.pil_to_qimage(layer.image)
            pix = QPixmap.fromImage(qim)
            item.setPixmap(pix)
            item.setPos(layer.x, layer.y)
            item.setZValue(len(self.layers) + 5)  # Acima do main layer

            self.layer_graphics_items[layer.id] = item
            self.scene.addItem(item)

    def select_layer(self, layer_id):
        """Seleciona um layer pelo ID"""
        self.active_layer_id = layer_id

        # Atualiza a seleção visual dos widgets
        for lid, widget in self.layer_widgets.items():
            widget.set_selected(lid == layer_id)

        # Atualiza a seleção dos items gráficos
        for lid, item in self.layer_graphics_items.items():
            item.setSelected(lid == layer_id)

        # Atualiza os botões
        self.update_layer_buttons()

        # Atualiza o slider de opacidade
        active_layer = self.get_active_layer()
        if active_layer:
            if active_layer.name == "Main":
                self.slider_opacity.setEnabled(False)
                self.slider_opacity.setValue(100)
                self.lbl_layer_info.setText(
                    "Layer Main selecionado - Edições afetam a imagem principal"
                )
            else:
                self.slider_opacity.setEnabled(True)
                opacity_percent = int(active_layer.opacity * 100 / 255)
                self.slider_opacity.blockSignals(True)
                self.slider_opacity.setValue(opacity_percent)
                self.slider_opacity.blockSignals(False)
                self.lbl_opacity_value.setText(f"{opacity_percent}%")
                self.lbl_layer_info.setText(
                    f"Layer '{active_layer.name}' selecionado - Arraste para mover"
                )

    def get_active_layer(self):
        """Retorna o layer ativo"""
        for layer in self.layers:
            if layer.id == self.active_layer_id:
                return layer
        return None

    def get_main_layer(self):
        """Retorna o layer principal (Main)"""
        for layer in self.layers:
            if layer.name == "Main":
                return layer
        return None

    def on_layer_visibility_changed(self, layer_id, visible):
        """Callback quando a visibilidade de um layer muda"""
        # Atualiza o item gráfico
        if layer_id in self.layer_graphics_items:
            self.layer_graphics_items[layer_id].setVisible(visible)

        self.compose_and_display_layers()

    def on_layer_opacity_changed(self, layer_id, opacity_percent):
        """Callback quando a opacidade de um layer muda"""
        # Encontra o layer
        for layer in self.layers:
            if layer.id == layer_id:
                layer.opacity = int(opacity_percent * 255 / 100)
                break

        # Atualiza o item gráfico
        if layer_id in self.layer_graphics_items:
            self.layer_graphics_items[layer_id].setOpacity(opacity_percent / 100.0)

        self.compose_and_display_layers()

    def on_opacity_slider_changed(self, value):
        """Callback quando o slider de opacidade muda"""
        self.lbl_opacity_value.setText(f"{value}%")

        # Aplica ao layer ativo
        active_layer = self.get_active_layer()
        if active_layer and active_layer.name != "Main":
            active_layer.opacity = int(value * 255 / 100)

            # Atualiza o item gráfico
            if active_layer.id in self.layer_graphics_items:
                self.layer_graphics_items[active_layer.id].setOpacity(value / 100.0)

            self.compose_and_display_layers()

    def remove_selected_layer(self):
        """Remove o layer selecionado"""
        active_layer = self.get_active_layer()

        if not active_layer:
            return

        if active_layer.name == "Main":
            QMessageBox.warning(self, "Aviso", "Não é possível remover o Layer Main!")
            return

        reply = QMessageBox.question(
            self,
            "Confirmar Remoção",
            f"Deseja remover o layer '{active_layer.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Remove o widget
            if active_layer.id in self.layer_widgets:
                widget = self.layer_widgets.pop(active_layer.id)
                self.layers_layout.removeWidget(widget)
                widget.deleteLater()

            # Remove o item gráfico
            if active_layer.id in self.layer_graphics_items:
                item = self.layer_graphics_items.pop(active_layer.id)
                self.scene.removeItem(item)

            # Remove da lista
            self.layers = [l for l in self.layers if l.id != active_layer.id]

            # Seleciona o layer main
            main_layer = self.get_main_layer()
            if main_layer:
                self.select_layer(main_layer.id)

            self.update_layers_ui()
            self.compose_and_display_layers()

    def move_layer_up(self):
        """Move o layer selecionado para cima (mais à frente)"""
        active_layer = self.get_active_layer()
        if not active_layer or active_layer.name == "Main":
            return

        idx = None
        for i, layer in enumerate(self.layers):
            if layer.id == active_layer.id:
                idx = i
                break

        if idx is not None and idx < len(self.layers) - 1:
            self.layers[idx], self.layers[idx + 1] = (
                self.layers[idx + 1],
                self.layers[idx],
            )
            self.rebuild_layer_widgets()
            self.update_layer_z_order()
            self.compose_and_display_layers()

    def move_layer_down(self):
        """Move o layer selecionado para baixo (mais atrás)"""
        active_layer = self.get_active_layer()
        if not active_layer or active_layer.name == "Main":
            return

        idx = None
        for i, layer in enumerate(self.layers):
            if layer.id == active_layer.id:
                idx = i
                break

        if idx is not None and idx > 1:  # Não pode ir abaixo do Main (índice 0)
            self.layers[idx], self.layers[idx - 1] = (
                self.layers[idx - 1],
                self.layers[idx],
            )
            self.rebuild_layer_widgets()
            self.update_layer_z_order()
            self.compose_and_display_layers()

    def update_layer_z_order(self):
        """Atualiza a ordem Z dos items gráficos dos layers"""
        for i, layer in enumerate(self.layers):
            if layer.id in self.layer_graphics_items:
                self.layer_graphics_items[layer.id].setZValue(i + 5)

    def rebuild_layer_widgets(self):
        """Reconstrói os widgets de layer na ordem correta"""
        # Remove todos os widgets do layout
        for widget in self.layer_widgets.values():
            self.layers_layout.removeWidget(widget)

        # Adiciona de volta na ordem correta
        for layer in self.layers:
            if layer.id in self.layer_widgets:
                self.layers_layout.addWidget(self.layer_widgets[layer.id])

    def merge_all_layers(self):
        """Mescla todos os layers visíveis na imagem principal"""
        if len(self.layers) <= 1:
            QMessageBox.information(self, "Merge", "Não há layers para mesclar!")
            return

        reply = QMessageBox.question(
            self,
            "Confirmar Merge",
            "Isso irá mesclar todos os layers na imagem principal.\nDeseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.save_state()

        # Obtém o layer main
        main_layer = self.get_main_layer()
        if not main_layer or not main_layer.image:
            return

        # Cria uma nova imagem com o tamanho necessário para conter todos os layers
        result = main_layer.image.copy()

        # Compõe cada layer visível sobre o resultado
        for layer in self.layers[1:]:  # Pula o main
            if layer.visible and layer.image:
                # Cria uma imagem do tamanho do resultado para posicionar o layer
                layer_canvas = Image.new("RGBA", result.size, (0, 0, 0, 0))

                # Cola o layer na posição correta
                paste_x = max(0, layer.x)
                paste_y = max(0, layer.y)

                # Ajusta se o layer tiver coordenadas negativas
                crop_x = max(0, -layer.x)
                crop_y = max(0, -layer.y)

                if crop_x > 0 or crop_y > 0:
                    cropped = layer.image.crop(
                        (crop_x, crop_y, layer.image.width, layer.image.height)
                    )
                    layer_canvas.paste(cropped, (paste_x, paste_y), cropped)
                else:
                    layer_canvas.paste(layer.image, (paste_x, paste_y), layer.image)

                # Compõe sobre o resultado
                result = Image.alpha_composite(result, layer_canvas)

        # Atualiza a imagem principal
        self.current_image_pil = result
        main_layer.image = result.copy()

        # Remove todos os layers exceto o main
        layers_to_remove = [l for l in self.layers if l.name != "Main"]
        for layer in layers_to_remove:
            if layer.id in self.layer_widgets:
                widget = self.layer_widgets.pop(layer.id)
                self.layers_layout.removeWidget(widget)
                widget.deleteLater()

            if layer.id in self.layer_graphics_items:
                item = self.layer_graphics_items.pop(layer.id)
                self.scene.removeItem(item)

        self.layers = [l for l in self.layers if l.name == "Main"]

        # Atualiza a UI
        self.update_canvas_image()
        self.update_layers_ui()

        # Atualiza o thumbnail do layer main
        if main_layer.id in self.layer_widgets:
            self.layer_widgets[main_layer.id].layer.image = result.copy()
            # self.layer_widgets[main_layer.id].update_thumbnail()

        QMessageBox.information(
            self, "Merge Complete", "Todos os layers foram mesclados com sucesso!"
        )

    def clear_all_layers(self):
        """Remove todos os layers"""
        # Remove widgets
        for widget in self.layer_widgets.values():
            self.layers_layout.removeWidget(widget)
            widget.deleteLater()

        # Remove items gráficos
        for item in self.layer_graphics_items.values():
            self.scene.removeItem(item)

        self.layers.clear()
        self.layer_widgets.clear()
        self.layer_graphics_items.clear()
        self.active_layer_id = None

    def update_layers_ui(self):
        """Atualiza a UI dos layers"""
        has_layers = len(self.layers) > 0
        has_secondary_layers = len(self.layers) > 1

        self.btn_add_layer.setEnabled(has_layers)
        self.btn_remove_layer.setEnabled(has_secondary_layers)
        self.btn_layer_up.setEnabled(has_secondary_layers)
        self.btn_layer_down.setEnabled(has_secondary_layers)
        self.btn_merge_layers.setEnabled(has_secondary_layers)

    def update_layer_buttons(self):
        """Atualiza o estado dos botões baseado no layer selecionado"""
        active_layer = self.get_active_layer()

        if active_layer:
            is_main = active_layer.name == "Main"
            self.btn_remove_layer.setEnabled(not is_main and len(self.layers) > 1)
            self.btn_layer_up.setEnabled(not is_main)
            self.btn_layer_down.setEnabled(not is_main)

    def compose_and_display_layers(self):
        """Compõe todos os layers visíveis e exibe no canvas"""
        if not self.layers:
            return

        main_layer = self.get_main_layer()
        if not main_layer or not main_layer.image:
            return

        # Atualiza apenas os items gráficos dos layers secundários
        # O main layer usa o pixmap_item principal
        for layer in self.layers:
            if layer.name != "Main" and layer.id in self.layer_graphics_items:
                item = self.layer_graphics_items[layer.id]
                item.setPos(layer.x, layer.y)
                item.setVisible(layer.visible)
    def on_brightness_change(self, value):
        self.lbl_brightness.setText(str(value))

    def on_contrast_change(self, value):
        self.lbl_contrast.setText(str(value))

    def on_saturation_change(self, value):
        self.lbl_saturation.setText(str(value))

    def on_red_change(self, value):
        self.lbl_red.setText(str(value))

    def on_green_change(self, value):
        self.lbl_green.setText(str(value))

    def on_blue_change(self, value):
        self.lbl_blue.setText(str(value))

    def reset_color_sliders(self):
        """Reseta todos os sliders de cor para 0"""
        self.slider_brightness.setValue(0)
        self.slider_contrast.setValue(0)
        self.slider_saturation.setValue(0)
        self.slider_red.setValue(0)
        self.slider_green.setValue(0)
        self.slider_blue.setValue(0)

    def apply_color_adjustments(self):
        if not self.current_image_pil:
            return

        self.save_state()

        try:
            import numpy as np
            from PIL import ImageEnhance

            img = self.current_image_pil.copy()

            if img.mode != "RGBA":
                img = img.convert("RGBA")

            brightness_val = self.slider_brightness.value()
            if brightness_val != 0:
                factor = 1.0 + (brightness_val / 100.0)
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(factor)

            contrast_val = self.slider_contrast.value()
            if contrast_val != 0:
                factor = 1.0 + (contrast_val / 100.0)
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(factor)

            saturation_val = self.slider_saturation.value()
            if saturation_val != 0:
                factor = 1.0 + (saturation_val / 100.0)
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(factor)

            red_val = self.slider_red.value()
            green_val = self.slider_green.value()
            blue_val = self.slider_blue.value()

            if red_val != 0 or green_val != 0 or blue_val != 0:
                img_array = np.array(img)

                r, g, b, a = (
                    img_array[:, :, 0],
                    img_array[:, :, 1],
                    img_array[:, :, 2],
                    img_array[:, :, 3],
                )

                r = np.clip(r.astype(np.int16) + red_val, 0, 255).astype(np.uint8)
                g = np.clip(g.astype(np.int16) + green_val, 0, 255).astype(np.uint8)
                b = np.clip(b.astype(np.int16) + blue_val, 0, 255).astype(np.uint8)

                img_array[:, :, 0] = r
                img_array[:, :, 1] = g
                img_array[:, :, 2] = b

                img = Image.fromarray(img_array, "RGBA")

            self.current_image_pil = img
            self.update_canvas_image()

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            QMessageBox.critical(
                self, "Error", f"Erro ao aplicar ajustes: {str(e)}\n\n{error_details}"
            )

    def on_eraser_feathering_change(self, value):
        self.eraser_feathering = value

    def toggle_paint_mode(self, checked):
        self.paint_mode = checked

        if checked:
            if self.eraser_mode:
                self.btn_toggle_eraser.setChecked(False)
                self.toggle_eraser_mode(False)
            if self.selection_mode:
                self.btn_toggle_selection.setChecked(False)
                self.toggle_selection_mode(False)

            self.btn_toggle_paint.setText("Disable Paint")
            self.btn_toggle_paint.setStyleSheet(
                "background-color: #8e44ad; font-weight: bold;"
            )
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
            self.grid_item.setFlag(
                QGraphicsObject.GraphicsItemFlag.ItemIsMovable, False
            )
        else:
            self.btn_toggle_paint.setText("Enable Paint")
            self.btn_toggle_paint.setStyleSheet(
                "background-color: #9b59b6; font-weight: bold;"
            )
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self.grid_item.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)
            self.last_paint_point = None

    def on_paint_size_change(self, value):
        self.paint_size = value

    def on_paint_feathering_change(self, value):
        self.paint_feathering = value

    def choose_paint_color(self):
        color = QColorDialog.getColor(self.paint_color, self, "Escolher Cor do Pincel")

        if color.isValid():
            self.paint_color = color
            self.lbl_paint_color_preview.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid #222;"
            )

    def enable_paint_color_picker(self):
        self.paint_color_picker_mode = True
        self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.view.mousePressEvent = self.pick_paint_color_from_image

    def pick_paint_color_from_image(self, event):
        if not self.paint_color_picker_mode or not self.current_image_pil:
            return

        scene_pos = self.view.mapToScene(event.pos())
        x = int(scene_pos.x())
        y = int(scene_pos.y())

        w, h = self.current_image_pil.size
        if 0 <= x < w and 0 <= y < h:
            pixel = self.current_image_pil.getpixel((x, y))
            r, g, b, a = pixel

            self.paint_color = QColor(r, g, b, a)

            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            self.lbl_paint_color_preview.setStyleSheet(
                f"background-color: {hex_color}; border: 1px solid #222;"
            )

            # QMessageBox.information(
                # self,
                # "Color Selected",
                # f"Cor do pincel: {hex_color}\nRGBA: ({r}, {g}, {b}, {a})",
            # )

        self.paint_color_picker_mode = False
        self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.view.mousePressEvent = self.view_mouse_press

    def paint_at_point(self, point):
        if not self.current_image_pil:
            return

        x, y = point.x(), point.y()
        w, h = self.current_image_pil.size

        if x < 0 or y < 0 or x >= w or y >= h:
            return

        size = max(1, self.paint_size)

        r, g, b, a = (
            self.paint_color.red(),
            self.paint_color.green(),
            self.paint_color.blue(),
            self.paint_color.alpha(),
        )

        brush_type = getattr(self, "brush_type", "Circle")

        if brush_type == "Circle":
            self._paint_circle(x, y, size, (r, g, b, a))

        elif brush_type == "Square":
            self._paint_square(x, y, size, (r, g, b, a))

        elif brush_type == "Hard Pixel":
            self._paint_hard_pixel(x, y, size, (r, g, b, a))

        elif brush_type == "Spray":
            self._paint_spray(x, y, size, (r, g, b, a))

        elif brush_type == "Texture" and self.texture_brush_image is not None:
            self._paint_texture(x, y, size)

        else:
            # fallback para o círculo atual
            self._paint_circle(x, y, size, (r, g, b, a))

        self.update_canvas_image()

    def _paint_circle(self, x, y, size, color_rgba):
        from PIL import ImageDraw

        r, g, b, a = color_rgba
        left = x - size // 2
        top = y - size // 2
        right = left + size - 1
        bottom = top + size - 1

        if self.paint_feathering == 0:
            draw = ImageDraw.Draw(self.current_image_pil, "RGBA")
            if size == 1:
                draw.point((x, y), fill=(r, g, b, a))
            else:
                draw.ellipse([left, top, right, bottom], fill=(r, g, b, a))
        else:
            blur_radius = int((self.paint_feathering / 100.0) * (size / 2))
            margin = blur_radius + 10
            
            temp_w = size + margin * 2
            temp_h = size + margin * 2

            color_layer = Image.new("RGB", (temp_w, temp_h), (r, g, b))
            mask = Image.new("L", (temp_w, temp_h), 0)
            mask_draw = ImageDraw.Draw(mask)

            if size == 1:
                mask_draw.point((margin, margin), fill=a)
            else:
                mask_draw.ellipse([margin, margin, margin + size - 1, margin + size - 1], fill=a)

            if blur_radius > 0:
                mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            color_layer = color_layer.convert("RGBA")
            color_layer.putalpha(mask)

            paste_x = left - margin
            paste_y = top - margin

            self.current_image_pil.alpha_composite(color_layer, (paste_x, paste_y))

    def _paint_square(self, x, y, size, color_rgba):
        from PIL import ImageDraw

        r, g, b, a = color_rgba
        draw = ImageDraw.Draw(self.current_image_pil, "RGBA")

        left = x - size // 2
        top = y - size // 2
        right = left + size - 1
        bottom = top + size - 1

        if self.paint_feathering == 0:
            draw.rectangle([left, top, right, bottom], fill=(r, g, b, a))
        else:
            blur_radius = int((self.paint_feathering / 100.0) * (size / 2))
            margin = blur_radius + 10
            temp_w = size + margin * 2
            temp_h = size + margin * 2

            color_layer = Image.new("RGB", (temp_w, temp_h), (r, g, b))
            mask = Image.new("L", (temp_w, temp_h), 0)
            mask_draw = ImageDraw.Draw(mask)

            mask_draw.rectangle([margin, margin, margin + size - 1, margin + size - 1], fill=a)

            if blur_radius > 0:
                mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            color_layer = color_layer.convert("RGBA")
            color_layer.putalpha(mask)

            paste_x = left - margin
            paste_y = top - margin

            self.current_image_pil.alpha_composite(color_layer, (paste_x, paste_y))

    def _paint_hard_pixel(self, x, y, size, color_rgba):
        # "Pixel" pode ser 1x1 ou NxN, sem feather, alinhado à grade de pixels
        from PIL import ImageDraw

        r, g, b, a = color_rgba

        left = x - size // 2
        top = y - size // 2
        right = left + size - 1
        bottom = top + size - 1

        draw = ImageDraw.Draw(self.current_image_pil, "RGBA")
        draw.rectangle([left, top, right, bottom], fill=(r, g, b, a))

    def _paint_spray(self, x, y, size, color_rgba):
        import random

        radius = size / 2.0
        if radius < 0.5: radius = 0.5

        r, g, b, a = color_rgba
        pixels = self.current_image_pil.load()
        w, h = self.current_image_pil.size

        density = getattr(self, "spray_density", 0.3)

        # Número de amostras proporcional à área e à densidade
        samples = int(max(1, (radius * radius * 3.14) * density))

        for _ in range(samples):
            # ponto aleatório dentro do círculo
            dx = random.uniform(-radius, radius)
            dy = random.uniform(-radius, radius)
            if dx * dx + dy * dy > radius * radius:
                continue

            px = int(x + dx)
            py = int(y + dy)

            if 0 <= px < w and 0 <= py < h:
                pixels[px, py] = (r, g, b, a)

    def _paint_texture(self, x, y, size):
        if not self.texture_brush_image:
            return

        # textura centralizada no ponto
        tex = self.texture_brush_image
        tw, th = tex.size

        paste_x = int(x - tw // 2)
        paste_y = int(y - th // 2)

        self.current_image_pil.alpha_composite(tex, (paste_x, paste_y))

    def paint_line(self, start, end):
        if not self.current_image_pil:
            return

        x1, y1 = start.x(), start.y()
        x2, y2 = end.x(), end.y()

        distance = max(abs(x2 - x1), abs(y2 - y1))

        if distance == 0:
            self.paint_at_point(start)
            return

        for i in range(distance + 1):
            t = i / distance
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)
            self.paint_at_point(QPoint(x, y))

    def save_state(self):
        if self.current_image_pil:
            state = self.current_image_pil.copy()
            self.undo_stack.append(state)

            if len(self.undo_stack) > self.max_undo_steps:
                self.undo_stack.pop(0)

            self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            QMessageBox.information(self, "Undo", "Nada para desfazer!")
            return

        if self.current_image_pil:
            self.redo_stack.append(self.current_image_pil.copy())

        self.current_image_pil = self.undo_stack.pop()
        self.update_canvas_image()

    def redo(self):
        if not self.redo_stack:
            QMessageBox.information(self, "Redo", "Nada para refazer!")
            return

        if self.current_image_pil:
            self.undo_stack.append(self.current_image_pil.copy())

        self.current_image_pil = self.redo_stack.pop()
        self.update_canvas_image()

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self.undo()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Y:
                self.redo()
                event.accept()
                return

        super().keyPressEvent(event)

    def update_zoom_label(self, zoom_percentage):
        self.lbl_zoom_val.setText(f"{zoom_percentage}%")

        self.slider_zoom.blockSignals(True)
        self.slider_zoom.setValue(zoom_percentage)
        self.slider_zoom.blockSignals(False)

    def toggle_selection_mode(self, checked):
        self.selection_mode = checked

        if checked:
            if self.eraser_mode:
                self.btn_toggle_eraser.setChecked(False)
                self.toggle_eraser_mode(False)
            if self.paint_mode:
                self.btn_toggle_paint.setChecked(False)
                self.toggle_paint_mode(False)

            self.btn_toggle_selection.setText("Disable Selection")
            self.btn_toggle_selection.setStyleSheet(
                "background-color: #27ae60; font-weight: bold;"
            )
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
            self.grid_item.setFlag(
                QGraphicsObject.GraphicsItemFlag.ItemIsMovable, False
            )
        else:
            self.btn_toggle_selection.setText("Enable Selection")
            self.btn_toggle_selection.setStyleSheet(
                "background-color: #ffa500; font-weight: bold;"
            )
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self.grid_item.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)

    def clear_selection(self):
        if self.selection_rect_item:
            self.scene.removeItem(self.selection_rect_item)
            self.selection_rect_item = None

        self.btn_cut_selection.setEnabled(False)
        self.btn_copy_selection.setEnabled(False)
        self.btn_clear_selection.setEnabled(False)

    def cut_selection(self):
        if not self.selection_rect_item or not self.current_image_pil:
            return

        self.save_state()

        self.copy_selection()

        rect = self.selection_rect_item.rect()
        x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())

        active_layer = self.get_active_layer()
        if active_layer and active_layer.name != "Main" and active_layer.image:
            layer_x = x - active_layer.x
            layer_y = y - active_layer.y
            transparent_box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            active_layer.image.paste(transparent_box, (layer_x, layer_y))
            if active_layer.id in self.layer_graphics_items:
                qim = self.pil_to_qimage(active_layer.image)
                pix = QPixmap.fromImage(qim)
                self.layer_graphics_items[active_layer.id].setPixmap(pix)
            self.compose_and_display_layers()
        else:
            transparent_box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            self.current_image_pil.paste(transparent_box, (x, y))
            self.update_canvas_image()

        self.clear_selection()

        QMessageBox.information(self, "Cut", "Seleção recortada.")

    def copy_selection(self):
        if not self.selection_rect_item or not self.current_image_pil:
            return

        rect = self.selection_rect_item.rect()
        x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())

        active_layer = self.get_active_layer()
        if active_layer and active_layer.name != "Main" and active_layer.image:
            img_w, img_h = active_layer.image.size
            layer_x = x - active_layer.x
            layer_y = y - active_layer.y
            if layer_x < 0 or layer_y < 0 or layer_x + w > img_w or layer_y + h > img_h:
                QMessageBox.warning(
                    self, "Invalid Selection", "Seleção fora dos limites do layer!"
                )
                return

            box = (layer_x, layer_y, layer_x + w, layer_y + h)
            self.selected_image_data = active_layer.image.crop(box)
        else:
            img_w, img_h = self.current_image_pil.size
            if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
                QMessageBox.warning(
                    self, "Invalid Selection", "Seleção fora dos limites da imagem!"
                )
                return

            box = (x, y, x + w, y + h)
            self.selected_image_data = self.current_image_pil.crop(box)

        self.btn_paste_selection.setEnabled(True)

    def paste_selection(self):
        if not self.selected_image_data or not self.current_image_pil:
            return

        self.save_state()

        sel_w, sel_h = self.selected_image_data.size

        active_layer = self.get_active_layer()
        if active_layer and active_layer.name != "Main" and active_layer.image:
            img_w, img_h = active_layer.image.size
            x = (img_w - sel_w) // 2
            y = (img_h - sel_h) // 2
            # Coordenada na cena = offset do layer + posicao calculada
            scene_x = active_layer.x + x
            scene_y = active_layer.y + y
            self.paste_to_layer_with_expansion(active_layer, self.selected_image_data, scene_x, scene_y)
        else:
            img_w, img_h = self.current_image_pil.size
            x = (img_w - sel_w) // 2
            y = (img_h - sel_h) // 2
            self.current_image_pil.paste(self.selected_image_data, (x, y), self.selected_image_data)
            self.update_canvas_image()

        QMessageBox.information(self, "Paste", "Seleção colada")


            
    def toggle_eraser_mode(self, checked):
        self.eraser_mode = checked
        if checked:
            if self.selection_mode:
                self.btn_toggle_eraser.setChecked(False)
                self.toggle_selection_mode(False)
            if self.paint_mode:
                self.btn_toggle_paint.setChecked(False)
                self.toggle_paint_mode(False)
            self.btn_toggle_eraser.setText("Disable Eraser")
            self.btn_toggle_eraser.setStyleSheet("background-color: #51cf66; font-weight: bold")
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
            self.grid_item.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, False)
            # ATIVAR OVERLAY
            self.eraser_overlay.setVisible(True)
            self.eraser_overlay.setSize(self.eraser_size)
        else:
            self.btn_toggle_eraser.setText("Enable Eraser")
            self.btn_toggle_eraser.setStyleSheet("background-color: #ff6b6b; font-weight: bold")
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self.grid_item.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)
            self.last_eraser_point = None
            # DESATIVAR OVERLAY
            self.eraser_overlay.setVisible(False)


    def on_eraser_size_change(self, value):
        self.eraser_size = value
        self.eraser_overlay.setSize(value)


    def view_mouse_press(self, event):
        modifiers = QApplication.keyboardModifiers()
        item_at_pos = self.view.itemAt(event.pos())
        
        
        
        if self.cut_size_mode:
            scene_pos = self.view.mapToScene(event.pos())
            self.cut_start_pos = scene_pos
            self.is_drawing_cut_rect = True
            event.accept()
            return        

        if self.eraser_mode and event.button() == Qt.MouseButton.LeftButton:
            self.save_state()
            scene_pos = self.view.mapToScene(event.pos())
            self.last_eraser_point = QPoint(int(scene_pos.x()), int(scene_pos.y()))
            self.erase_at_point(self.last_eraser_point)

        elif self.paint_mode:
            if event.button() == Qt.MouseButton.LeftButton:
                self.save_state()
                scene_pos = self.view.mapToScene(event.pos())
                self.last_paint_point = QPoint(int(scene_pos.x()), int(scene_pos.y()))
                self.paint_at_point(self.last_paint_point)
            elif event.button() == Qt.MouseButton.RightButton:
                self.save_state()
                scene_pos = self.view.mapToScene(event.pos())
                self.last_eraser_point = QPoint(int(scene_pos.x()), int(scene_pos.y()))
                
                old_size = self.eraser_size
                old_feather = self.eraser_feathering
                self.eraser_size = self.paint_size
                self.eraser_feathering = self.paint_feathering
                
                self.erase_at_point(self.last_eraser_point)
                
                self.eraser_size = old_size
                self.eraser_feathering = old_feather

        elif self.selection_mode and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.view.mapToScene(event.pos())

            if (
                modifiers == Qt.KeyboardModifier.ControlModifier
                and self.selection_rect_item
            ):
                if self.selection_rect_item.contains(
                    self.selection_rect_item.mapFromScene(scene_pos)
                ):
                    self.start_moving_selection(scene_pos)
                    return

            self.selection_start = scene_pos
            self.is_drawing_selection = True

            if self.selection_rect_item:
                self.scene.removeItem(self.selection_rect_item)
                if self.floating_selection_pixmap:
                    self.scene.removeItem(self.floating_selection_pixmap)
                    self.floating_selection_pixmap = None

            self.selection_rect_item = SelectionRectangle()
            self.scene.addItem(self.selection_rect_item)
        else:
            QGraphicsView.mousePressEvent(self.view, event)

    def view_mouse_move(self, event):
        
        if self.eraser_mode:
            scenepos = self.view.mapToScene(event.pos())
            self.eraser_overlay.updatePosition(scenepos)        
        
        
        if self.cut_size_mode and self.is_drawing_cut_rect and self.cut_start_pos:
            scene_pos = self.view.mapToScene(event.pos())
            
            x1 = min(self.cut_start_pos.x(), scene_pos.x())
            y1 = min(self.cut_start_pos.y(), scene_pos.y())
            x2 = max(self.cut_start_pos.x(), scene_pos.x())
            y2 = max(self.cut_start_pos.y(), scene_pos.y())
            
            width = x2 - x1
            height = y2 - y1
            
            if width > 0 and height > 0:
                rect = QRectF(x1, y1, width, height)
                self.create_cut_rect(rect)
            
            event.accept()
            return
                
        
        
        if self.eraser_mode and event.buttons() & Qt.MouseButton.LeftButton:
            scene_pos = self.view.mapToScene(event.pos())
            current_point = QPoint(int(scene_pos.x()), int(scene_pos.y()))

            if self.last_eraser_point:
                self.erase_line(self.last_eraser_point, current_point)

            self.last_eraser_point = current_point
            
            
            
           

        elif self.paint_mode:
            scene_pos = self.view.mapToScene(event.pos())
            current_point = QPoint(int(scene_pos.x()), int(scene_pos.y()))

            if event.buttons() & Qt.MouseButton.LeftButton:
                if self.last_paint_point:
                    self.paint_line(self.last_paint_point, current_point)
                self.last_paint_point = current_point

            elif event.buttons() & Qt.MouseButton.RightButton:
                if self.last_eraser_point:
                    old_size = self.eraser_size
                    old_feather = self.eraser_feathering
                    self.eraser_size = self.paint_size
                    self.eraser_feathering = self.paint_feathering
                    
                    self.erase_line(self.last_eraser_point, current_point)
                    
                    self.eraser_size = old_size
                    self.eraser_feathering = old_feather
                self.last_eraser_point = current_point

        elif self.selection_mode:
            if self.is_moving_selection and event.buttons() & Qt.MouseButton.LeftButton:
                scene_pos = self.view.mapToScene(event.pos())
                self.move_selection(scene_pos)

            elif self.is_drawing_selection:
                scene_pos = self.view.mapToScene(event.pos())
                rect = QRectF(self.selection_start, scene_pos).normalized()
                self.selection_rect_item.set_rect(rect)
        else:
            QGraphicsView.mouseMoveEvent(self.view, event)

    def view_mouse_release(self, event):
        
     # NOVO: Cut Size Mode
        if self.cut_size_mode and self.is_drawing_cut_rect:
            self.is_drawing_cut_rect = False
            event.accept()
            return       
        
        
        if self.eraser_mode:
            self.last_eraser_point = None

        elif self.paint_mode:
            self.last_paint_point = None
            self.last_eraser_point = None

        elif self.selection_mode:
            if self.is_moving_selection:
                self.finish_moving_selection()
            elif self.is_drawing_selection:
                self.is_drawing_selection = False

                if (
                    self.selection_rect_item
                    and not self.selection_rect_item.rect().isEmpty()
                ):
                    self.btn_cut_selection.setEnabled(True)
                    self.btn_copy_selection.setEnabled(True)
                    self.btn_clear_selection.setEnabled(True)
        else:
            QGraphicsView.mouseReleaseEvent(self.view, event)

    def paste_to_layer_with_expansion(self, active_layer, img_to_paste, scene_x, scene_y):
        layer_x = scene_x - active_layer.x
        layer_y = scene_y - active_layer.y
        
        min_x = min(0, layer_x)
        min_y = min(0, layer_y)
        max_x = max(active_layer.image.width, layer_x + img_to_paste.width)
        max_y = max(active_layer.image.height, layer_y + img_to_paste.height)
        
        if min_x < 0 or min_y < 0 or max_x > active_layer.image.width or max_y > active_layer.image.height:
            new_w = max_x - min_x
            new_h = max_y - min_y
            new_img = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
            new_img.paste(active_layer.image, (-min_x, -min_y))
            new_img.paste(img_to_paste, (layer_x - min_x, layer_y - min_y), img_to_paste)
            
            active_layer.image = new_img
            active_layer.x += min_x
            active_layer.y += min_y
        else:
            active_layer.image.paste(img_to_paste, (layer_x, layer_y), img_to_paste)
            
        if active_layer.id in self.layer_graphics_items:
            item = self.layer_graphics_items[active_layer.id]
            qim = self.pil_to_qimage(active_layer.image)
            pix = QPixmap.fromImage(qim)
            item.setPixmap(pix)
            item.setPos(active_layer.x, active_layer.y)
        self.compose_and_display_layers()

    def start_moving_selection(self, scene_pos):
        if not self.current_image_pil or not self.selection_rect_item:
            return

        self.save_state()
        self.is_moving_selection = True
        self.move_start_pos = scene_pos

        rect = self.selection_rect_item.rect()
        x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())

        active_layer = self.get_active_layer()
        if active_layer and active_layer.name != "Main" and active_layer.image:
            layer_x = x - active_layer.x
            layer_y = y - active_layer.y
            box = (layer_x, layer_y, layer_x + w, layer_y + h)
            self.selected_image_data = active_layer.image.crop(box)

            transparent_box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            active_layer.image.paste(transparent_box, (layer_x, layer_y))
            if active_layer.id in self.layer_graphics_items:
                qim = self.pil_to_qimage(active_layer.image)
                pix = QPixmap.fromImage(qim)
                self.layer_graphics_items[active_layer.id].setPixmap(pix)
            self.compose_and_display_layers()
        else:
            box = (x, y, x + w, y + h)
            self.selected_image_data = self.current_image_pil.crop(box)

            transparent_box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            self.current_image_pil.paste(transparent_box, (x, y))
            self.update_canvas_image()

        qim = self.pil_to_qimage(self.selected_image_data)
        pix = QPixmap.fromImage(qim)

        if self.floating_selection_pixmap:
            self.scene.removeItem(self.floating_selection_pixmap)

        self.floating_selection_pixmap = QGraphicsPixmapItem(pix)
        self.floating_selection_pixmap.setPos(x, y)
        self.floating_selection_pixmap.setZValue(20)
        self.scene.addItem(self.floating_selection_pixmap)

        self.view.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)

    def move_selection(self, scene_pos):
        if not self.is_moving_selection or not self.move_start_pos:
            return

        delta = scene_pos - self.move_start_pos

        rect = self.selection_rect_item.rect()
        new_rect = rect.translated(delta.x(), delta.y())
        self.selection_rect_item.set_rect(new_rect)

        if self.floating_selection_pixmap:
            current_pos = self.floating_selection_pixmap.pos()
            self.floating_selection_pixmap.setPos(
                current_pos.x() + delta.x(), current_pos.y() + delta.y()
            )

        self.move_start_pos = scene_pos

    def finish_moving_selection(self):
        if not self.is_moving_selection:
            return

        if self.floating_selection_pixmap:
            final_pos = self.floating_selection_pixmap.pos()
            x, y = int(final_pos.x()), int(final_pos.y())

            if self.selected_image_data:
                active_layer = self.get_active_layer()
                if active_layer and active_layer.name != "Main" and active_layer.image:
                    self.paste_to_layer_with_expansion(active_layer, self.selected_image_data, x, y)
                else:
                    self.current_image_pil.paste(self.selected_image_data, (x, y), self.selected_image_data)
                    self.update_canvas_image()

            self.scene.removeItem(self.floating_selection_pixmap)
            self.floating_selection_pixmap = None

        self.is_moving_selection = False
        self.move_start_pos = None
        self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def erase_at_point(self, point):
        if not self.current_image_pil:
            return

        x, y = point.x(), point.y()
        w, h = self.current_image_pil.size

        if x < 0 or y < 0 or x >= w or y >= h:
            return

        size = max(1, self.eraser_size)

        left = x - size // 2
        top = y - size // 2
        right = left + size - 1
        bottom = top + size - 1

        if self.eraser_feathering == 0:
            draw = ImageDraw.Draw(self.current_image_pil, "RGBA")
            bbox = [left, top, right, bottom]

            temp = Image.new("RGBA", self.current_image_pil.size, (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp)
            if size == 1:
                temp_draw.point((x, y), fill=(0, 0, 0, 255))
            else:
                temp_draw.ellipse(bbox, fill=(0, 0, 0, 255))

            mask = temp.split()[3]

            pixels = self.current_image_pil.load()
            mask_pixels = mask.load()

            for py in range(max(0, top), min(h, bottom + 1)):
                for px in range(max(0, left), min(w, right + 1)):
                    if mask_pixels[px, py] > 0:
                        pixels[px, py] = (0, 0, 0, 0)
        else:
            blur_radius = int((self.eraser_feathering / 100.0) * (size / 2))

            margin = blur_radius + 10
            temp_w = size + margin * 2
            temp_h = size + margin * 2

            mask = Image.new("L", (temp_w, temp_h), 0)
            mask_draw = ImageDraw.Draw(mask)

            if size == 1:
                mask_draw.point((margin, margin), fill=255)
            else:
                mask_draw.ellipse([margin, margin, margin + size - 1, margin + size - 1], fill=255)

            if blur_radius > 0:
                mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            paste_x = left - margin
            paste_y = top - margin

            mask_pixels = mask.load()
            img_pixels = self.current_image_pil.load()

            for py in range(temp_size[1]):
                for px in range(temp_size[0]):
                    img_x = paste_x + px
                    img_y = paste_y + py

                    if 0 <= img_x < w and 0 <= img_y < h:
                        mask_alpha = mask_pixels[px, py]

                        if mask_alpha > 0:
                            current_pixel = img_pixels[img_x, img_y]
                            r, g, b, a = current_pixel

                            erase_factor = mask_alpha / 255.0
                            new_alpha = int(a * (1.0 - erase_factor))

                            img_pixels[img_x, img_y] = (r, g, b, new_alpha)

        self.update_canvas_image()

    def erase_line(self, start, end):
        if not self.current_image_pil:
            return

        x1, y1 = start.x(), start.y()
        x2, y2 = end.x(), end.y()

        distance = max(abs(x2 - x1), abs(y2 - y1))

        if distance == 0:
            self.erase_at_point(start)
            return

        for i in range(distance + 1):
            t = i / distance
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)
            self.erase_at_point(QPoint(x, y))

    def update_grid_visuals(self):
        rows = self.spin_rows.value()
        cols = self.spin_cols.value()
        subs = self.chk_subdivisions.isChecked()
        self.grid_item.update_grid(rows, cols, subs, self.cell_size)

    def open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.bmp *.jpg)"
        )
        if file_path:
            try:
                self.current_image_pil = Image.open(file_path).convert("RGBA")
                self.original_image_pil = self.current_image_pil.copy()

                self.undo_stack.clear()
                self.redo_stack.clear()

                w, h = self.current_image_pil.size
                self.spin_resize_width.blockSignals(True)
                self.spin_resize_height.blockSignals(True)
                self.spin_resize_width.setValue(w)
                self.spin_resize_height.setValue(h)
                self.spin_resize_width.blockSignals(False)
                self.spin_resize_height.blockSignals(False)

                self.update_canvas_image()

                self.grid_item.setPos(0, 0)
                self.spin_x.setValue(0)
                self.spin_y.setValue(0)

                self.btn_apply_resize.setEnabled(True)
                self.btn_reset_image.setEnabled(True)
                self.btn_pick_color.setEnabled(True)
                self.btn_remove_color.setEnabled(True)
                self.btn_remove_by_opacity.setEnabled(True)
                self.btn_toggle_eraser.setEnabled(True)
                self.btn_toggle_paint.setEnabled(True)
                self.btn_choose_color.setEnabled(True)
                self.btn_pick_paint_color.setEnabled(True)  # NOVO
                self.btn_toggle_selection.setEnabled(True)
                self.btn_outline_color.setEnabled(True)
                self.btn_apply_outline.setEnabled(True)
                self.btn_erase_edges.setEnabled(True)
                self.btn_apply_sharpen.setEnabled(True)

                self.btn_apply_color.setEnabled(True)
                self.btn_reset_color.setEnabled(True)
                self.chk_enable_fine_grid.setEnabled(True)
                self.btn_cut_size.setEnabled(True)
                self.btn_apply_pixel_snap.setEnabled(True)
            # Rotate Fine
                self.btn_apply_rotate_fine.setEnabled(True)
                self.slider_rotate_fine.setEnabled(True)
                self.spin_rotate_fine.setEnabled(True)

                # Habilita botões de upscale/denoise
                self.update_upscale_button_state()

                # Cria o layer principal
                self.add_main_layer()

            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def add_blank_image(self):
        """
        Cria uma imagem vazia (transparente) com o tamanho definido
        em Width/Height, e a define como imagem principal (Main).
        """
        from PIL import Image

        width = self.spin_resize_width.value()
        height = self.spin_resize_height.value()

        if width <= 0 or height <= 0:
            QMessageBox.warning(self, "Invalid Size", "Width e Height devem ser > 0.")
            return

        # Cria imagem RGBA transparente
        blank = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # Limpa stacks de undo/redo
        self.undo_stack.clear()
        self.redo_stack.clear()

        # Define como original e atual
        self.original_image_pil = blank.copy()
        self.current_image_pil = blank

        # Atualiza spinboxes (garante coerência)
        self.spin_resize_width.blockSignals(True)
        self.spin_resize_height.blockSignals(True)
        self.spin_resize_width.setValue(width)
        self.spin_resize_height.setValue(height)
        self.spin_resize_width.blockSignals(False)
        self.spin_resize_height.blockSignals(False)

        # Atualiza canvas
        self.update_canvas_image()

        # Reset grid posição
        self.grid_item.setPos(0, 0)
        self.spin_x.setValue(0)
        self.spin_y.setValue(0)

        # Habilita os mesmos controles que quando abre uma imagem
        self.btn_apply_resize.setEnabled(True)
        self.btn_reset_image.setEnabled(True)
        self.btn_pick_color.setEnabled(True)
        self.btn_remove_color.setEnabled(True)
        self.btn_remove_by_opacity.setEnabled(True)
        self.btn_toggle_eraser.setEnabled(True)
        self.btn_toggle_paint.setEnabled(True)
        self.btn_choose_color.setEnabled(True)
        self.btn_pick_paint_color.setEnabled(True)
        self.btn_toggle_selection.setEnabled(True)
        self.btn_outline_color.setEnabled(True)
        self.btn_apply_outline.setEnabled(True)
        self.btn_erase_edges.setEnabled(True)
        self.btn_apply_sharpen.setEnabled(True)

        self.btn_apply_color.setEnabled(True)
        self.btn_reset_color.setEnabled(True)
        self.chk_enable_fine_grid.setEnabled(True)
        self.btn_cut_size.setEnabled(True)
        self.btn_apply_pixel_snap.setEnabled(True)

        # Cria Layer Main baseado nessa imagem em branco
        self.add_main_layer()

        self.lbl_layer_info.setText(
            "Projeto em branco criado como Layer Main. Você pode pintar e adicionar layers."
        )

    def update_color_preview(self, text):
        if self.hex_to_rgb(text):
            self.lbl_preview_color.setStyleSheet(
                f"background-color: {text}; border: 1px solid #222;"
            )
        else:
            self.lbl_preview_color.setStyleSheet(
                "background-color: #333; border: 1px solid #222;"
            )

    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            return None
        try:
            return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return None

    def remove_color_to_transparent(self):
        if not self.current_image_pil:
            return

        self.save_state()

        hex_color = self.line_hex_color.text().strip()
        target_rgb = self.hex_to_rgb(hex_color)

        if not target_rgb:
            QMessageBox.warning(
                self, "Invalid Color", "Digite uma cor hex válida (ex: #dcff73)"
            )
            return

        tolerance = self.spin_tolerance.value()
        smoothness = getattr(self, 'spin_smoothness', None)
        smoothness_val = smoothness.value() if smoothness else 0

        try:
            img = self.current_image_pil.convert("RGBA")
            datas = img.getdata()

            newData = []
            pixels_changed = 0

            import math

            for item in datas:
                r, g, b, a = item
                if a == 0:
                    newData.append(item)
                    continue

                dist = math.sqrt((r - target_rgb[0])**2 + (g - target_rgb[1])**2 + (b - target_rgb[2])**2)

                if dist <= tolerance:
                    newData.append((r, g, b, 0))
                    pixels_changed += 1
                elif smoothness_val > 0 and dist <= tolerance + smoothness_val:
                    factor = (dist - tolerance) / smoothness_val
                    new_a = int(a * factor)
                    newData.append((r, g, b, new_a))
                    pixels_changed += 1
                else:
                    newData.append(item)

            img.putdata(newData)
            self.current_image_pil = img
            self.update_canvas_image()

            QMessageBox.information(
                self,
                "Color Removed",
                f"Cor {hex_color} removida!\n{pixels_changed} pixels tornados transparentes.",
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def remove_by_opacity(self):
        if not self.current_image_pil:
            return

        self.save_state()

        max_opacity_percent = self.spin_remove_opacity.value()
        max_opacity_alpha = int((max_opacity_percent / 100.0) * 255)

        try:
            img = self.current_image_pil.convert("RGBA")
            datas = img.getdata()

            newData = []
            pixels_changed = 0

            for item in datas:
                r, g, b, a = item
                # we don't need to change already fully transparent pixels
                if a <= max_opacity_alpha and a > 0:
                    newData.append((r, g, b, 0))
                    pixels_changed += 1
                else:
                    newData.append(item)

            img.putdata(newData)
            self.current_image_pil = img
            self.update_canvas_image()

            QMessageBox.information(
                self,
                "Opacity Removed",
                f"{pixels_changed} pixels removidos com opacidade <= {max_opacity_percent}%!",
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def choose_outline_color(self):
        color = QColorDialog.getColor(
            self.outline_color, self, "Escolher Cor do Outline"
        )

        if color.isValid():
            self.outline_color = color
            self.lbl_outline_color_preview.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid #222;"
            )

    def apply_sharpen(self):
        if not self.current_image_pil:
            return

        self.save_state()

        try:
            from PIL import ImageFilter
            radius = self.spin_sharpen_radius.value()
            percent = self.spin_sharpen_percent.value()
            threshold = 3

            if self.current_image_pil.mode == "RGBA":
                r, g, b, a = self.current_image_pil.split()
                rgb_image = Image.merge("RGB", (r, g, b))
                rgb_image = rgb_image.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))
                r2, g2, b2 = rgb_image.split()
                self.current_image_pil = Image.merge("RGBA", (r2, g2, b2, a))
            else:
                self.current_image_pil = self.current_image_pil.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))

            self.update_canvas_image()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Erro ao aplicar sharpening: {str(e)}")

    def apply_outline(self):
        if not self.current_image_pil:
            return

        self.save_state()

        try:
            import numpy as np
            from scipy.ndimage import distance_transform_edt

            thickness = self.spin_outline_thickness.value()
            feathering = self.spin_outline_feathering.value()

            r = self.outline_color.red()
            g = self.outline_color.green()
            b = self.outline_color.blue()
            a = self.outline_color.alpha()

            w, h = self.current_image_pil.size

            if self.current_image_pil.mode == "RGBA":
                alpha_mask = self.current_image_pil.split()[3]
            else:
                alpha_mask = Image.new("L", (w, h), 255)

            # Convert alpha to binary: opaque (True) vs transparent (False)
            alpha_arr = np.array(alpha_mask, dtype=np.float64)
            opaque = alpha_arr > 128

            # Distance from each TRANSPARENT pixel to the nearest OPAQUE pixel
            # distance_transform_edt computes distance from each False pixel 
            # to nearest True pixel when we invert
            transparent = ~opaque
            dist_from_opaque = distance_transform_edt(transparent)

            # Distance from each OPAQUE pixel to the nearest TRANSPARENT pixel
            # (needed to remove the outline from inside the sprite)
            dist_from_transparent = distance_transform_edt(opaque)

            if feathering == 0:
                # Sharp outline: pixels within 'thickness' distance from
                # the opaque region boundary, but only on the outside
                outline_mask_arr = np.zeros((h, w), dtype=np.uint8)
                # Outside pixels that are within thickness distance of the sprite
                outside_near = (dist_from_opaque > 0) & (dist_from_opaque <= thickness)
                outline_mask_arr[outside_near] = 255

            else:
                # Feathered outline with smooth falloff
                outline_mask_arr = np.zeros((h, w), dtype=np.float64)
                
                # Base outline region
                outside_near = (dist_from_opaque > 0) & (dist_from_opaque <= thickness)
                outline_mask_arr[outside_near] = 255.0

                # Anti-alias the outer boundary
                boundary = (dist_from_opaque > thickness) & (dist_from_opaque <= thickness + 1.0)
                if np.any(boundary):
                    frac = 1.0 - (dist_from_opaque[boundary] - thickness)
                    outline_mask_arr[boundary] = frac * 255.0

                # Apply feathering as gaussian blur on the mask
                from PIL import ImageFilter
                feather_img = Image.fromarray(outline_mask_arr.astype(np.uint8), mode="L")
                blur_amount = (feathering / 100.0) * max(thickness, 0.5)
                if blur_amount > 0:
                    feather_img = feather_img.filter(
                        ImageFilter.GaussianBlur(radius=blur_amount)
                    )
                outline_mask_arr = np.array(feather_img, dtype=np.uint8)

            expanded_mask = Image.fromarray(outline_mask_arr, mode="L")

            # Create the colored outline layer
            outline_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            outline_color_layer = Image.new("RGBA", (w, h), (r, g, b, a))
            outline_layer.paste(outline_color_layer, (0, 0), expanded_mask)

            # Composite: outline behind, then original on top
            result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            result.paste(outline_layer, (0, 0), outline_layer)
            result.paste(self.current_image_pil, (0, 0), self.current_image_pil)

            self.current_image_pil = result
            self.update_canvas_image()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Erro ao aplicar outline: {str(e)}")

    def erase_edges(self):
        if not self.current_image_pil:
            return

        self.save_state()

        try:
            import numpy as np
            from scipy.ndimage import distance_transform_edt

            distance = self.spin_edge_eraser_distance.value()
            feathering = self.spin_edge_eraser_feathering.value()

            w, h = self.current_image_pil.size

            if self.current_image_pil.mode == "RGBA":
                alpha = self.current_image_pil.split()[3]
            else:
                self.current_image_pil = self.current_image_pil.convert("RGBA")
                alpha = self.current_image_pil.split()[3]

            # Convert alpha to binary
            alpha_arr = np.array(alpha, dtype=np.float64)
            opaque = alpha_arr > 128

            # Distance from each OPAQUE pixel to nearest TRANSPARENT pixel
            # This tells us how far inside the sprite each pixel is
            dist_from_edge = distance_transform_edt(opaque)

            if feathering == 0:
                # Sharp erosion: remove pixels within 'distance' of the edge
                eroded_arr = np.zeros((h, w), dtype=np.uint8)

                # Keep only pixels deeper inside than 'distance'
                deep_inside = dist_from_edge > distance
                eroded_arr[deep_inside] = 255

                # Preserve original alpha for pixels that survive (don't make
                # semi-transparent pixels opaque)
                orig_arr = np.array(alpha, dtype=np.uint8)
                eroded_arr = np.minimum(eroded_arr, orig_arr)

            else:
                # Feathered erosion with smooth falloff
                eroded_arr = np.zeros((h, w), dtype=np.float64)

                deep_inside = dist_from_edge > distance
                eroded_arr[deep_inside] = 255.0

                boundary = (dist_from_edge > (distance - 1.0)) & (dist_from_edge <= distance)
                if np.any(boundary):
                    frac = dist_from_edge[boundary] - (distance - 1.0)
                    frac = np.clip(frac, 0.0, 1.0)
                    eroded_arr[boundary] = frac * 255.0

                # Apply feathering as gaussian blur
                from PIL import ImageFilter
                feather_img = Image.fromarray(eroded_arr.astype(np.uint8), mode="L")
                blur_amount = (feathering / 100.0) * max(distance, 0.5)
                if blur_amount > 0:
                    feather_img = feather_img.filter(
                        ImageFilter.GaussianBlur(radius=blur_amount)
                    )
                eroded_arr = np.array(feather_img, dtype=np.uint8)

                # Preserve original alpha
                orig_arr = np.array(alpha, dtype=np.uint8)
                eroded_arr = np.minimum(eroded_arr, orig_arr)

            eroded_mask = Image.fromarray(eroded_arr.astype(np.uint8), mode="L")
            self.current_image_pil.putalpha(eroded_mask)

            self.update_canvas_image()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Erro ao apagar bordas: {str(e)}")

    def enable_color_picker(self):
        self.color_picker_mode = True
        self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)

        self.original_mouse_press = self.view.mousePressEvent
        self.view.mousePressEvent = self.pick_color_from_image

    def pick_color_from_image(self, event):
        if not self.color_picker_mode or not self.current_image_pil:
            return

        scene_pos = self.view.mapToScene(event.pos())
        x = int(scene_pos.x())
        y = int(scene_pos.y())

        w, h = self.current_image_pil.size
        if 0 <= x < w and 0 <= y < h:
            pixel = self.current_image_pil.getpixel((x, y))
            r, g, b = pixel[:3]

            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            self.line_hex_color.setText(hex_color)
            self.lbl_preview_color.setStyleSheet(
                f"background-color: {hex_color}; border: 1px solid #222;"
            )

            QMessageBox.information(
                self,
                "Color Selected",
                f"Cor selecionada: {hex_color}\nRGB: ({r}, {g}, {b})",
            )

        self.color_picker_mode = False
        self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.view.mousePressEvent = self.view_mouse_press

    def on_resize_width_change(self, value):
        if self.chk_keep_aspect.isChecked() and self.original_image_pil:
            w, h = self.original_image_pil.size
            aspect_ratio = h / w
            new_height = int(value * aspect_ratio)
            self.spin_resize_height.blockSignals(True)
            self.spin_resize_height.setValue(new_height)
            self.spin_resize_height.blockSignals(False)

    def on_resize_height_change(self, value):
        if self.chk_keep_aspect.isChecked() and self.original_image_pil:
            w, h = self.original_image_pil.size
            aspect_ratio = w / h
            new_width = int(value * aspect_ratio)
            self.spin_resize_width.blockSignals(True)
            self.spin_resize_width.setValue(new_width)
            self.spin_resize_width.blockSignals(False)

    def apply_resize(self):
        """Aplica o resize na imagem atual"""
        if not self.original_image_pil:
            return

        self.save_state()

        new_width = self.spin_resize_width.value()
        new_height = self.spin_resize_height.value()

        method_map = {
            0: Image.NEAREST,
            1: Image.BILINEAR,
            2: Image.BICUBIC,
            3: Image.LANCZOS,
        }

        resize_method = method_map[self.combo_resize_method.currentIndex()]

        try:
            self.current_image_pil = self.original_image_pil.resize(
                (new_width, new_height), resize_method
            )
            self.update_canvas_image()

            QMessageBox.information(
                self, "Resize Applied", f"Image resized to {new_width}x{new_height}px"
            )

        except Exception as e:
            QMessageBox.critical(self, "Resize Error", str(e))

    def apply_pixel_snap(self):
        """
        Aplica pixel snapping na imagem atual para converter imagens de IA
        em pixel art estilo Tibia. Pipeline:
        1. Posterizar cores (reduz gradientes suaves)
        2. Quantizar paleta (K-means para limitar cores)
        3. Snap alpha (binariza para bordas 100% nítidas)
        """
        if not self.current_image_pil:
            return

        self.save_state()

        try:
            import numpy as np

            img = self.current_image_pil.copy()
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            img_array = np.array(img)
            rgb = img_array[:, :, :3]
            alpha = img_array[:, :, 3]

            # Passo 1: Posterizar
            if self.chk_snap_posterize.isChecked():
                levels = self.spin_snap_posterize.value()
                if levels < 256:
                    divisor = 256.0 / levels
                    rgb = (np.floor(rgb.astype(np.float32) / divisor) * divisor).astype(np.uint8)

            # Passo 2: Quantizar paleta (K-means)
            if self.chk_snap_quantize.isChecked():
                import cv2 as cv
                n_colors = self.spin_snap_colors.value()
                h, w = rgb.shape[:2]
                pixels = rgb.reshape(-1, 3).astype(np.float32)

                criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 20, 1.0)
                _, labels, centers = cv.kmeans(
                    pixels, n_colors, None, criteria,
                    attempts=3, flags=cv.KMEANS_PP_CENTERS
                )
                centers = centers.astype(np.uint8)
                rgb = centers[labels.flatten()].reshape(h, w, 3)

            # Passo 3: Snap alpha (bordas duras)
            if self.chk_snap_alpha.isChecked():
                alpha = np.where(alpha > 127, 255, 0).astype(np.uint8)

            # Recombinar
            result = np.dstack([rgb, alpha])
            self.current_image_pil = Image.fromarray(result, "RGBA")
            self.update_canvas_image()

            # Conta cores únicas
            mask = alpha > 0
            visible_pixels = rgb[mask]
            if len(visible_pixels) > 0:
                unique_colors = len(np.unique(visible_pixels.reshape(-1, 3), axis=0))
            else:
                unique_colors = 0

            QMessageBox.information(
                self,
                "Pixel Snap Applied",
                f"Pixel snap aplicado!\n"
                f"Cores únicas: {unique_colors}\n"
                f"Tamanho: {self.current_image_pil.width}x{self.current_image_pil.height}px"
            )

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            QMessageBox.critical(
                self, "Pixel Snap Error",
                f"Erro ao aplicar pixel snap: {str(e)}\n\n{error_details}"
            )


    def reset_to_original(self):
        if not self.original_image_pil:
            return

        self.save_state()

        self.current_image_pil = self.original_image_pil.copy()

        w, h = self.current_image_pil.size
        self.spin_resize_width.blockSignals(True)
        self.spin_resize_height.blockSignals(True)
        self.spin_resize_width.setValue(w)
        self.spin_resize_height.setValue(h)
        self.spin_resize_width.blockSignals(False)
        self.spin_resize_height.blockSignals(False)

        self.update_canvas_image()

    def update_canvas_image(self):
        if self.current_image_pil:
            qim = self.pil_to_qimage(self.current_image_pil)
            pix = QPixmap.fromImage(qim)
            self.pixmap_item.setPixmap(pix)
            self.create_fine_grid()

            self.scene.setSceneRect(QRectF(pix.rect()))

            w, h = self.current_image_pil.size
            self.spin_x.setRange(0, w)
            self.spin_y.setRange(0, h)

            # Atualiza o layer main se existir
            main_layer = self.get_main_layer()
            if main_layer:
                main_layer.image = self.current_image_pil.copy()
                # if main_layer.id in self.layer_widgets:
                    # self.layer_widgets[main_layer.id].update_thumbnail()

    def transform_image(self, mode):
        """
        Transforma a imagem (rotate, flip)
        Se um layer específico estiver selecionado, aplica APENAS nele
        Se Main estiver selecionado, aplica na imagem toda
        """
        if not self.current_image_pil:
            return
        
        # Obtém o layer ativo
        active_layer = self.get_active_layer()
        
        # Define se vai aplicar no layer ou na imagem inteira
        is_main_selected = not active_layer or active_layer.name == "Main"
        
        self.save_state()
        
        if is_main_selected:
            # Aplica na imagem toda (Main)
            if mode == "rotate_90":
                self.current_image_pil = self.current_image_pil.rotate(-90, expand=True)
            elif mode == "flip_h":
                self.current_image_pil = self.current_image_pil.transpose(Image.FLIP_LEFT_RIGHT)
            elif mode == "flip_v":
                self.current_image_pil = self.current_image_pil.transpose(Image.FLIP_TOP_BOTTOM)
            
            # Atualiza o layer main também
            main_layer = self.get_main_layer()
            if main_layer:
                main_layer.image = self.current_image_pil.copy()
            
            self.update_canvas_image()
            
            # if mode == "rotate_90":
                # QMessageBox.information(self, "Rotate", "Imagem rotacionada 90° no sentido anti-horário!")
            # elif mode == "flip_h":
                # QMessageBox.information(self, "Flip", "Imagem flipada horizontalmente!")
            # elif mode == "flip_v":
                # QMessageBox.information(self, "Flip", "Imagem flipada verticalmente!")
        else:
            # Aplica APENAS no layer selecionado
            if active_layer and active_layer.image:
                if mode == "rotate_90":
                    active_layer.image = active_layer.image.rotate(-90, expand=True)
                elif mode == "flip_h":
                    active_layer.image = active_layer.image.transpose(Image.FLIP_LEFT_RIGHT)
                elif mode == "flip_v":
                    active_layer.image = active_layer.image.transpose(Image.FLIP_TOP_BOTTOM)
                
                # Atualiza o item gráfico do layer
                if active_layer.id in self.layer_graphics_items:
                    qim = self.pil_to_qimage(active_layer.image)
                    pix = QPixmap.fromImage(qim)
                    self.layer_graphics_items[active_layer.id].setPixmap(pix)
                
                self.compose_and_display_layers()
                
                # if mode == "rotate_90":
                    # QMessageBox.information(
                        # self,
                        # "Layer Transform",
                        # f"Layer '{active_layer.name}' rotacionado 90°!"
                    # )
                # elif mode == "flip_h":
                    # QMessageBox.information(
                        # self,
                        # "Layer Transform",
                        # f"Layer '{active_layer.name}' flipado horizontalmente!"
                    # )
                # elif mode == "flip_v":
                    # QMessageBox.information(
                        # self,
                        # "Layer Transform",
                        # f"Layer '{active_layer.name}' flipado verticalmente!"
                    # )


    def on_grid_moved_by_mouse(self, x, y):
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        self.spin_x.setValue(x)
        self.spin_y.setValue(y)
        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)

    def on_cell_size_change(self, text):
        size = int(text.split('x')[0])
        self.cell_size = size
        if hasattr(self, 'grid_item') and self.grid_item:
            self.update_grid_visuals()

    def on_spinbox_change(self):
        x = self.spin_x.value()
        y = self.spin_y.value()
        self.grid_item.setPos(x, y)

    def on_zoom_change(self, value):
        scale = value / 100.0
        self.lbl_zoom_val.setText(f"{value}%")
        self.view.resetTransform()
        self.view.scale(scale, scale)

        self.view.zoom_factor = scale

    def cut_image(self):
        if not self.current_image_pil:
            return

        start_x = self.spin_x.value()
        start_y = self.spin_y.value()
        cols = self.spin_cols.value()
        rows = self.spin_rows.value()
        size = self.cell_size

        for c in range(cols):
            for r in range(rows):
                x = start_x + (c * size)
                y = start_y + (r * size)

                if (
                    x + size > self.current_image_pil.width
                    or y + size > self.current_image_pil.height
                ):
                    continue

                box = (x, y, x + size, y + size)
                sprite = self.current_image_pil.crop(box)

                if not self.chk_empty.isChecked():
                    if not sprite.getbbox():
                        continue

                self.add_sprite_to_list(sprite)

        if self.list_widget.count() > 0:
            self.btn_export.setEnabled(True)
            self.btn_import.setEnabled(True)            

    def add_sprite_to_list(self, pil_image):
        self.sliced_images.append(pil_image)

        qim = self.pil_to_qimage(pil_image)
        pix = QPixmap.fromImage(qim)

        icon = QIcon(pix)
        item = QListWidgetItem(icon, "")
        item.setSizeHint(QSize(40, 40))
        self.list_widget.addItem(item)
        self.list_widget.scrollToBottom()

    def clear_list(self):
        self.sliced_images.clear()
        self.list_widget.clear()
        self.btn_export.setEnabled(False)
        self.btn_import.setEnabled(False)        
        
        
    def import_sprites(self):
        if not self.sliced_images:
            return
        
        reply = QMessageBox.question(
            self, "Import", 
            f"Import {len(self.sliced_images)} sprites to the editor?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.sprites_imported.emit(self.sliced_images)
            self.close()
        
        

    def export_sprites(self):
        if not self.sliced_images:
            return

        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", "", QFileDialog.Option.ShowDirsOnly
        )

        if not output_dir:
            return

        from PyQt6.QtWidgets import QInputDialog

        prefix, ok = QInputDialog.getText(
            self, "Export Prefix", "Enter filename prefix:", text="sprite"
        )

        if not ok or not prefix:
            prefix = "sprite"

        try:
            for idx, sprite in enumerate(self.sliced_images):
                filename = f"{prefix}_{idx:04d}.png"
                filepath = f"{output_dir}/{filename}"
                sprite.save(filepath, "PNG")

            QMessageBox.information(
                self,
                "Export Complete",
                f"{len(self.sliced_images)} sprites exported successfully!",
            )

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

    @staticmethod
    def pil_to_qimage(pil_image):
        if pil_image.mode != "RGBA":
            pil_image = pil_image.convert("RGBA")
        data = pil_image.tobytes("raw", "RGBA")
        qimage = QImage(
            data, pil_image.width, pil_image.height, QImage.Format.Format_RGBA8888
        )
        return qimage

    def export_full_project(self):
        """
        Exporta o projeto inteiro como uma única imagem:
        usa self.current_image_pil (ou seja, a imagem atual com tudo aplicado).
        Não depende de cells/slice.
        """
        if not self.current_image_pil:
            QMessageBox.information(
                self, "Export", "Nenhuma imagem carregada para exportar."
            )
            return

        # Diálogo de salvar arquivo
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Project Image",
            "",
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;All Files (*)",
        )

        if not file_path:
            return

        try:
            # Decide o formato pelo filtro/ extensão
            fmt = None
            lower = file_path.lower()
            if lower.endswith(".jpg") or lower.endswith(".jpeg"):
                fmt = "JPEG"
            elif lower.endswith(".png"):
                fmt = "PNG"
            else:
                # Se não tiver extensão, usa PNG por padrão
                file_path = file_path + ".png"
                fmt = "PNG"

            # Salva a imagem atual
            self.current_image_pil.save(file_path, fmt)
            QMessageBox.information(
                self, "Export", f"Projeto exportado em:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Export Error", f"Erro ao exportar imagem:\n{str(e)}"
            )


    def on_rotate_fine_change(self, value):
        """Sincroniza o spin box com o slider"""
        self.spin_rotate_fine.blockSignals(True)
        self.spin_rotate_fine.setValue(value)
        self.spin_rotate_fine.blockSignals(False)

    def on_rotate_fine_spin_change(self, value):
        """Sincroniza o slider com o spin box"""
        self.slider_rotate_fine.blockSignals(True)
        self.slider_rotate_fine.setValue(value)
        self.slider_rotate_fine.blockSignals(False)

    def apply_rotate_fine(self):
        """Aplica a rotação fina"""
        if not self.current_image_pil:
            return
        
        # Obtém o layer ativo
        active_layer = self.get_active_layer()
        is_main_selected = not active_layer or active_layer.name == "Main"
        
        self.save_state()
        angle = self.spin_rotate_fine.value()
        
        try:
            if is_main_selected:
                # Rotaciona a imagem principal
                self.current_image_pil = self.current_image_pil.rotate(-angle, expand=True)
                
                # Atualiza o layer main também
                main_layer = self.get_main_layer()
                if main_layer:
                    main_layer.image = self.current_image_pil.copy()
                
                self.update_canvas_image()
                
                # QMessageBox.information(
                    # self,
                    # "Rotate Applied",
                    # f"Imagem rotacionada em {angle}°"
                # )
            else:
                # Rotaciona apenas o layer selecionado
                if active_layer and active_layer.image:
                    active_layer.image = active_layer.image.rotate(-angle, expand=True)
                    
                    # Atualiza o item gráfico do layer
                    if active_layer.id in self.layer_graphics_items:
                        qim = self.pil_to_qimage(active_layer.image)
                        pix = QPixmap.fromImage(qim)
                        self.layer_graphics_items[active_layer.id].setPixmap(pix)
                    
                    self.compose_and_display_layers()
                    
                    # QMessageBox.information(
                        # self,
                        # "Layer Rotate",
                        # f"Layer '{active_layer.name}' rotacionado em {angle}°"
                    # )
            
            self.reset_rotate_fine()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Erro ao rotacionar: {str(e)}")

    def reset_rotate_fine(self):
        """Reseta os controles de rotação fina"""
        self.slider_rotate_fine.blockSignals(True)
        self.spin_rotate_fine.blockSignals(True)
        
        self.slider_rotate_fine.setValue(0)
        self.spin_rotate_fine.setValue(0)
        
        self.slider_rotate_fine.blockSignals(False)
        self.spin_rotate_fine.blockSignals(False)

    def on_upscale_method_changed(self, method):
        is_waifu = method == "Waifu2x"
        self.lbl_upscale_noise.setEnabled(is_waifu)
        self.combo_upscale_noise.setEnabled(is_waifu)
        self.update_upscale_button_state()

    def update_upscale_button_state(self):
        method = self.combo_upscale_method.currentText()
        has_image = self.current_image_pil is not None

        # Denoise button (only for Waifu2x)
        self.btn_apply_denoise.setEnabled(has_image and WAIFU_AVAILABLE)
        
        if method == "Waifu2x":
            self.btn_apply_upscale.setEnabled(has_image and WAIFU_AVAILABLE)
            if not WAIFU_AVAILABLE:
                self.btn_apply_upscale.setToolTip(f"upscale2.exe não encontrado em:\n{WAIFU_EXE}")
                self.lbl_upscale_status.setText(f"⚠️ upscale2.exe não encontrado em:\n{WAIFU_EXE}")
            else:
                self.btn_apply_upscale.setToolTip("")
                self.lbl_upscale_status.setText("")
        elif method == "Real-ESRGAN":
            self.btn_apply_upscale.setEnabled(has_image and ESRGAN_AVAILABLE)
            if not ESRGAN_AVAILABLE:
                self.btn_apply_upscale.setToolTip("realesrgan ou basicsr/torch não instalados no Python.")
                self.lbl_upscale_status.setText("⚠️ realesrgan ou basicsr/torch não instalados no Python.")
            else:
                self.btn_apply_upscale.setToolTip("")
                self.lbl_upscale_status.setText("")

    def apply_denoise(self):
        """Aplica denoise na imagem atual usando waifu2x (upscale2.exe)"""
        if not self.current_image_pil:
            return

        if not WAIFU_AVAILABLE:
            QMessageBox.warning(self, "Waifu2x", f"upscale2.exe não encontrado em:\n{WAIFU_EXE}")
            return

        noise_level = self.combo_denoise_level.currentText()

        self.lbl_upscale_status.setText("⏳ Aplicando denoise...")
        self.btn_apply_denoise.setEnabled(False)
        QApplication.processEvents()

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                input_path = os.path.join(tmp_dir, "input.png")
                output_path = os.path.join(tmp_dir, "output.png")

                # Salva imagem atual para o arquivo temporário
                self.current_image_pil.save(input_path)

                cmd = [
                    WAIFU_EXE,
                    "-i", input_path,
                    "-o", output_path,
                    "-s", "1",
                    "-m", "noise",
                    "-n", noise_level,
                    "-p", "cpu"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)

                if os.path.isfile(output_path):
                    self.save_state()
                    result_img = Image.open(output_path).convert("RGBA")
                    self.current_image_pil = result_img
                    self.update_canvas_image()
                    self.lbl_upscale_status.setText(f"✅ Denoise (nível {noise_level}) aplicado!")
                else:
                    stderr = result.stderr.strip() if result.stderr else "Erro desconhecido"
                    self.lbl_upscale_status.setText(f"❌ Falha: {stderr[:100]}")
                    QMessageBox.critical(self, "Erro", f"upscale2.exe falhou:\n{stderr}")

        except Exception as e:
            self.lbl_upscale_status.setText(f"❌ Erro: {str(e)[:80]}")
            QMessageBox.critical(self, "Erro", str(e))
        finally:
            self.update_upscale_button_state()

    def apply_ai_upscale(self):
        """Aplica AI upscale na imagem atual"""
        if not self.current_image_pil:
            return

        method = self.combo_upscale_method.currentText()

        if method == "Waifu2x":
            if not WAIFU_AVAILABLE:
                QMessageBox.warning(self, "Waifu2x", f"upscale2.exe não encontrado em:\n{WAIFU_EXE}")
                return

            factor_text = self.combo_upscale_factor.currentText()  # "2x" ou "4x"
            factor = factor_text.replace("x", "")  # "2" ou "4"
            noise_level = self.combo_upscale_noise.currentText()
            keep_original = self.chk_keep_original_size.isChecked()
            original_size = self.current_image_pil.size

            self.lbl_upscale_status.setText(f"⏳ Aplicando upscale {factor_text}...")
            self.btn_apply_upscale.setEnabled(False)
            QApplication.processEvents()

            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    input_path = os.path.join(tmp_dir, "input.png")
                    output_path = os.path.join(tmp_dir, "output.png")

                    # Salva imagem atual
                    self.current_image_pil.save(input_path)

                    cmd = [
                        WAIFU_EXE,
                        "-i", input_path,
                        "-o", output_path,
                        "-s", factor,
                        "-m", "noise_scale",
                        "-n", noise_level,
                        "-p", "cpu"
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)

                    if os.path.isfile(output_path):
                        self.save_state()
                        result_img = Image.open(output_path).convert("RGBA")

                        if keep_original:
                            # Redimensiona de volta para o tamanho original
                            result_img = result_img.resize(original_size, Image.LANCZOS)
                            status_msg = f"✅ Upscale {factor_text} + volta para {original_size[0]}x{original_size[1]}"
                        else:
                            status_msg = f"✅ Upscale {factor_text} aplicado! Novo tamanho: {result_img.width}x{result_img.height}"

                        self.current_image_pil = result_img

                        # Atualiza os spinboxes de resize
                        self.spin_resize_width.blockSignals(True)
                        self.spin_resize_height.blockSignals(True)
                        self.spin_resize_width.setValue(result_img.width)
                        self.spin_resize_height.setValue(result_img.height)
                        self.spin_resize_width.blockSignals(False)
                        self.spin_resize_height.blockSignals(False)

                        self.update_canvas_image()
                        self.lbl_upscale_status.setText(status_msg)
                    else:
                        stderr = result.stderr.strip() if result.stderr else "Erro desconhecido"
                        self.lbl_upscale_status.setText(f"❌ Falha: {stderr[:100]}")
                        QMessageBox.critical(self, "Erro", f"upscale2.exe falhou:\n{stderr}")

            except Exception as e:
                self.lbl_upscale_status.setText(f"❌ Erro: {str(e)[:80]}")
                QMessageBox.critical(self, "Erro", str(e))
            finally:
                self.update_upscale_button_state()

        elif method == "Real-ESRGAN":
            if not ESRGAN_AVAILABLE:
                QMessageBox.warning(self, "Real-ESRGAN", "Real-ESRGAN não está disponível.")
                return

            factor_text = self.combo_upscale_factor.currentText()  # "2x" ou "4x"
            factor = int(factor_text.replace("x", ""))  # 2 ou 4
            keep_original = self.chk_keep_original_size.isChecked()
            original_size = self.current_image_pil.size

            self.lbl_upscale_status.setText(f"⏳ Aplicando Real-ESRGAN {factor_text}...")
            self.btn_apply_upscale.setEnabled(False)
            QApplication.processEvents()

            try:
                # 1. Preparar imagem
                img_rgba = self.current_image_pil.copy()
                alpha = img_rgba.split()[3] if len(img_rgba.split()) == 4 else None
                rgb_img = img_rgba.convert("RGB")

                # Converter para array BGR numpy
                img_np = np.array(rgb_img)
                img_bgr = img_np[:, :, ::-1]

                # 2. Configurar o upsampler
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                model_path = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"

                upsampler = RealESRGANer(
                    scale=4,
                    model_path=model_path,
                    model=model,
                    tile=0,
                    tile_pad=10,
                    pre_pad=0,
                    half=False,
                    device=device
                )

                # 3. Executar o upscale
                output_bgr, _ = upsampler.enhance(img_bgr, outscale=factor)

                # 4. Reconstrutor de imagem RGBA
                output_rgb_np = output_bgr[:, :, ::-1]
                output_rgb_pil = Image.fromarray(output_rgb_np)

                if alpha:
                    new_w, new_h = output_rgb_pil.size
                    alpha_resized = alpha.resize((new_w, new_h), Image.Resampling.NEAREST)
                    result_img = Image.merge("RGBA", (*output_rgb_pil.split(), alpha_resized))
                else:
                    result_img = output_rgb_pil.convert("RGBA")

                self.save_state()

                if keep_original:
                    result_img = result_img.resize(original_size, Image.Resampling.LANCZOS)
                    status_msg = f"✅ Real-ESRGAN {factor_text} + volta para {original_size[0]}x{original_size[1]}"
                else:
                    status_msg = f"✅ Real-ESRGAN {factor_text} aplicado! Novo tamanho: {result_img.width}x{result_img.height}"

                self.current_image_pil = result_img

                # Atualiza os spinboxes de resize
                self.spin_resize_width.blockSignals(True)
                self.spin_resize_height.blockSignals(True)
                self.spin_resize_width.setValue(result_img.width)
                self.spin_resize_height.setValue(result_img.height)
                self.spin_resize_width.blockSignals(False)
                self.spin_resize_height.blockSignals(False)

                self.update_canvas_image()
                self.lbl_upscale_status.setText(status_msg)

            except Exception as e:
                self.lbl_upscale_status.setText(f"❌ Erro: {str(e)[:80]}")
                QMessageBox.critical(self, "Erro", str(e))
            finally:
                self.update_upscale_button_state()



if __name__ == "__main__":
    import sys

    try:
        app = QApplication(sys.argv)
        window = SliceWindow()
        window.show()
        window.showMaximized()
        sys.exit(app.exec())
    except Exception as e:
        print(f"❌ ERRO FATAL: {e}")
        import traceback

        traceback.print_exc()
        input("Pressione ENTER para fechar...")
