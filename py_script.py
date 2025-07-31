import sys
import os
import random
import time
from PyQt5.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QRegion, QGuiApplication, QTransform
from PyQt5.QtWidgets import QApplication, QWidget

KITTEN_IMAGE_PATH = r"C:\Users\livad\Fisiere_coding\Pawse\Kitties"
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080
FPS = 60
SPAWN_INTERVAL_MS = 250
KITTEN_SPEED = 5
KITTEN_MAX_DIMENSION = 120
KITTEN_COLLISION_SCALE = 0.6
STABILITY_THRESHOLD_X = 80
SLIDE_HORIZONTAL_SPEED = 5
SPAWN_COLUMNS = 20
COLUMN_WIDTH = WINDOW_WIDTH // SPAWN_COLUMNS
TOP_THRESHOLD = 10  # Threshold for column height to consider it filled
VIBRATION_GUARD_TIME = 0.2
TOGGLE_COUNT_LIMIT = 6  # Number of toggles within short time to freeze motion

class Kitten:
    def __init__(self, x, y, image):
        self.original_pixmap = image
        rotation = random.randint(-25, 25)
        transform = QTransform().rotate(rotation)
        self.pixmap = image.transformed(transform, Qt.SmoothTransformation)
        self.rect = QRectF(x, y, self.pixmap.width(), self.pixmap.height())
        self.speed_y = KITTEN_SPEED + random.uniform(-1, 1)
        self.speed_x = random.uniform(-1, 1)
        self.is_falling = True
        self.last_toggle_time = time.time()
        self.toggle_count = 0
        self.freeze_motion = False

    def update(self, stacked_kittens):
        now = time.time()

        if self.freeze_motion:
            return

        if self.is_falling:
            self.rect.moveTop(self.rect.top() + self.speed_y)
            self.rect.moveLeft(self.rect.left() + self.speed_x)

        if self.rect.bottom() >= WINDOW_HEIGHT:
            self.rect.moveBottom(WINDOW_HEIGHT)
            self.is_falling = False
            self.speed_x = 0
            return

        support = None
        for other in stacked_kittens:
            if other != self and not other.is_falling:
                if self.rect.intersects(other.rect):
                    if abs(self.rect.bottom() - other.rect.top()) <= self.speed_y:
                        if support is None or other.rect.top() < support.rect.top():
                            support = other

        if support:
            self.rect.moveBottom(support.rect.top())
            offset_x = self.rect.center().x() - support.rect.center().x()
            if abs(offset_x) > STABILITY_THRESHOLD_X:
                if now - self.last_toggle_time > VIBRATION_GUARD_TIME:
                    self.is_falling = True
                    self.speed_x = SLIDE_HORIZONTAL_SPEED if offset_x > 0 else -SLIDE_HORIZONTAL_SPEED
                    self.last_toggle_time = now
                    self.toggle_count += 1
            else:
                if self.is_falling:
                    self.toggle_count += 1
                self.is_falling = False
                self.speed_x = 0
                self.last_toggle_time = now
        else:
            if not self.is_falling and now - self.last_toggle_time > VIBRATION_GUARD_TIME:
                self.is_falling = True
                self.speed_x = 0
                self.last_toggle_time = now
                self.toggle_count += 1

        if self.toggle_count > TOGGLE_COUNT_LIMIT:
            self.freeze_motion = True
            print(f"Kitten at {self.rect.topLeft()} frozen to prevent vibration.")

class TransparentOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        screen = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())

        self.kitten_images = self.load_kittens()
        self.all_kittens = []
        self.stacked_kittens = []
        self.spawn_timer = QTimer()
        self.spawn_timer.timeout.connect(self.spawn_kitten)
        self.spawn_timer.start(SPAWN_INTERVAL_MS)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.game_loop)
        self.update_timer.start(1000 // FPS)

        self.column_heights = [WINDOW_HEIGHT] * SPAWN_COLUMNS

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

    def spawn_kitten(self):
        if not self.kitten_images:
            print("No kitten images loaded. Skipping spawn.")
            return

        image = random.choice(self.kitten_images)
        img_width = image.width()

        eligible_columns = []
        for i in range(SPAWN_COLUMNS):
            if self.column_heights[i] > TOP_THRESHOLD:
                min_x = i * COLUMN_WIDTH
                max_x = (i + 1) * COLUMN_WIDTH - img_width
                if max_x >= min_x:
                    eligible_columns.append(i)

        if not eligible_columns:
            print("WARNING: All columns are filled to the top. Cannot spawn more kittens.")
            return

        filled_count = SPAWN_COLUMNS - len(eligible_columns)
        if filled_count >= int(SPAWN_COLUMNS * 0.8):
            print(f"NOTICE: {filled_count}/{SPAWN_COLUMNS} columns are filled near the top.")

        spawn_count = random.randint(1, 3)
        for _ in range(spawn_count):
            if not eligible_columns:
                break

            col = random.choice(eligible_columns)
            min_x = col * COLUMN_WIDTH
            max_x = min((col + 1) * COLUMN_WIDTH - image.width(), WINDOW_WIDTH - image.width())

            if max_x < min_x:
                print(f"Invalid spawn range for column {col}: min_x={min_x}, max_x={max_x}")
                continue

            x = random.randint(min_x, max_x)
            x += random.randint(-20, 20)
            x = max(0, min(x, WINDOW_WIDTH - image.width()))
            y = -image.height() - random.randint(0, 100)

            print(f"Spawning kitten at x={x}, y={y}, col={col}")
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
        painter.setOpacity(1.0)

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
    app = QApplication(sys.argv)
    overlay = TransparentOverlay()
    overlay.showFullScreen()
    sys.exit(app.exec_())
