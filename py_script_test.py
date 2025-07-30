import pygame
import random
import os
import sys

# --- Initialize Pygame ---
pygame.init()
print("Pygame initialized successfully.")

# --- Constants ---
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
SCREEN_WIDTH = WINDOW_WIDTH
SCREEN_HEIGHT = WINDOW_HEIGHT
print(f"Game area set to: {SCREEN_WIDTH}x{SCREEN_HEIGHT} pixels.")

FPS = 60
KITTEN_SPEED = 5
KITTEN_MAX_DIMENSION = 120 # Max width or height for any scaled kitten.
KITTEN_COLLISION_SCALE = 0.6 # Adjust for tighter/looser visual stacking (0.5 to 0.9)

# NEW: Constants for Stability and Sliding
STABILITY_THRESHOLD_X = 80 # Pixels: Max horizontal offset from center for stable stack. Adjust this.
SLIDE_HORIZONTAL_SPEED = 5 # Pixels per frame: How fast unstable kittens slide horizontally.

KITTEN_IMAGE_PATH = r"C:\Users\livad\Fisiere_coding\Pawse\Kitties"

SPAWN_COLUMNS = 20 # Number of vertical columns for spawning logic
COLUMN_WIDTH = SCREEN_WIDTH // SPAWN_COLUMNS # Actual width of each tracking column

# --- Set up the display ---
try:
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Pawse App - Falling Kittens (Windowed)")
    print(f"Pygame display set to windowed mode: {WINDOW_WIDTH}x{WINDOW_HEIGHT} pixels.")
except pygame.error as e:
    print(f"CRITICAL ERROR: Could not set display mode: {e}")
    pygame.quit()
    sys.exit()

# --- Load Kitten Images ---
kitten_original_images = []
print(f"Attempting to load kitten images from: {KITTEN_IMAGE_PATH}")
if not os.path.exists(KITTEN_IMAGE_PATH):
    print(f"ERROR: The specified kitten image path does NOT exist: {KITTEN_IMAGE_PATH}")
    print("Please ensure the directory exists and contains image files.")
    pygame.quit()
    sys.exit()

try:
    found_images = False
    for filename in os.listdir(KITTEN_IMAGE_PATH):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            filepath = os.path.join(KITTEN_IMAGE_PATH, filename)
            try:
                image = pygame.image.load(filepath).convert_alpha()
                original_width, original_height = image.get_size()
                aspect_ratio = original_width / original_height

                if original_width > original_height:
                    new_width = KITTEN_MAX_DIMENSION
                    new_height = int(new_width / aspect_ratio)
                else:
                    new_height = KITTEN_MAX_DIMENSION
                    new_width = int(new_height * aspect_ratio)

                image = pygame.transform.scale(image, (new_width, new_height))
                kitten_original_images.append(image)
                print(f"  - Successfully loaded and scaled: {filename} to {new_width}x{new_height}")
                found_images = True
            except pygame.error as e:
                print(f"  - WARNING: Error loading image {filename}: {e}")

    if not found_images:
        print(f"WARNING: No valid kitten images found in {KITTEN_IMAGE_PATH}. The app will run, but no kittens will appear as there are no images to display.")
except Exception as e:
    print(f"CRITICAL ERROR: An unexpected error occurred while processing image directory: {e}")
    pygame.quit()
    sys.exit()

