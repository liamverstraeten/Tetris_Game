"""
Tetris Hardcore Pack
- Bomb pieces
- Invisible mode (piece invisible after 2s)
- Hyper mode (field contraction over time + periodic garbage)
- Random shape swap
- Local 2-player split-screen
- Simple menu to toggle modes

Benodigdheden: pygame
Installatie: pip install pygame
Run: python tetris_hardcore_pack.py
"""

import pygame
import random
import sys
import time

# ===========================
# CONFIGURATIE
# ===========================
CELL_SIZE = 24
COLS = 10
ROWS = 20
PANEL_WIDTH = 200
FPS = 60

# Mode toggles — je kunt deze standaard aan/uit zetten of in menu aanpassen
DEFAULT_MODES = {
    "bombs": True,
    "invisible_mode": True,
    "hyper_mode": True,
    "random_swap": True,
    "multiplayer_local": True,
    "sound": False
}

# kleuren
COLORS = [
    (0, 0, 0),        # 0 leeg
    (0, 240, 240),    # I
    (0, 0, 240),      # J
    (240, 160, 0),    # L
    (240, 240, 0),    # O
    (0, 240, 0),      # S
    (160, 0, 240),    # T
    (240, 0, 0),      # Z
    (200, 200, 200)   # grid lijnen/tekst
]

# SHAPES: elke vorm heeft rotaties; toevoegen van 'bomb' attribuut via shape_id > 7
# Voor bomb-blocks: we will treat shape_ids 11..17 as bomb variants of 1..7
SHAPES = {
    1: [  # I
        [[0,0,0,0],
         [1,1,1,1],
         [0,0,0,0],
         [0,0,0,0]],
        [[0,0,1,0],
         [0,0,1,0],
         [0,0,1,0],
         [0,0,1,0]]
    ],
    2: [  # J
        [[1,0,0],
         [1,1,1],
         [0,0,0]],
        [[0,1,1],
         [0,1,0],
         [0,1,0]],
        [[0,0,0],
         [1,1,1],
         [0,0,1]],
        [[0,1,0],
         [0,1,0],
         [1,1,0]]
    ],
    3: [  # L
        [[0,0,1],
         [1,1,1],
         [0,0,0]],
        [[0,1,0],
         [0,1,0],
         [0,1,1]],
        [[0,0,0],
         [1,1,1],
         [1,0,0]],
        [[1,1,0],
         [0,1,0],
         [0,1,0]]
    ],
    4: [  # O
        [[1,1],
         [1,1]]
    ],
    5: [  # S
        [[0,1,1],
         [1,1,0],
         [0,0,0]],
        [[0,1,0],
         [0,1,1],
         [0,0,1]]
    ],
    6: [  # T
        [[0,1,0],
         [1,1,1],
         [0,0,0]],
        [[0,1,0],
         [0,1,1],
         [0,1,0]],
        [[0,0,0],
         [1,1,1],
         [0,1,0]],
        [[0,1,0],
         [1,1,0],
         [0,1,0]]
    ],
    7: [  # Z
        [[1,1,0],
         [0,1,1],
         [0,0,0]],
        [[0,0,1],
         [0,1,1],
         [0,1,0]]
    ]
}

# ===========================
# UTILS / GAME CLASSES
# ===========================
class Piece:
    def __init__(self, shape_id, is_bomb=False):
        # shape_id in 1..7 reference shapes; if is_bomb True create bomb-variant
        self.base_id = shape_id
        self.is_bomb = is_bomb
        self.shape_id = shape_id + (10 if is_bomb else 0)  # bomb ids mapped >10
        self.rotations = SHAPES[shape_id]
        self.rotation = 0
        self.shape = self.rotations[self.rotation]
        self.x = COLS // 2 - len(self.shape[0]) // 2
        self.y = -2  # spawn slightly above to allow rotation
        self.spawn_time = time.time()
        self.visible_until = self.spawn_time + 2.0  # invisible after 2s if invisible_mode on
        self.hold_used = False

    def rotate(self, grid):
        old = self.rotation
        self.rotation = (self.rotation + 1) % len(self.rotations)
        self.shape = self.rotations[self.rotation]
        if not valid_position(self, grid):
            # beperkte wall kick: probeer 1 x left/right
            for dx in (-1, 1):
                self.x += dx
                if valid_position(self, grid):
                    return True
                self.x -= dx
            self.rotation = old
            self.shape = self.rotations[self.rotation]
            return False
        return True

    def get_cells(self):
        cells = []
        for i, row in enumerate(self.shape):
            for j, val in enumerate(row):
                if val:
                    cells.append((self.x + j, self.y + i))
        return cells

