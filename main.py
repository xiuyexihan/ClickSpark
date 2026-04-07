"""
ClickSpark - 鼠标点击特效应用
依赖安装: pip install PyQt6 pynput pywin32
打包命令: pyinstaller --noconsole --onefile --icon=icon.ico main.py
"""

import sys
import json
import os
import random
import math
import winreg
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QColorDialog, QComboBox, QCheckBox, QSpinBox,
    QGroupBox, QTabWidget, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QFrame
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QPointF, QPropertyAnimation,
    QEasingCurve, pyqtSignal, QThread, QObject, QRect, QRectF  # <--- 在这里加上 QRectF
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QIcon, QPixmap,
    QPen, QBrush, QRadialGradient, QLinearGradient,
    QAction, QPainterPath, QConicalGradient  # <--- 在这里添加 QConicalGradient
)
from pynput import mouse as pynput_mouse

# ────────────────────────────────────────────
#  配置管理
# ────────────────────────────────────────────
CONFIG_PATH = Path(os.getenv("APPDATA")) / "ClickSpark" / "config.json"

DEFAULT_CONFIG = {
    "effect": "particle",          # particle / spark / ripple / emoji / text / firework
    "color_mode": "random",        # random / fixed / rainbow
    "fixed_color": "#FF6B6B",
    "size": 40,
    "count": 12,
    "duration": 800,
    "opacity": 90,
    "emoji_list": ["✨", "💥", "⭐", "🔥", "💫", "🎉"],
    "text_list": ["哇!", "棒!", "Nice!", "666", "Click!"],
    "blacklist": [],               # 进程黑名单
    "hotkey_toggle": "ctrl+alt+s",
    "enabled": True,
    "auto_start": False,
    "multi_monitor": True,
    "fullscreen_pause": True,
}

def load_config():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = {**DEFAULT_CONFIG, **json.load(f)}
                return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ────────────────────────────────────────────
#  开机启动管理
# ────────────────────────────────────────────
APP_NAME = "ClickSpark"
EXE_PATH = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)

def set_autostart(enable: bool):
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE
    )
    if enable:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{EXE_PATH}"')
    else:
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)

def get_autostart() -> bool:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False