# --- Kitten Class ---
class Kitten(pygame.sprite.Sprite):
    def __init__(self, x, y, image, layer):
        super().__init__()
        self.original_image = image # Original scaled image, for rotation
        self.image = image # Current rotated image, for drawing

        # This rect represents the VISUAL bounds of the kitten at its current (unrotated) form.
        self.visual_image_rect = self.image.get_rect()
        self.visual_image_rect.topleft = (x, y) # Set its initial position

        # This 'rect' attribute is the actual collision box.
        # It's derived from the visual_image_rect but scaled down for tighter collision.
        collision_width = int(self.visual_image_rect.width * KITTEN_COLLISION_SCALE)
        collision_height = int(self.visual_image_rect.height * KITTEN_COLLISION_SCALE)

        collision_width = max(1, collision_width) # Ensure minimum size
        collision_height = max(1, collision_height)

        self.rect = pygame.Rect(0, 0, collision_width, collision_height)
        self.rect.center = self.visual_image_rect.center # Center collision rect on visual image

        self.speed = KITTEN_SPEED
        self.is_falling = True # Kitten always starts falling
        self.horizontal_slide_speed = 0 # New: horizontal speed for sliding
        self.rotation_angle = random.randint(0, 359)
        self.layer = layer # 0 for background, 1 for foreground

        # Apply initial rotation
        self._rotate_image()

        # After rotation, re-center rects to the initial spawn position
        self.visual_image_rect.topleft = (x, y)
        self.rect.center = self.visual_image_rect.center

        # Debug print for creation
        # print(f"Kitten created at ({self.rect.x}, {self.rect.y}) Collision Size: {self.rect.width}x{self.rect.height} Visual Size: {self.visual_image_rect.width}x{self.visual_image_rect.height}. Layer: {self.layer}")


    def _rotate_image(self):
        current_collision_center = self.rect.center

        self.image = pygame.transform.rotate(self.original_image, self.rotation_angle)

        self.visual_image_rect = self.image.get_rect(center=current_collision_center)

        collision_width = int(self.visual_image_rect.width * KITTEN_COLLISION_SCALE)
        collision_height = int(self.visual_image_rect.height * KITTEN_COLLISION_SCALE)

        collision_width = max(1, collision_width)
        collision_height = max(1, collision_height)

        self.rect.update(self.rect.x, self.rect.y, collision_width, collision_height)
        self.rect.center = current_collision_center


    def update(self, stacked_kittens_group):
        # Apply movement (vertical and horizontal) if the kitten is considered "falling" (which includes sliding)
        if self.is_falling:
            self.rect.y += self.speed
            self.rect.x += self.horizontal_slide_speed

            # Clamp horizontal movement to screen boundaries
            if self.rect.left < 0:
                self.rect.left = 0
                self.horizontal_slide_speed = 0 # Stop sliding into the wall
            if self.rect.right > SCREEN_WIDTH:
                self.rect.right = SCREEN_WIDTH
                self.horizontal_slide_speed = 0 # Stop sliding into the wall

        # Check for collision with the bottom of the window (solid ground)
        if self.rect.bottom >= SCREEN_HEIGHT:
            self.rect.bottom = SCREEN_HEIGHT
            self.is_falling = False # Definitely not falling on solid ground
            self.horizontal_slide_speed = 0 # Stop any horizontal slide
            return # Kitten has landed firmly, no more checks needed for this frame

        # Find potential support kittens from the already stacked group
        # Look for kittens that are below and whose top is close to our bottom
        support_kitten = None
        for other_kitten in stacked_kittens_group:
            if other_kitten != self and not other_kitten.is_falling: # Exclude self and falling kittens
                # Check if our bottom is at or just below their top, AND there's horizontal overlap
                if self.rect.colliderect(other_kitten.rect) and \
                   self.rect.bottom >= other_kitten.rect.top - self.speed and \
                   self.rect.bottom <= other_kitten.rect.top + self.speed:
                    # This is a strong candidate for support. Prioritize the highest (lowest Y) one.
                    if support_kitten is None or other_kitten.rect.top < support_kitten.rect.top:
                        support_kitten = other_kitten
        
        # Determine state based on whether a primary support was found
        if support_kitten:
            # Snap vertically to the top of the support kitten
            self.rect.bottom = support_kitten.rect.top

            # Calculate horizontal offset from the support kitten's center
            offset_x = self.rect.centerx - support_kitten.rect.centerx

            # Check for horizontal stability
            if abs(offset_x) > STABILITY_THRESHOLD_X:
                self.is_falling = True # Kitten is unstable, so it remains "falling" (sliding)
                if offset_x > 0: # Current kitten is to the right of support's center
                    self.horizontal_slide_speed = SLIDE_HORIZONTAL_SPEED
                else: # Current kitten is to the left
                    self.horizontal_slide_speed = -SLIDE_HORIZONTAL_SPEED
                # print(f"Kitten {id(self)} unstable on {id(support_kitten)}. Offset: {offset_x:.1f}. Sliding: {self.horizontal_slide_speed}")
            else:
                # Kitten is stable on top of the support
                self.is_falling = False # Stop vertical "fall"
                self.horizontal_slide_speed = 0 # Stop horizontal slide
                # print(f"Kitten {id(self)} stable on {id(support_kitten)}. Offset: {offset_x:.1f}.")
        else:
            # No support kitten found. If it was previously stable, it must start falling again.
            if not self.is_falling:
                self.is_falling = True
                self.horizontal_slide_speed = 0 # Reset horizontal slide if it completely falls off a stack

# --- Game Variables ---
all_kittens = pygame.sprite.Group()
stacked_kittens = pygame.sprite.Group()
clock = pygame.time.Clock()
spawn_timer = 0
SPAWN_INTERVAL = 5

# Initialize column heights
column_highest_stacked_y = [SCREEN_HEIGHT] * SPAWN_COLUMNS

# Temporary visual indicator timer
show_test_rect_duration = FPS * 2
test_rect_timer = 0

