import sys
import os
import random
import time
from PyQt5.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QRegion, QGuiApplication, QTransform
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMainWindow

KITTEN_IMAGE_PATH = r"C:\Users\livad\Fisiere_coding\Pawse\Kitties"

app = QApplication(sys.argv)  # Required to get screens
# Get combined geometry across all screens
screen_geometries = QGuiApplication.screens()
if not screen_geometries:
    raise RuntimeError("No screens found. Cannot determine screen geometry.")

screen_rects = [screen.geometry() for screen in screen_geometries]
WINDOW_LEFT = min(rect.left() for rect in screen_rects)
WINDOW_TOP = min(rect.top() for rect in screen_rects)
WINDOW_RIGHT = max(rect.right() for rect in screen_rects)
WINDOW_BOTTOM = max(rect.bottom() for rect in screen_rects)

WINDOW_WIDTH = WINDOW_RIGHT - WINDOW_LEFT
WINDOW_HEIGHT = WINDOW_BOTTOM - WINDOW_TOP
print(f"Overlay starts at ({WINDOW_LEFT}, {WINDOW_TOP}) and spans {WINDOW_WIDTH}x{WINDOW_HEIGHT}")


FPS = 60
SPAWN_INTERVAL_MS = 250
KITTEN_SPEED = 5
KITTEN_MAX_DIMENSION = 200
KITTEN_COLLISION_SCALE = 0.6
STABILITY_THRESHOLD_X = 80
SLIDE_HORIZONTAL_SPEED = 5
SPAWN_COLUMNS = 20
COLUMN_WIDTH = WINDOW_WIDTH // SPAWN_COLUMNS
TOP_THRESHOLD = 10
VIBRATION_GUARD_TIME = 0.2
TOGGLE_COUNT_LIMIT = 6
GRAVITY = 0.5
TERMINAL_VELOCITY = 10


# --- Pre-fall Phase ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        screens = QGuiApplication.screens()
        combined_rect = screens[0].geometry()

        for screen in screens[1:]:
            combined_rect = combined_rect.united(screen.geometry())

        # Save combined geometry constants for consistent use
        global WINDOW_LEFT, WINDOW_TOP, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_RIGHT, COLUMN_WIDTH
        WINDOW_LEFT = combined_rect.left()
        WINDOW_TOP = combined_rect.top()
        WINDOW_WIDTH = combined_rect.width()
        WINDOW_HEIGHT = combined_rect.height()
        WINDOW_RIGHT = WINDOW_LEFT + WINDOW_WIDTH
        COLUMN_WIDTH = WINDOW_WIDTH // SPAWN_COLUMNS


        self.setGeometry(combined_rect)
        self.window_rect = combined_rect  # Save for reference


        self.warning_kitten_count = 0
        self.labels = []

        for screen in screens:
            screen_geom = screen.geometry()
            label = QLabel("Break time in 1 minute...", self)
            label.setStyleSheet(
                "color: white; font-size: 30px; background-color: rgba(0,0,0,0.5); padding: 20px; border-radius: 10px;"
            )
            label.adjustSize()
            # Position relative to main window coordinates (combined)
            label_x = screen_geom.left() - WINDOW_LEFT + (screen_geom.width() - label.width()) // 2
            label_y = screen_geom.top() - WINDOW_TOP + (screen_geom.height() - label.height()) // 2
            label.move(label_x, label_y)
            label.show()
            self.labels.append(label)

        self.overlay = TransparentOverlay(self, geometry=combined_rect)
        # self.overlay.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.overlay.show()
        self.overlay.spawn_timer.stop()

         # Setup timer to spawn 2-3 warning kittens over ~1 min
        self.warning_spawn_timer = QTimer()
        self.warning_spawn_timer.timeout.connect(self.spawn_warning_kitten)
        self.warning_spawn_timer.start(3000) # spawn warning kitten every 3 seconds (adjust as needed)

        # Immediately spawn the first warning kitten
        self.spawn_warning_kitten()

        # Start main fall after 10 seconds
        self.warning_timer = QTimer()
        self.warning_timer.setSingleShot(True)
        self.warning_timer.timeout.connect(self.start_main_kitten_fall)
        self.warning_timer.start(10000) #change break message time ------------------------------------

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
        transform = QTransform().rotate(self.rotation)
        self.original_pixmap = image
        self.pixmap = image.transformed(transform, Qt.SmoothTransformation)

        width = self.pixmap.width()
        height = self.pixmap.height()

        # Shrink collision rect compared to visible image
        collision_width = width * KITTEN_COLLISION_SCALE
        collision_height = height * KITTEN_COLLISION_SCALE
        offset_x = (width - collision_width) / 2
        offset_y = (height - collision_height) / 2

        self.rect = QRectF(x + offset_x, y + offset_y, collision_width, collision_height)
        # self.rect = QRectF(x, y, self.pixmap.width(), self.pixmap.height())
        self.speed_y = KITTEN_SPEED + random.uniform(-1, 1)
        self.speed_x = random.uniform(-1, 1)
        self.is_falling = True
        self.last_toggle_time = time.time()
        self.toggle_count = 0
        self.freeze_motion = False




    def update(self, stacked_kittens, screen_rects):
        now = time.time()
        if self.freeze_motion:
            return
        
        collided = False  # define once, used in both contexts

        if self.is_falling:
            steps = int(max(abs(self.speed_y), abs(self.speed_x))) + 1
            dy = self.speed_y / steps
            dx = self.speed_x / steps
            
            for _ in range(steps):
                self.rect.translate(dx, dy)

            # Check collision with stacked kittens
                for other in stacked_kittens:
                     if other != self and self.rect.intersects(other.rect):

            # Collision from above (falling on top)
                        if self.rect.bottom() > other.rect.top() and self.rect.center().y() < other.rect.center().y():
                            self.rect.moveBottom(other.rect.top())
                            self.is_falling = False
                            self.speed_y = 0
                            collided = True
                            break
                if collided:
                    break

                # Collision screen edges
                for screen_rect in screen_rects:
                        if screen_rect.contains(self.rect.center().toPoint()):
                            # Bottom collision
                            if self.rect.bottom() >= screen_rect.bottom():
                                self.rect.moveBottom(screen_rect.bottom())
                                self.is_falling = False
                                self.speed_y = 0
                                collided = True
                                break

                            # Left/right horizontal clamp
                            if self.rect.left() < screen_rect.left():
                                self.rect.moveLeft(screen_rect.left())
                            elif self.rect.right() > screen_rect.right():
                                self.rect.moveRight(screen_rect.right())
                            break  # found the containing screen, no need to check others

                        if collided:
                            break
                        


            # Apply gravity if still falling
            if self.is_falling:
                self.speed_y = min(self.speed_y + GRAVITY, TERMINAL_VELOCITY)
            



    # --- Stability/Vibration Logic ---
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