# ────────────────────────────────────────────
#  特效粒子单元
# ────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color, effect_type, config):
        self.x = x
        self.y = y
        self.color = color
        self.effect = effect_type
        self.cfg = config
        
        self.life = 1.0
        self.rotation = random.uniform(0, 360)
        self.rot_speed = random.uniform(-3, 3)

        # ── 关键修复：定义 base_size ──
        # 从配置中读取 size，如果没有则默认 40
        self.base_size = self.cfg.get("size", 40) 

        if self.effect == "halo":
            self.decay = 0.04 
            self.extra_stars = []
            # 这里的星星大小也要基于 base_size 缩放
            scale = self.base_size / 40.0
            for _ in range(random.randint(3, 6)):
                self.extra_stars.append({
                    "angle": random.uniform(0, 360),
                    "dist_ratio": random.uniform(0.8, 1.2),
                    "size_base": random.uniform(8, 14) * scale,
                    "life_off": random.uniform(0.0, 0.2),
                })
        else:
            self.decay = random.uniform(0.015, 0.03)
            # 粒子的扩散速度也可以根据 base_size 稍微调整
            speed_scale = self.base_size / 20.0
            self.vx = random.uniform(-2, 2) * speed_scale
            self.vy = random.uniform(-2, 2) * speed_scale

        # 针对特殊特效的额外初始化
        if self.effect == "emoji":
            emojis = self.cfg.get("emojis", ["✨", "⭐", "🌟", "🔥"])
            self.emoji = random.choice(emojis)
        elif self.effect == "text":
            texts = self.cfg.get("texts", ["+1", "Click!", "Spark"])
            self.text = random.choice(texts)
    @property
    def alive(self):
        return self.life > 0

    def update(self):
        self.life -= self.decay
        
        # 💡 核心修复：如果是 halo 特效，不应用位移，让它留在原地
        if self.effect != "halo":
            self.x += self.vx
            self.y += self.vy
            
        self.rotation += self.rot_speed

    def draw(self, painter):
        if not self.alive: return
        cx, cy = self.x, self.y
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 获取基础颜色和透明度设置
        c = QColor(self.color)
        global_opacity = self.cfg.get("opacity", 100) / 100.0
        # 基础 alpha 计算：生命值 * 设置透明度
        base_alpha = int(self.life * 255 * global_opacity)
        c.setAlpha(base_alpha)

        # ── 1. 基础粒子效果 ──
        if self.effect == "particle":
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.PenStyle.NoPen)
            # 使用 self.base_size 确保受控
            s = (self.base_size / 10.0) * self.life 
            painter.drawEllipse(QPointF(cx, cy), s, s)

        # ── 2. 火花效果 (调用刚才定义的内凹星，但角更锐利) ──
        elif self.effect == "spark":
            s = self.base_size * self.life * 0.5
            self._draw_concave_star(painter, cx, cy, s, base_alpha, c)

        # ── 3. 涟漪扩散 ──
        elif self.effect == "ripple":
            # 线条随消失变细
            pen = QPen(c, max(1, int(3 * self.life)))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # 半径从中心向外扩张
            r = int(self.base_size * (1 - self.life) * 1.5)
            painter.drawEllipse(QPointF(cx, cy), r, r)

        # ── 4. Emoji 飞溅 ──
        elif self.effect == "emoji":
            painter.setOpacity(self.life * global_opacity)
            # 字体大小随 life 缩放
            font_size = max(6, int(self.base_size * 0.8 * self.life))
            painter.setFont(QFont("Segoe UI Emoji", font_size))
            # 这里的 self.emoji 需要在 __init__ 中获取
            emoji_text = getattr(self, 'emoji', "✨")
            painter.drawText(
                QRectF(cx - 50, cy - 50, 100, 100),
                Qt.AlignmentFlag.AlignCenter,
                emoji_text
            )

        # ── 5. 文字弹出 ──
        elif self.effect == "text":
            painter.setOpacity(self.life * global_opacity)
            font = QFont("微软雅黑", max(6, int(self.base_size * 0.5)))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(c))
            # 这里的 self.text 需要在 __init__ 中获取
            display_text = getattr(self, 'text', "+1")
            painter.drawText(
                QRectF(cx - 100, cy - 50, 200, 100),
                Qt.AlignmentFlag.AlignCenter,
                display_text
            )

        # ── 6. 烟花 (八角星) ──
        elif self.effect == "firework":
            painter.translate(cx, cy)
            painter.rotate(self.rotation)
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.PenStyle.NoPen)
            # 这里的 s 使用 self.base_size
            s = max(1, int(self.base_size * self.life * 0.4))
            from PyQt6.QtGui import QPolygon
            pts = [
                QPoint(0, -s), QPoint(int(s*0.3), int(-s*0.3)),
                QPoint(s, 0),  QPoint(int(s*0.3), int(s*0.3)),
                QPoint(0, s),  QPoint(int(-s*0.3), int(s*0.3)),
                QPoint(-s, 0), QPoint(int(-s*0.3), int(-s*0.3)),
            ]
            painter.drawPolygon(QPolygon(pts))

        # 7. 重点：光环效果 (根据 image_0.png 深度还原)
        elif self.effect == "halo":
            # 光环大小完全由设置面板中的 size 决定
            current_base = self.base_size * 0.6
            smooth_alpha = self.life * self.life 

            if self.life > 0.8:
                t = (1.0 - self.life) / 0.2
                r = current_base * 0.3 * (1.2 - t)
                self._draw_soft_ring(painter, cx, cy, r, int(150 * t), r * 0.5)
                self._draw_concave_star(painter, cx, cy, current_base * 0.5 * t, int(255 * t), QColor(255, 255, 255))
            else:
                t = (0.8 - self.life) / 0.8
                r = current_base * (0.2 + 0.9 * (1.0 - math.exp(-t * 8)))
                
                # 环的厚度和颜色受设置影响
                ring_op = int(210 * (self.life ** 1.5))
                self._draw_soft_ring(painter, cx, cy, r, ring_op, r * 0.8)

                for s in self.extra_stars:
                    star_life = self.life + s["life_off"]
                    if star_life <= 0: continue
                    s_alpha = int(255 * (min(1.0, star_life) ** 0.8))
                    angle_rad = math.radians(s["angle"])
                    dist = r * s["dist_ratio"]
                    sx = cx + dist * math.cos(angle_rad)
                    sy = cy + dist * math.sin(angle_rad)
                    # 星星颜色如果是随机模式，会更有趣，这里先保持高亮
                    self._draw_concave_star(painter, sx, sy, s["size_base"] * min(1.0, star_life * 2), s_alpha, QColor(200, 240, 255))

        painter.restore()

    def _draw_concave_star(self, painter, cx, cy, size, alpha, color):
        if alpha <= 0 or size < 1: return
        def get_star_path(s):
            path = QPainterPath()
            pts = [(cx, cy-s), (cx+s, cy), (cx, cy+s), (cx-s, cy)]
            path.moveTo(pts[0][0], pts[0][1])
            for i in range(1, 4): path.quadTo(cx, cy, pts[i][0], pts[i][1])
            path.quadTo(cx, cy, pts[0][0], pts[0][1])
            return path
        painter.save()
        c = QColor(color)
        c.setAlpha(int(alpha * 0.5))
        painter.setBrush(QBrush(c))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(get_star_path(size * 1.1))
        painter.setBrush(QBrush(QColor(255, 255, 255, int(alpha))))
        painter.drawPath(get_star_path(size * 0.6))
        painter.restore()

    def _draw_soft_ring(self, painter, cx, cy, radius, opacity, width):
        if opacity <= 0 or radius < 1: return
        painter.save()
        fade_color = QColor(255, 255, 255, int(opacity * 0.2))
        painter.setPen(QPen(fade_color, float(width * 1.4), Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        
        gradient = QConicalGradient(QPointF(cx, cy), 90)
        for i in range(0, 11):
            # 这里可以根据 self.color 做一点点色彩混合，让环的颜色也受设置影响
            color = QColor.fromHsv(int((i/10.0)*359), 130, 255, int(opacity * 0.8))
            gradient.setColorAt(i/10.0, color)
            
        painter.setPen(QPen(QBrush(gradient), float(width), Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        painter.restore()
# ────────────────────────────────────────────
#  特效覆盖窗口（单屏版，每块屏幕独立一个）
# ────────────────────────────────────────────
class EffectOverlay(QWidget):
    """覆盖单块屏幕的透明特效层。每块屏幕各一个实例，彻底消除跨屏竖线。"""

    def __init__(self, screen):
        super().__init__()
        self.particles: list[Particle] = []
        self.config = load_config()
        self._rainbow_hue = 0
        self._screen = screen

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 覆盖该屏幕的物理区域
        self._fit_to_screen()
        screen.geometryChanged.connect(self._fit_to_screen)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.setInterval(16)

    def _fit_to_screen(self):
        geo  = self._screen.geometry()
        dpr  = self._screen.devicePixelRatio()   # 缩放比，如125%→1.25
        self.setGeometry(geo)                    # Qt窗口用逻辑像素
        self._dpr      = dpr
        # geo.x/y() 是虚拟桌面中该屏幕左上角坐标（主屏DPR=1时等于物理坐标）
        # 用 物理宽/高 = 逻辑宽/高 × DPR 计算物理边界，与pynput物理坐标匹配
        self._phys_x = geo.x()
        self._phys_y = geo.y()
        self._phys_w = int(geo.width()  * dpr)
        self._phys_h = int(geo.height() * dpr)

    def reload_config(self):
        self.config = load_config()

    def try_spawn(self, gx: int, gy: int):
        """如果全局坐标落在本屏幕范围内，则生成特效；否则忽略。"""
        if not self.config.get("enabled", True):
            return
        # 用物理像素边界判断（pynput返回物理坐标）
        if not (self._phys_x <= gx < self._phys_x + self._phys_w and
                self._phys_y <= gy < self._phys_y + self._phys_h):
            return
        # 物理坐标 → 窗口本地逻辑坐标（除以DPR，与Qt窗口尺寸对应）
        lx = int((gx - self._phys_x) / self._dpr)
        ly = int((gy - self._phys_y) / self._dpr)

        effect = self.config.get("effect", "particle")
        count  = self.config.get("count", 12)
        single = {"ripple", "halo"}

        for _ in range(count):
            p = Particle(lx, ly, self._pick_color(), effect, self.config)
            self.particles.append(p)
            if effect in single:
                break

        if not self.timer.isActive():
            self.timer.start()

    def _pick_color(self) -> str:
        mode = self.config.get("color_mode", "random")
        if mode == "fixed":
            return self.config.get("fixed_color", "#FF6B6B")
        elif mode == "rainbow":
            self._rainbow_hue = (self._rainbow_hue + 15) % 360
            return QColor.fromHsv(self._rainbow_hue, 255, 255).name()
        else:
            return QColor.fromHsv(random.randint(0, 359), 220, 255).name()

    def _tick(self):
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.alive]
        self.update()
        if not self.particles:
            self.timer.stop()

    def paintEvent(self, event):
        if not self.particles:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for p in self.particles:
            p.draw(painter)
        painter.end()


# ────────────────────────────────────────────
#  全局鼠标监听线程
# ────────────────────────────────────────────
class MouseSignalEmitter(QObject):
    clicked = pyqtSignal(int, int)

class MouseListenerThread(QThread):
    def __init__(self, emitter: MouseSignalEmitter):
        super().__init__()
        self.emitter = emitter
        self._listener = None

    def run(self):
        def on_click(x, y, button, pressed):
            if pressed and button == pynput_mouse.Button.left:
                self.emitter.clicked.emit(int(x), int(y))
        self._listener = pynput_mouse.Listener(on_click=on_click)
        self._listener.start()
        self._listener.join()

    def stop(self):
        if self._listener:
            self._listener.stop()

# ────────────────────────────────────────────
#  设置对话框
# ────────────────────────────────────────────
class SettingsDialog(QDialog):
    config_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = load_config()
        self.setWindowTitle("ClickSpark 设置")
        self.setMinimumSize(520, 580)
        self.setStyleSheet(STYLE_SHEET)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._tab_effect(), "✨ 特效")
        tabs.addTab(self._tab_color(),  "🎨 颜色")
        tabs.addTab(self._tab_advanced(), "⚙️ 高级")
        layout.addWidget(tabs)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_save   = QPushButton("保存")
        btn_cancel = QPushButton("取消")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._save)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    # ── 特效标签页 ──
    def _tab_effect(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(14)

        # 特效类型
        row = QHBoxLayout()
        row.addWidget(QLabel("特效类型"))
        self.combo_effect = QComboBox()
        for k, label in [
            ("particle", "粒子爆炸"),
            ("spark",    "火花拖尾"),
            ("ripple",   "涟漪扩散"),
            ("halo",     "光环 ✦"),
            ("emoji",    "Emoji 飞溅"),
            ("text",     "文字弹出"),
            ("firework", "烟花"),
        ]:
            self.combo_effect.addItem(label, k)
        idx = [self.combo_effect.itemData(i) for i in range(self.combo_effect.count())].index(self.cfg.get("effect","particle"))
        self.combo_effect.setCurrentIndex(idx)
        row.addWidget(self.combo_effect)
        v.addLayout(row)

        # 粒子数量
        v.addWidget(self._slider_row("粒子数量", "count", 4, 40, self.cfg["count"]))
        # 特效大小
        v.addWidget(self._slider_row("特效大小", "size",  10, 100, self.cfg["size"]))
        # 持续时间
        v.addWidget(self._slider_row("持续时间(ms)", "duration", 200, 2000, self.cfg["duration"], step=50))
        # 透明度
        v.addWidget(self._slider_row("透明度", "opacity", 10, 100, self.cfg["opacity"]))

        # Emoji 列表
        g = QGroupBox("Emoji 列表（空格分隔）")
        gl = QVBoxLayout(g)
        from PyQt6.QtWidgets import QLineEdit
        self.edit_emoji = QLineEdit(" ".join(self.cfg.get("emoji_list", [])))
        gl.addWidget(self.edit_emoji)
        v.addWidget(g)

        # 文字列表
        g2 = QGroupBox("弹出文字（空格分隔）")
        gl2 = QVBoxLayout(g2)
        self.edit_text = QLineEdit(" ".join(self.cfg.get("text_list", [])))
        gl2.addWidget(self.edit_text)
        v.addWidget(g2)

        v.addStretch()
        return w

    def _slider_row(self, label, key, mn, mx, val, step=1):
        frame = QFrame()
        h = QHBoxLayout(frame)
        h.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFixedWidth(130)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(mn, mx)
        slider.setSingleStep(step)
        slider.setValue(val)
        val_lbl = QLabel(str(val))
        val_lbl.setFixedWidth(40)
        slider.valueChanged.connect(lambda v: val_lbl.setText(str(v)))
        slider.setProperty("cfg_key", key)
        h.addWidget(lbl)
        h.addWidget(slider)
        h.addWidget(val_lbl)
        if not hasattr(self, "_sliders"):
            self._sliders = []
        self._sliders.append(slider)
        return frame

    # ── 颜色标签页 ──
    def _tab_color(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(14)

        row = QHBoxLayout()
        row.addWidget(QLabel("颜色模式"))
        self.combo_color = QComboBox()
        for k, l in [("random","随机颜色"),("fixed","固定颜色"),("rainbow","彩虹渐变")]:
            self.combo_color.addItem(l, k)
        idx2 = [self.combo_color.itemData(i) for i in range(self.combo_color.count())].index(self.cfg.get("color_mode","random"))
        self.combo_color.setCurrentIndex(idx2)
        row.addWidget(self.combo_color)
        v.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("固定颜色"))
        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(80, 30)
        self._set_btn_color(self.cfg.get("fixed_color","#FF6B6B"))
        self.btn_color.clicked.connect(self._pick_color)
        row2.addWidget(self.btn_color)
        row2.addStretch()
        v.addLayout(row2)

        v.addStretch()
        return w

    def _set_btn_color(self, hex_color):
        self._fixed_color = hex_color
        self.btn_color.setStyleSheet(f"background:{hex_color};border-radius:4px;")

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._fixed_color), self)
        if c.isValid():
            self._set_btn_color(c.name())

    # ── 高级标签页 ──
    def _tab_advanced(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(14)

        self.chk_autostart = QCheckBox("开机自动启动")
        self.chk_autostart.setChecked(get_autostart())
        v.addWidget(self.chk_autostart)

        self.chk_multimon = QCheckBox("多显示器支持")
        self.chk_multimon.setChecked(self.cfg.get("multi_monitor", True))
        v.addWidget(self.chk_multimon)

        self.chk_fullscreen = QCheckBox("全屏时自动暂停特效")
        self.chk_fullscreen.setChecked(self.cfg.get("fullscreen_pause", True))
        v.addWidget(self.chk_fullscreen)

        # 导入/导出
        row = QHBoxLayout()
        btn_export = QPushButton("📤 导出配置")
        btn_import = QPushButton("📥 导入配置")
        btn_export.clicked.connect(self._export)
        btn_import.clicked.connect(self._import)
        row.addWidget(btn_export)
        row.addWidget(btn_import)
        row.addStretch()
        v.addLayout(row)

        v.addStretch()
        return w

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出配置", "clickspark_config.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "成功", "配置已导出！")

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "JSON (*.json)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                imported = json.load(f)
            self.cfg.update(imported)
            QMessageBox.information(self, "成功", "配置已导入，请重新打开设置生效。")

    def _save(self):
        # 读取所有滑块
        for s in getattr(self, "_sliders", []):
            key = s.property("cfg_key")
            if key:
                self.cfg[key] = s.value()

        self.cfg["effect"]      = self.combo_effect.currentData()
        self.cfg["color_mode"]  = self.combo_color.currentData()
        self.cfg["fixed_color"] = self._fixed_color
        self.cfg["multi_monitor"]   = self.chk_multimon.isChecked()
        self.cfg["fullscreen_pause"] = self.chk_fullscreen.isChecked()

        raw_emoji = self.edit_emoji.text().strip().split()
        if raw_emoji:
            self.cfg["emoji_list"] = raw_emoji
        raw_text = self.edit_text.text().strip().split()
        if raw_text:
            self.cfg["text_list"] = raw_text

        save_config(self.cfg)
        set_autostart(self.chk_autostart.isChecked())
        self.config_changed.emit()
        self.accept()

