import sys
import os
import random
import time
from PyQt5.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QGuiApplication, QTransform
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMainWindow  # Add QMainWindow here


KITTEN_IMAGE_PATH = r"C:\Users\livad\Fisiere_coding\Pawse\Kitties"

app = QApplication(sys.argv)
screens = QGuiApplication.screens()
if not screens:
    raise RuntimeError("No screens found.")

screen_rects = [s.geometry() for s in screens]
WINDOW_LEFT = min(r.left() for r in screen_rects)
WINDOW_TOP = min(r.top() for r in screen_rects)
WINDOW_RIGHT = max(r.right() for r in screen_rects)
WINDOW_BOTTOM = max(r.bottom() for r in screen_rects)
WINDOW_WIDTH = WINDOW_RIGHT - WINDOW_LEFT
WINDOW_HEIGHT = WINDOW_BOTTOM - WINDOW_TOP

FPS = 60
SPAWN_INTERVAL_MS = 170
KITTEN_SPEED = 5
KITTEN_MAX_DIMENSION = 220
STABILITY_THRESHOLD_X = 80
SLIDE_HORIZONTAL_SPEED = 5
SPAWN_COLUMNS = 2
COLUMN_WIDTH = WINDOW_WIDTH // SPAWN_COLUMNS
TOP_THRESHOLD = 5
STEP_SIZE = 1
COLLISION_BUFFER = 1  # Prevents tiny visual overlap


# --- Pre-fall Phase: Spawns 2–3 warning kittens over 10s ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(WINDOW_LEFT, WINDOW_TOP, WINDOW_WIDTH, WINDOW_HEIGHT)

        self.warning_kitten_count = 0
        self.labels = []

        for screen in QGuiApplication.screens():
            screen_geom = screen.geometry()
            label = QLabel("Break time in 1 minute...", self)
            label.setStyleSheet(
                "color: white; font-size: 30px; background-color: rgba(0,0,0,0.5); padding: 20px; border-radius: 10px;"
            )
            label.adjustSize()
            label_x = screen_geom.left() - WINDOW_LEFT + (screen_geom.width() - label.width()) // 2
            label_y = screen_geom.top() - WINDOW_TOP + (screen_geom.height() - label.height()) // 2
            label.move(label_x, label_y)
            label.show()
            self.labels.append(label)

        self.overlay = TransparentOverlay(self)
        self.overlay.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.overlay.show()
        self.overlay.spawn_timer.stop()

        # ⏱️ Setup timer for spawning next warning kittens
        self.warning_spawn_timer = QTimer()
        self.warning_spawn_timer.timeout.connect(self.spawn_warning_kitten)
        self.warning_spawn_timer.start(0)

        # 🐱 Immediately spawn the first warning kitten
        self.spawn_warning_kitten()

        # ⏲️ Start main fall after 10 seconds
        self.warning_timer = QTimer()
        self.warning_timer.setSingleShot(True)
        self.warning_timer.timeout.connect(self.start_main_kitten_fall)
        self.warning_timer.start(60000)

    def spawn_warning_kitten(self):
        if self.warning_kitten_count < 3:
            self.overlay.spawn_kitten(single=True)
            self.warning_kitten_count += 1
        else:
            self.warning_spawn_timer.stop()

    def start_main_kitten_fall(self):
        for label in self.labels:
            label.hide()
        self.overlay.spawn_timer.start(SPAWN_INTERVAL_MS)


class Kitten:
    def __init__(self, x, y, image):
        self.rotation = random.randint(-90, 90)
        self.original_pixmap = image
        self.pixmap = image.transformed(QTransform().rotate(self.rotation), Qt.SmoothTransformation)
        self.rect = QRectF(x, y, self.pixmap.width(), self.pixmap.height())
        self.speed_y = KITTEN_SPEED + random.uniform(-1, 1)
        self.speed_x = random.uniform(-1, 1)
        self.is_falling = True
        self.freeze_motion = False

    def update(self, stacked_kittens):
        if self.freeze_motion or not self.is_falling:
            return

        for _ in range(int(self.speed_y)):
            # Try to fall step-by-step
            self.rect.translate(0, STEP_SIZE)

            # Screen bottom
            if self.rect.bottom() >= WINDOW_HEIGHT:
                self.rect.moveBottom(WINDOW_HEIGHT)
                self.speed_x = 0
                self.is_falling = False
                return

            # Mid-air collision detection
            collided = None
            for other in stacked_kittens:
                if not other.is_falling:
                    vertical_overlap = self.rect.bottom() - other.rect.top()
                    horizontal_overlap = (
                        self.rect.right() > other.rect.left() and
                        self.rect.left() < other.rect.right()
                    )
                    if 0 < vertical_overlap <= STEP_SIZE and horizontal_overlap:
                        collided = other
                        break

            if collided:
                # Snap to top of collided kitten
                self.rect.moveBottom(collided.rect.top() - COLLISION_BUFFER)
                offset_x = self.rect.center().x() - collided.rect.center().x()

                if abs(offset_x) > STABILITY_THRESHOLD_X:
                    self.speed_x = SLIDE_HORIZONTAL_SPEED if offset_x > 0 else -SLIDE_HORIZONTAL_SPEED
                    self.is_falling = True
                else:
                    self.speed_x = 0
                    self.is_falling = False
                return

        # Apply horizontal motion (if still falling)
        self.rect.translate(self.speed_x, 0)

        # Bounce left/right
        if self.rect.left() <= 0:
            self.rect.moveLeft(0)
            self.speed_x *= -1
        elif self.rect.right() >= WINDOW_WIDTH:
            self.rect.moveRight(WINDOW_WIDTH)
            self.speed_x *= -1

class TransparentOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setGeometry(WINDOW_LEFT, WINDOW_TOP, WINDOW_WIDTH, WINDOW_HEIGHT)

        self.kitten_images = self.load_kittens()
        self.all_kittens = []
        self.stacked_kittens = []
        self.column_heights = [WINDOW_HEIGHT] * SPAWN_COLUMNS

        self.spawn_timer = QTimer()
        self.spawn_timer.timeout.connect(self.spawn_kitten)
        self.spawn_timer.start(SPAWN_INTERVAL_MS)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.game_loop)
        self.update_timer.start(2000 // FPS)

    def load_kittens(self):
        kittens = []
        if not os.path.exists(KITTEN_IMAGE_PATH):
            print("ERROR: Kitten image path does not exist.")
            return kittens

        for filename in os.listdir(KITTEN_IMAGE_PATH):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                filepath = os.path.join(KITTEN_IMAGE_PATH, filename)
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    w, h = pixmap.width(), pixmap.height()
                    if w > h:
                        new_w = KITTEN_MAX_DIMENSION
                        new_h = int(new_w * h / w)
                    else:
                        new_h = KITTEN_MAX_DIMENSION
                        new_w = int(new_h * w / h)
                    scaled = pixmap.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    kittens.append(scaled)
        print(f"Loaded {len(kittens)} kitten images.")
        return kittens

    def spawn_kitten(self, single=False):
        if not self.kitten_images:
            return

        image = random.choice(self.kitten_images)
        img_width = image.width()
        eligible_columns = [i for i in range(SPAWN_COLUMNS)
                            if self.column_heights[i] > TOP_THRESHOLD and
                            (i + 1) * COLUMN_WIDTH - img_width >= i * COLUMN_WIDTH]

        if not eligible_columns:
            return
        
        # If single=True, spawn exactly one kitten; else spawn 1 or 2 kittens randomly
        count = 1 if single else random.randint(1, 2)

        for _ in range(count):
            if not eligible_columns:
                break

            col = random.choice(eligible_columns)
            min_x = col * COLUMN_WIDTH
            max_x = (col + 1) * COLUMN_WIDTH - image.width()
            x = random.randint(min_x, max_x)
            x = max(0, min(x, WINDOW_WIDTH - image.width()))
            x += random.randint(-20, 20)
            x = max(0, min(x, WINDOW_WIDTH - image.width()))
            y = -image.height() - random.randint(0, 100)

            self.all_kittens.append(Kitten(x, y, image))

    def game_loop(self):
        for kitten in self.all_kittens:
            kitten.update(self.stacked_kittens)
            if not kitten.is_falling and kitten not in self.stacked_kittens:
                self.stacked_kittens.append(kitten)
                start_col = int(kitten.rect.left()) // COLUMN_WIDTH
                end_col = int(kitten.rect.right()) // COLUMN_WIDTH
                for i in range(start_col, end_col + 1):
                    if 0 <= i < SPAWN_COLUMNS:
                        self.column_heights[i] = min(self.column_heights[i], int(kitten.rect.top()))
        self.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for kitten in self.all_kittens:
            painter.drawPixmap(kitten.rect.topLeft(), kitten.pixmap)

    def mousePressEvent(self, event):
        for kitten in reversed(self.all_kittens):
            if kitten.rect.contains(event.pos()):
                print(f"Click blocked by kitten at {kitten.rect.topLeft()}.")
                return
        print("Click passed through.")
        event.ignore()

if __name__ == '__main__':
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