def create_grid(locked_positions, cols=COLS, rows=ROWS):
    return [[0 for _ in range(cols)] for _ in range(rows)]

def valid_position(piece, grid):
    for i, row in enumerate(piece.shape):
        for j, val in enumerate(row):
            if val:
                x = piece.x + j
                y = piece.y + i
                if x < 0 or x >= COLS or y >= ROWS:
                    return False
                if y >= 0 and grid[y][x] != 0:
                    return False
    return True

def lock_piece(piece, locked_positions, modes):
    """Lock the piece into locked_positions. If bomb -> explode neighbors."""
    for i, row in enumerate(piece.shape):
        for j, val in enumerate(row):
            if val:
                x = piece.x + j
                y = piece.y + i
                if 0 <= x < COLS and 0 <= y < ROWS:
                    if piece.is_bomb and modes["bombs"]:
                        # mark bomb cell differently (we'll explode immediately)
                        locked_positions[(x, y)] = -1  # -1 means bomb tile
                    else:
                        locked_positions[(x, y)] = piece.base_id
    # handle bombs explosion: find bombs and explode
    if modes["bombs"]:
        bombs = [pos for pos, v in list(locked_positions.items()) if v == -1]
        for (bx, by) in bombs:
            # explosion radius 1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    tx, ty = bx + dx, by + dy
                    if (tx, ty) in locked_positions:
                        del locked_positions[(tx, ty)]
            # leave a small flash? already removed
    return

def clear_rows(grid, locked_positions):
    rows_cleared = 0
    for y in range(ROWS - 1, -1, -1):
        full = True
        for x in range(COLS):
            if grid[y][x] == 0:
                full = False
                break
        if full:
            rows_cleared += 1
            # remove from locked
            for x in range(COLS):
                if (x, y) in locked_positions:
                    del locked_positions[(x, y)]
            # move everything above down
            for key in sorted(list(locked_positions.keys()), key=lambda k: k[1])[::-1]:
                xk, yk = key
                if yk < y:
                    val = locked_positions.pop(key)
                    locked_positions[(xk, yk + 1)] = val
    return rows_cleared

def convert_locked_to_grid(locked_positions):
    grid = create_grid(locked_positions)
    for (x, y), v in locked_positions.items():
        if 0 <= y < ROWS and 0 <= x < COLS:
            # bomb exploded cells were deleted already; store base id values only
            if v > 0:
                grid[y][x] = v
    return grid

def add_garbage_line(locked_positions):
    """Add a garbage line (random hole) at bottom, shift everything up"""
    # shift everything up by 1: decrease y by 1
    new_locked = {}
    for (x, y), v in list(locked_positions.items()):
        ny = y - 1
        if ny >= 0:
            new_locked[(x, ny)] = v
    # new bottom row at y = ROWS-1 with hole
    hole = random.randint(0, COLS - 1)
    for x in range(COLS):
        if x != hole:
            new_locked[(x, ROWS - 1)] = random.randint(1, 7)
    locked_positions.clear()
    locked_positions.update(new_locked)

def shrink_field_from_sides(locked_positions, shrink_amount_left, shrink_amount_right):
    """Mark columns as unusable by setting locked cells in the shrink columns."""
    # left shrink
    for col in range(shrink_amount_left):
        for row in range(ROWS):
            locked_positions[(col, row)] = random.randint(1, 7)
    for col in range(COLS - shrink_amount_right, COLS):
        for row in range(ROWS):
            locked_positions[(col, row)] = random.randint(1, 7)

# ===========================
# GAME LOOP / UI
# ===========================
pygame.init()
pygame.mixer.init()
FONT = pygame.font.SysFont('consolas', 18)
BIGFONT = pygame.font.SysFont('consolas', 36)

SCREEN_WIDTH = COLS * CELL_SIZE + (PANEL_WIDTH if not DEFAULT_MODES["multiplayer_local"] else PANEL_WIDTH * 2)
SCREEN_HEIGHT = ROWS * CELL_SIZE
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Tetris Hardcore Pack")
clock = pygame.time.Clock()