# ────────────────────────────────────────────
#  样式表
# ────────────────────────────────────────────
STYLE_SHEET = """
QDialog, QWidget {
    background: #1a1a2e;
    color: #e0e0e0;
    font-family: '微软雅黑', sans-serif;
    font-size: 13px;
}
QTabWidget::pane { border: 1px solid #333; border-radius: 6px; }
QTabBar::tab {
    background: #16213e; color: #aaa;
    padding: 8px 18px; margin-right: 2px;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #0f3460; color: #fff; }
QComboBox, QLineEdit, QSpinBox {
    background: #16213e; border: 1px solid #444;
    border-radius: 5px; padding: 4px 8px; color: #eee;
}
QComboBox::drop-down { border: none; }
QSlider::groove:horizontal {
    height: 6px; background: #333; border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 14px; height: 14px;
    background: #e94560; border-radius: 7px;
    margin: -4px 0;
}
QSlider::sub-page:horizontal { background: #e94560; border-radius: 3px; }
QPushButton {
    background: #16213e; border: 1px solid #555;
    border-radius: 6px; padding: 6px 16px; color: #ddd;
}
QPushButton:hover { background: #0f3460; border-color: #e94560; }
QPushButton#btnPrimary {
    background: #e94560; border: none; color: white; font-weight: bold;
}
QPushButton#btnPrimary:hover { background: #c73652; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 2px solid #555; border-radius: 4px; background: #16213e;
}
QCheckBox::indicator:checked { background: #e94560; border-color: #e94560; }
QGroupBox {
    border: 1px solid #333; border-radius: 6px;
    margin-top: 10px; padding-top: 8px;
    font-weight: bold; color: #aaa;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; }
"""