# --- Freeze kitten if it's vibrating too much ---
        if self.toggle_count > TOGGLE_COUNT_LIMIT:
            self.freeze_motion = True
            print(f"Kitten at {self.rect.topLeft()} frozen to prevent vibration.")




# --- Fall Phase ---
class TransparentOverlay(QWidget):
    def __init__(self, parent=None, geometry=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # Use passed geometry or fallback to full window constants
        if geometry:
            self.setGeometry(geometry)
        else:
            self.setGeometry(WINDOW_LEFT, WINDOW_TOP, WINDOW_WIDTH, WINDOW_HEIGHT)

        # Create screen rects relative to the overlay
        self.screen_rects = [
            screen.geometry().translated(-self.geometry().left(), -self.geometry().top())
            for screen in QGuiApplication.screens()
        ]


        self.kitten_images = self.load_kittens()
        self.all_kittens = []
        self.stacked_kittens = []
        self.spawn_timer = QTimer()
        self.spawn_timer.timeout.connect(self.spawn_kitten)
        self.spawn_timer.start(SPAWN_INTERVAL_MS)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.game_loop)
        self.update_timer.start(1000 // FPS)

        self.column_heights = [self.geometry().bottom()] * SPAWN_COLUMNS

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

        spawn_count = 1 if single else random.randint(1, 3)
        for _ in range(spawn_count):
            if not eligible_columns:
                break

            col = random.choice(eligible_columns)
            min_x = col * COLUMN_WIDTH
            max_x = min((col + 1) * COLUMN_WIDTH - image.width(), WINDOW_WIDTH - image.width())

            if max_x < min_x:
                print(f"Invalid spawn range for column {col}: min_x={min_x}, max_x={max_x}")
                continue

            # Spawn kitten horizontally within column boundaries
            x = random.randint(min_x, max_x)

            # Spawn above the visible area
            y = -image.height() - random.randint(0, 100)

            # # Spawn in screen-wide range (absolute)
            # x = random.randint(WINDOW_LEFT, WINDOW_RIGHT - image.width())
            # x += random.randint(-20, 20)
            # x = max(WINDOW_LEFT, min(x, WINDOW_RIGHT - image.width()))
            # y = WINDOW_TOP - image.height() - random.randint(0, 100)

            # # ✅ Convert to overlay-relative coordinates
            # x -= WINDOW_LEFT
            # y -= WINDOW_TOP

            print(f"Spawning kitten at x={x}, y={y}, col={col}")
            self.all_kittens.append(Kitten(x, y, image))

    def game_loop(self):
        for kitten in self.all_kittens:
            kitten.update(self.stacked_kittens, self.screen_rects)

            if not kitten.is_falling and kitten not in self.stacked_kittens:
                self.stacked_kittens.append(kitten)
                start_col = int(kitten.rect.left()) // COLUMN_WIDTH
                end_col = int(kitten.rect.right()) // COLUMN_WIDTH
                end_col = min(SPAWN_COLUMNS - 1, int(kitten.rect.right()) // COLUMN_WIDTH)

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
            # adjusted_pos = kitten.rect.topLeft() - QPoint(WINDOW_LEFT, WINDOW_TOP)
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