# sounds (optional) - generate simple beep with pygame.mixer.Sound if available
SOUND_DROP = None
SOUND_CLEAR = None
if DEFAULT_MODES["sound"]:
    try:
        SOUND_DROP = pygame.mixer.Sound(pygame.sndarray.make_sound(
            (pygame.surfarray.array2d(pygame.Surface((1,1)))) ))
    except Exception:
        SOUND_DROP = None

def draw_grid(surface, grid, offset_x=0, offset_y=0, hide_grid=False):
    for y in range(ROWS):
        for x in range(COLS):
            val = grid[y][x]
            color = COLORS[val] if val < len(COLORS) else COLORS[0]
            rect = pygame.Rect(offset_x + x * CELL_SIZE, offset_y + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(surface, color, rect)
            if not hide_grid:
                pygame.draw.rect(surface, COLORS[8], rect, 1)

def draw_piece(surface, piece, offset_x=0, offset_y=0, modes=None):
    # if invisible_mode enabled and piece is past visible_until -> don't draw it
    if modes and modes["invisible_mode"] and time.time() > piece.visible_until:
        return  # invisible (still collides)
    for i, row in enumerate(piece.shape):
        for j, v in enumerate(row):
            if v:
                x = piece.x + j
                y = piece.y + i
                if y >= 0:
                    rect = pygame.Rect(offset_x + x * CELL_SIZE, offset_y + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                    # bomb pieces brighter
                    color = COLORS[piece.base_id]
                    if piece.is_bomb and modes and modes["bombs"]:
                        # highlight bomb with white border
                        pygame.draw.rect(surface, color, rect)
                        pygame.draw.rect(surface, (255, 255, 255), rect, 2)
                    else:
                        pygame.draw.rect(surface, color, rect)
                        pygame.draw.rect(surface, COLORS[8], rect, 1)

def draw_panel(surface, x, y, width, title, score, level, modes, next_piece, hold_piece):
    pygame.draw.rect(surface, (20, 20, 20), (x, y, width - 10, 200))
    title_surf = FONT.render(title, True, (240,240,240))
    surface.blit(title_surf, (x + 10, y + 10))
    score_surf = FONT.render(f"Score: {score}", True, (240,240,240))
    level_surf = FONT.render(f"Level: {level}", True, (240,240,240))
    surface.blit(score_surf, (x + 10, y + 40))
    surface.blit(level_surf, (x + 10, y + 70))
    # modes
    y0 = y + 110
    for idx, (k, v) in enumerate(modes.items()):
        mtxt = f"{k}: {'ON' if v else 'OFF'}"
        ms = FONT.render(mtxt, True, (200,200,200))
        surface.blit(ms, (x + 10, y0 + idx*20))
    # draw next piece
    if next_piece:
        nsurf = FONT.render("Next:", True, (200,200,200))
        surface.blit(nsurf, (x + 10, y + 160))
        for i, row in enumerate(next_piece.shape):
            for j, val in enumerate(row):
                if val:
                    rect = pygame.Rect(x + 80 + j * CELL_SIZE, y + 150 + i * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                    pygame.draw.rect(surface, COLORS[next_piece.base_id], rect)
                    pygame.draw.rect(surface, COLORS[8], rect, 1)
    # hold
    if hold_piece:
        hs = FONT.render("Hold:", True, (200,200,200))
        surface.blit(hs, (x + 10, y + 260))
        for i, row in enumerate(hold_piece.shape):
            for j, val in enumerate(row):
                if val:
                    rect = pygame.Rect(x + 80 + j * CELL_SIZE, y + 250 + i * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                    pygame.draw.rect(surface, COLORS[hold_piece.base_id], rect)
                    pygame.draw.rect(surface, COLORS[8], rect, 1)

# ===========================
# MAIN GAME CLASS (per speler)
# ===========================
class TetrisPlayer:
    def __init__(self, modes, side_name="P1"):
        self.modes = modes
        self.locked = {}  # (x,y) -> id
        self.grid = create_grid(self.locked)
        self.current = self.get_new_piece()
        self.next_piece = self.get_new_piece()
        self.hold_piece = None
        self.score = 0
        self.level = 1
        self.lines = 0
        self.fall_speed = 700  # ms
        self.last_drop_time = pygame.time.get_ticks()
        self.swap_cooldown = 0  # for random swap
        self.side_name = side_name
        self.start_time = time.time()
        self.shrink_left = 0
        self.shrink_right = 0

    def get_new_piece(self):
        # small chance to spawn bomb piece if bombs mode on
        is_bomb = self.modes["bombs"] and random.random() < 0.08  # 8% chance
        return Piece(random.randint(1, 7), is_bomb=is_bomb)

    def update_grid_from_locked(self):
        self.grid = create_grid(self.locked)
        for (x, y), v in self.locked.items():
            if 0 <= x < COLS and 0 <= y < ROWS and v > 0:
                self.grid[y][x] = v

    def soft_drop(self):
        self.current.y += 1
        if not valid_position(self.current, self.grid):
            self.current.y -= 1
            lock_piece(self.current, self.locked, self.modes)
            rows = clear_rows(self.grid, self.locked)
            if rows:
                self.score += rows * 1000
                self.lines += rows
            self.current = self.next_piece
            self.next_piece = self.get_new_piece()
            self.current.hold_used = False
            if not valid_position(self.current, self.grid):
                return False  # game over
        return True

    def hard_drop(self):
        while valid_position(self.current, self.grid):
            self.current.y += 1
        self.current.y -= 1
        lock_piece(self.current, self.locked, self.modes)
        rows = clear_rows(self.grid, self.locked)
        if rows:
            self.score += rows * 1000
            self.lines += rows
        self.current = self.next_piece
        self.next_piece = self.get_new_piece()
        self.current.hold_used = False
        if not valid_position(self.current, self.grid):
            return False
        return True

    def hold(self):
        if self.current.hold_used:
            return
        if self.hold_piece is None:
            self.hold_piece = Piece(self.current.base_id, is_bomb=self.current.is_bomb)
            self.current = self.next_piece
            self.next_piece = self.get_new_piece()
        else:
            # swap
            tmp = Piece(self.current.base_id, is_bomb=self.current.is_bomb)
            self.current = Piece(self.hold_piece.base_id, is_bomb=self.hold_piece.is_bomb)
            self.hold_piece = tmp
        self.current.hold_used = True

    def step(self):
        # update grid
        self.update_grid_from_locked()
        # gravitational drop based on fall_speed (ms)
        now = pygame.time.get_ticks()
        if now - self.last_drop_time > max(50, self.fall_speed):
            self.current.y += 1
            if not valid_position(self.current, self.grid):
                self.current.y -= 1
                lock_piece(self.current, self.locked, self.modes)
                rows = clear_rows(self.grid, self.locked)
                if rows:
                    self.score += rows * 1000
                    self.lines += rows
                self.current = self.next_piece
                self.next_piece = self.get_new_piece()
                self.current.hold_used = False
                if not valid_position(self.current, self.grid):
                    return False
            self.last_drop_time = now

        # random swap: occasionally swap to random shape mid-air
        if self.modes["random_swap"]:
            if pygame.time.get_ticks() > self.swap_cooldown:
                # small probability each tick to swap
                if random.random() < 0.003:  # ~0.3% per frame
                    # swap to a random piece but keep position if valid
                    candidate = Piece(random.randint(1, 7), is_bomb=(self.modes["bombs"] and random.random() < 0.05))
                    candidate.x, candidate.y = self.current.x, self.current.y
                    if valid_position(candidate, self.grid):
                        self.current = candidate
                        self.swap_cooldown = pygame.time.get_ticks() + 500  # 0.5s cooldown to avoid rapid swaps

        # hyper mode: periodic garbage + shrink sides over time
        if self.modes["hyper_mode"]:
            elapsed = time.time() - self.start_time
            # every 30s add garbage
            if int(elapsed) % 30 == 0 and int(elapsed) != 0:
                # add garbage only occasionally (50% chance)
                if random.random() < 0.08:
                    add_garbage_line(self.locked)
            # shrink sides every 45s by 1 column
            shrink_steps = int(elapsed // 45)
            if shrink_steps > 0:
                # compute left/right shrink amounts progressively (alternate)
                new_left = shrink_steps // 2
                new_right = shrink_steps - new_left
                if new_left != self.shrink_left or new_right != self.shrink_right:
                    self.shrink_left, self.shrink_right = new_left, new_right
                    shrink_field_from_sides(self.locked, self.shrink_left, self.shrink_right)

        # invisible mode: current piece visibility handled in draw
        return True

# ===========================
# GAME INIT
# ===========================
modes = DEFAULT_MODES.copy()
player1 = TetrisPlayer(modes, side_name="PLAYER 1")
player2 = TetrisPlayer(modes, side_name="PLAYER 2") if modes["multiplayer_local"] else None

# input mapping
controls_p1 = {
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "rotate": pygame.K_UP,
    "soft": pygame.K_DOWN,
    "hard": pygame.K_SPACE,
    "hold": pygame.K_c
}
controls_p2 = {
    "left": pygame.K_a,
    "right": pygame.K_d,
    "rotate": pygame.K_w,
    "soft": pygame.K_s,
    "hard": pygame.K_RSHIFT,
    "hold": pygame.K_q
}

paused = False
muted = not modes["sound"]

def draw():
    screen.fill((10,10,10))
    # left player viewport
    left_offset_x = 0
    right_offset_x = COLS * CELL_SIZE + PANEL_WIDTH if modes["multiplayer_local"] else COLS * CELL_SIZE
    # draw player1 area
    player1.update_grid_from_locked()
    draw_grid(screen, player1.grid, offset_x=left_offset_x)
    draw_piece(screen, player1.current, offset_x=left_offset_x, modes=modes)
    draw_panel(screen, left_offset_x + COLS * CELL_SIZE + 10, 10, PANEL_WIDTH, player1.side_name,
               player1.score, player1.level, modes, player1.next_piece, player1.hold_piece)

    if modes["multiplayer_local"] and player2:
        player2.update_grid_from_locked()
        draw_grid(screen, player2.grid, offset_x=right_offset_x)
        draw_piece(screen, player2.current, offset_x=right_offset_x, modes=modes)
        draw_panel(screen, right_offset_x + COLS * CELL_SIZE + 10, 10, PANEL_WIDTH, player2.side_name,
                   player2.score, player2.level, modes, player2.next_piece, player2.hold_piece)

    # top HUD
    if paused:
        text = BIGFONT.render("PAUSED", True, (255,255,255))
        screen.blit(text, ((SCREEN_WIDTH - text.get_width())//2, 10))
    # controls hint
    hint = FONT.render("P=pauze  M=mute  ESC=quit", True, (200,200,200))
    screen.blit(hint, (10, SCREEN_HEIGHT - 30))

    pygame.display.flip()

# ===========================
# MAIN LOOP
# ===========================
def main_loop():
    global paused, muted, modes, player1, player2
    running = True
    last_tick = pygame.time.get_ticks()
    while running:
        dt = clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_m:
                    muted = not muted
                # player 1 controls
                if not paused:
                    if event.key == controls_p1["left"]:
                        player1.current.x -= 1
                        if not valid_position(player1.current, player1.grid):
                            player1.current.x += 1
                    elif event.key == controls_p1["right"]:
                        player1.current.x += 1
                        if not valid_position(player1.current, player1.grid):
                            player1.current.x -= 1
                    elif event.key == controls_p1["rotate"]:
                        player1.current.rotate(player1.grid)
                    elif event.key == controls_p1["soft"]:
                        if not player1.soft_drop():
                            print("Player 1 lost")
                            running = False
                    elif event.key == controls_p1["hard"]:
                        if not player1.hard_drop():
                            print("Player 1 lost")
                            running = False
                    elif event.key == controls_p1["hold"]:
                        player1.hold()

                    # player 2 controls (if enabled)
                    if modes["multiplayer_local"] and player2:
                        if event.key == controls_p2["left"]:
                            player2.current.x -= 1
                            if not valid_position(player2.current, player2.grid):
                                player2.current.x += 1
                        elif event.key == controls_p2["right"]:
                            player2.current.x += 1
                            if not valid_position(player2.current, player2.grid):
                                player2.current.x -= 1
                        elif event.key == controls_p2["rotate"]:
                            player2.current.rotate(player2.grid)
                        elif event.key == controls_p2["soft"]:
                            if not player2.soft_drop():
                                print("Player 2 lost")
                                running = False
                        elif event.key == controls_p2["hard"]:
                            if not player2.hard_drop():
                                print("Player 2 lost")
                                running = False
                        elif event.key == controls_p2["hold"]:
                            player2.hold()

            # mouse/menu interactions could go here (not implemented)

        if not paused:
            # step players
            ok1 = player1.step()
            if not ok1:
                print("GAME OVER - Player 1")
                running = False
            if modes["multiplayer_local"] and player2:
                ok2 = player2.step()
                if not ok2:
                    print("GAME OVER - Player 2")
                    running = False

        draw()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main_loop()