# ────────────────────────────────────────────
#  系统托盘图标（程序化生成）
# ────────────────────────────────────────────
def make_tray_icon(enabled: bool) -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 背景圆
    grad = QRadialGradient(32, 32, 32)
    if enabled:
        grad.setColorAt(0, QColor("#e94560"))
        grad.setColorAt(1, QColor("#c73652"))
    else:
        grad.setColorAt(0, QColor("#555"))
        grad.setColorAt(1, QColor("#333"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(4, 4, 56, 56)

    # 闪光射线
    p.setPen(QPen(QColor(255, 255, 255, 200 if enabled else 80), 3,
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = 32 + 18 * math.cos(rad)
        y1 = 32 + 18 * math.sin(rad)
        x2 = 32 + 26 * math.cos(rad)
        y2 = 32 + 26 * math.sin(rad)
        p.drawLine(int(x1), int(y1), int(x2), int(y2))

    # 中心星
    p.setBrush(QBrush(QColor(255, 255, 255, 230 if enabled else 100)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(26, 26, 12, 12)

    p.end()
    return QIcon(pix)

# ────────────────────────────────────────────
#  主应用
# ────────────────────────────────────────────
class ClickSparkApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # 每块屏幕一个独立 overlay，彻底消除跨屏竖线
        self.overlays: list[EffectOverlay] = []
        self._build_overlays()

        # 监听屏幕增减，动态更新 overlay 列表
        self.app.screenAdded.connect(self._on_screen_added)
        self.app.screenRemoved.connect(self._on_screen_removed)

        # 鼠标监听：点击时广播给所有 overlay，各自判断是否在本屏范围内
        self.emitter = MouseSignalEmitter()
        self.emitter.clicked.connect(self._dispatch_click)
        self.listener = MouseListenerThread(self.emitter)
        self.listener.start()

        self._settings_dlg: SettingsDialog | None = None
        self._setup_tray()

    def _setup_tray(self):
        # 1. 初始化托盘（不传 self 避免类型错误）
        self.tray = QSystemTrayIcon() 
        self.tray.setIcon(make_tray_icon(True))
        self.tray.setToolTip("ClickSpark — 魔法星环")

        # 2. 创建菜单，必须存为 self 属性防止被回收
        self.tray_menu = QMenu()

        # --- 暂停/启用 ---
        self.act_toggle = QAction("⏸ 暂停特效", self.tray_menu)
        self.act_toggle.triggered.connect(self._toggle)
        self.tray_menu.addAction(self.act_toggle)

        self.tray_menu.addSeparator()

        # --- 快捷切换特效子菜单 ---
        effect_menu = self.tray_menu.addMenu("✨ 切换特效")
        effect_list = [
            ("particle", "粒子爆炸"),
            ("spark",    "火花拖尾"),
            ("ripple",   "涟漪扩散"),
            ("halo",     "光环 ✦"),
            ("emoji",    "Emoji"),
            ("text",     "文字弹出"),
            ("firework", "烟花"),
        ]

        for k, l in effect_list:
            action = QAction(l, effect_menu)
            # 使用默认参数 k=k 解决 lambda 闭包陷阱
            action.triggered.connect(lambda _, key=k: self._quick_switch(key))
            effect_menu.addAction(action)

        self.tray_menu.addSeparator()

        # --- 设置中心 ---
        act_settings = QAction("⚙️ 设置中心", self.tray_menu)
        act_settings.triggered.connect(self._open_settings)
        self.tray_menu.addAction(act_settings)

        self.tray_menu.addSeparator()

        # --- 退出程序（这就找回来了！） ---
        act_quit = QAction("❌ 退出程序", self.tray_menu)
        act_quit.triggered.connect(self._quit)
        self.tray_menu.addAction(act_quit)

        # 3. 关联菜单、绑定激活事件并显示
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _toggle(self):
        """切换特效的开启与暂停"""
        cfg = load_config()
        # 切换布尔值
        cfg["enabled"] = not cfg.get("enabled", True)
        save_config(cfg)
        
        # 通知所有渲染窗口重载配置
        for ov in self.overlays: 
            ov.reload_config()
            
        enabled = cfg["enabled"]
        # 更新托盘图标（变灰或彩色）
        self.tray.setIcon(make_tray_icon(enabled))
        # 更新菜单文字
        self.act_toggle.setText("▶ 启用特效" if not enabled else "⏸ 暂停特效")
        
        # 弹个气泡提示一下
        status_text = "特效已启用 ✨" if enabled else "特效已暂停 ⏸"
        self.tray.showMessage("ClickSpark", status_text, QSystemTrayIcon.MessageIcon.Information, 1000)

    def _build_overlays(self):
        for screen in QApplication.screens():
            ov = EffectOverlay(screen)
            ov.show()
            self.overlays.append(ov)

    def _on_screen_added(self, screen):
        ov = EffectOverlay(screen)
        ov.show()
        self.overlays.append(ov)

    def _on_screen_removed(self, screen):
        self.overlays = [ov for ov in self.overlays if ov._screen != screen]

    def _dispatch_click(self, gx: int, gy: int):
        for ov in self.overlays:
            ov.try_spawn(gx, gy)

    def _on_tray_activated(self, reason):
        """处理托盘点击事件：双击打开设置"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_settings()

    def _toggle(self):
        """切换特效开启/关闭状态"""
        cfg = load_config()
        cfg["enabled"] = not cfg.get("enabled", True)
        save_config(cfg)
        
        # 通知所有窗口重载
        for ov in self.overlays: 
            ov.reload_config()
            
        enabled = cfg["enabled"]
        self.tray.setIcon(make_tray_icon(enabled))
        self.act_toggle.setText("⏸ 暂停特效" if enabled else "▶ 启用特效")
        
        status = "已启用 ✨" if enabled else "已暂停 ⏸"
        self.tray.showMessage("ClickSpark", f"特效{status}", QSystemTrayIcon.MessageIcon.Information, 1000)

    def _quick_switch(self, effect_key):
        """快速切换特效模式"""
        cfg = load_config()
        cfg["effect"] = effect_key
        save_config(cfg)
        
        for ov in self.overlays:
            ov.reload_config()
            
        self.tray.showMessage("特效切换", f"当前模式: {effect_key}", QSystemTrayIcon.MessageIcon.Information, 800)

    def _open_settings(self):
        """打开设置对话框"""
        # 检查是否已有实例在运行
        if hasattr(self, '_settings_dlg') and self._settings_dlg is not None:
            if self._settings_dlg.isVisible():
                self._settings_dlg.raise_()
                self._settings_dlg.activateWindow()
                return

        self._settings_dlg = SettingsDialog()
        # 绑定实时预览
        for ov in self.overlays:
            self._settings_dlg.config_changed.connect(ov.reload_config)
            
        self._settings_dlg.exec() # 模态运行
        self._settings_dlg = None

    def _quit(self):
        """安全退出程序"""
        if hasattr(self, 'listener'):
            self.listener.stop()
        self.tray.hide()
        self.app.quit()
        sys.exit(0)

    def _open_settings(self):
        # 检查窗口是否已存在
        if self._settings_dlg is not None and self._settings_dlg.isVisible():
            self._settings_dlg.raise_()
            self._settings_dlg.activateWindow()
            return
        
        self._settings_dlg = SettingsDialog()
        
        # 修正：遍历 overlays 列表进行 reload_config 绑定
        for ov in self.overlays:
            self._settings_dlg.config_changed.connect(ov.reload_config)
            
        self._settings_dlg.exec()
        self._settings_dlg = None

    def _quit(self):
        self.listener.stop()
        self.tray.hide()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())


if __name__ == "__main__":
    # ── 竖线/多屏修复：用 Windows 原生 API 设置 Per-Monitor DPI 感知 ──
    # 必须在任何窗口创建之前调用，告诉系统"我自己处理每块屏幕的 DPI"
    # 这样 Windows 合成器不会在 DPI 边界处插入缩放层，竖线自然消失。
    # 关键：完全不修改 Qt 的坐标系，pynput 和 Qt 都继续使用物理像素，坐标一致。
    try:
        import ctypes
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4（Windows 10 1703+）
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
    except Exception:
        try:
            # 降级方案：Per-Monitor Aware V1（Windows 8.1+）
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass  # 更老的系统跳过，不影响运行

    ClickSparkApp().run()