# --- Game Loop ---
running = True
print("Starting game loop.")
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            print("Quit event detected. Exiting game loop.")
        if event.type == pygame.KEYDOWN: # Check for KEYDOWN event type
            if event.key == pygame.K_ESCAPE:
                running = False
                print("Escape key pressed. Exiting application.")

    # --- Conditional Spawning ---
    if kitten_original_images:
        spawn_timer += 1
        if spawn_timer >= SPAWN_INTERVAL:
            eligible_columns_indices = [
                i for i, height in enumerate(column_highest_stacked_y)
                if height > (KITTEN_MAX_DIMENSION + 10) # Ensure space for at least one kitten + buffer
            ]

            if eligible_columns_indices:
                chosen_column_index = random.choice(eligible_columns_indices)
                chosen_image = random.choice(kitten_original_images)
                kitten_layer = random.choice([0, 1])

                min_x_in_column = chosen_column_index * COLUMN_WIDTH
                max_x_in_column = min(
                    (chosen_column_index + 1) * COLUMN_WIDTH - chosen_image.get_width(),
                    SCREEN_WIDTH - chosen_image.get_width()
                )

                if min_x_in_column < max_x_in_column:
                    spawn_x = random.randint(min_x_in_column, max_x_in_column)
                else: # Fallback if column is too narrow for kitten, spawn at column start
                    spawn_x = min_x_in_column
                    if spawn_x + chosen_image.get_width() > SCREEN_WIDTH: # If even column start exceeds screen
                        spawn_x = SCREEN_WIDTH - chosen_image.get_width()

                spawn_y = -chosen_image.get_height()

                new_kitten = Kitten(spawn_x, spawn_y, chosen_image, kitten_layer)
                all_kittens.add(new_kitten)
            # else: print("All columns are filled to the top! No more kittens can spawn.") # Too much console spam
            spawn_timer = 0
    elif not pygame.time.get_ticks() % (FPS * 5):
        print("WARNING: No kitten images loaded. No kittens will spawn.")

    # --- Update ---
    for kitten in list(all_kittens): # Iterate over a copy to allow safe modification
        kitten.update(stacked_kittens)
        # If kitten has stopped falling AND is not already in the stacked group, add it.
        # Note: 'is_falling' being False now means it's firmly stable.
        if not kitten.is_falling and kitten not in stacked_kittens:
            stacked_kittens.add(kitten)
            # print(f"Kitten (ID:{id(kitten)}) moved to stacked_kittens group. Stacked count: {len(stacked_kittens)}")

            # Update the highest stacked point for the columns this kitten occupies
            start_col = kitten.rect.x // COLUMN_WIDTH
            end_col = (kitten.rect.right - 1) // COLUMN_WIDTH

            for i in range(start_col, end_col + 1):
                if 0 <= i < SPAWN_COLUMNS:
                    column_highest_stacked_y[i] = min(column_highest_stacked_y[i], kitten.rect.top)
                    # print(f"Column {i} filled up to Y: {column_highest_stacked_y[i]}")

    # --- Draw ---
    screen.fill((135, 206, 235)) # Sky blue background

    # Sort all_kittens by layer to ensure correct drawing order (layer 0 first, then layer 1)
    sorted_kittens = sorted(all_kittens, key=lambda k: k.layer)
    for kitten in sorted_kittens:
        # Calculate the draw position for the image based on the collision rect's center
        draw_rect = kitten.image.get_rect(center=kitten.rect.center)
        screen.blit(kitten.image, draw_rect)

        # --- DEBUG VISUAL: Uncomment to see the collision rects ---
        # if kitten.is_falling:
        #     pygame.draw.rect(screen, (255, 0, 0, 100), kitten.rect, 1) # Red for falling/sliding
        # else:
        #     pygame.draw.rect(screen, (0, 255, 0, 100), kitten.rect, 1) # Green for stable


    # Temporary red rectangle indicator
    if test_rect_timer < show_test_rect_duration:
        pygame.draw.rect(screen, (255, 0, 0), (SCREEN_WIDTH - 120, 20, 100, 100))
        test_rect_timer += 1

    # --- Optional: Draw column boundaries for debugging ---
    # for i in range(SPAWN_COLUMNS):
    #     pygame.draw.line(screen, (255, 255, 0, 100), (i * COLUMN_WIDTH, 0), (i * COLUMN_WIDTH, SCREEN_HEIGHT), 1)
    #     pygame.draw.line(screen, (255, 0, 255, 150), (i * COLUMN_WIDTH, column_highest_stacked_y[i]), ((i+1) * COLUMN_WIDTH -1, column_highest_stacked_y[i]), 2)


    # --- Update the display ---
    pygame.display.flip()
    clock.tick(FPS)

print("Game loop ended.")
pygame.quit()
print("Pygame quit and system exit.")
sys.exit()