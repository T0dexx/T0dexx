#!/usr/bin/env python3
"""
F1 Top-Down Racing Game
A 2D top-down racing game with F1-style cars, AI opponents with rubberbanding.
Controls: Arrow keys or WASD to drive. ESC to quit. R to restart after finish.
"""

import pygame
import math
import random
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

TRACK_WIDTH = 120
NUM_LAPS = 3
NUM_AI = 5

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)
DARK_GRAY = (50, 50, 50)
RED = (220, 20, 20)
GREEN = (0, 200, 0)
YELLOW = (255, 220, 0)
TRACK_COLOR = (70, 70, 75)
CURB_RED = (200, 0, 0)
CURB_WHITE = (230, 230, 230)
GRASS_COLOR = (34, 120, 34)
HUD_BG = (0, 0, 0)

# Team colors and names
TEAM_COLORS = [
    ((220, 20, 20), "Ferrari"),
    ((0, 172, 230), "Mercedes"),
    ((255, 135, 0), "McLaren"),
    ((0, 111, 98), "Aston Martin"),
    ((54, 113, 198), "Alpine"),
    ((180, 25, 28), "Alfa Romeo"),
]

# Track control points – a large F1-inspired circuit
CONTROL_POINTS = [
    (800, 800),
    (1400, 780),
    (1900, 800),
    (2200, 950),
    (2350, 1200),
    (2300, 1500),
    (2100, 1750),
    (1800, 1900),
    (1400, 1950),
    (1000, 1950),
    (650, 1850),
    (400, 1650),
    (300, 1400),
    (280, 1100),
    (350, 850),
    (550, 750),
]


# ---------------------------------------------------------------------------
# Catmull-Rom spline helpers
# ---------------------------------------------------------------------------
def _catmull_rom_point(p0, p1, p2, p3, t):
    """Return a point on a Catmull-Rom spline at parameter *t* in [0, 1]."""
    t2 = t * t
    t3 = t2 * t
    x = 0.5 * (
        2 * p1[0]
        + (-p0[0] + p2[0]) * t
        + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
        + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
    )
    y = 0.5 * (
        2 * p1[1]
        + (-p0[1] + p2[1]) * t
        + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
        + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
    )
    return (x, y)


def generate_smooth_track(control_points, samples_per_segment=25):
    """Generate a smooth closed track from control points."""
    n = len(control_points)
    points = []
    for i in range(n):
        p0 = control_points[(i - 1) % n]
        p1 = control_points[i]
        p2 = control_points[(i + 1) % n]
        p3 = control_points[(i + 2) % n]
        for s in range(samples_per_segment):
            t = s / samples_per_segment
            points.append(_catmull_rom_point(p0, p1, p2, p3, t))
    return points


def compute_track_edges(centerline, width):
    """Compute inner and outer edge points from the centerline."""
    n = len(centerline)
    inner, outer = [], []
    half_w = width / 2
    for i in range(n):
        ni = (i + 1) % n
        dx = centerline[ni][0] - centerline[i][0]
        dy = centerline[ni][1] - centerline[i][1]
        length = math.hypot(dx, dy)
        if length < 0.001:
            continue
        nx = -dy / length
        ny = dx / length
        inner.append((centerline[i][0] + nx * half_w, centerline[i][1] + ny * half_w))
        outer.append((centerline[i][0] - nx * half_w, centerline[i][1] - ny * half_w))
    return inner, outer


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
class Camera:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.lerp = 0.08

    def update(self, tx, ty):
        self.x += (tx - self.x) * self.lerp
        self.y += (ty - self.y) * self.lerp

    def w2s(self, wx, wy):
        """World-to-screen coordinate conversion."""
        return (int(wx - self.x + SCREEN_WIDTH // 2),
                int(wy - self.y + SCREEN_HEIGHT // 2))


# ---------------------------------------------------------------------------
# Car (base class)
# ---------------------------------------------------------------------------
class Car:
    """Base car with physics."""

    def __init__(self, x, y, angle, color, name="Car"):
        self.x = x
        self.y = y
        self.angle = angle  # radians, 0 = right
        self.speed = 0.0
        self.color = color
        self.name = name

        # Physics tunables
        self.max_speed = 8.0
        self.accel = 0.15
        self.brake = 0.25
        self.steer_rate = 0.04
        self.friction = 0.985
        self.off_friction = 0.94
        self.off_max_speed = 3.0

        # Race state
        self.on_track = True
        self.current_wp = 0
        self.lap = 0
        self.progress = 0.0  # fractional [0,1) within current lap
        self.total_progress = 0.0  # lap + progress

    # -- polygon for drawing ------------------------------------------------
    _SHAPE = [
        (20, 0),
        (16, -5),
        (12, -7),
        (-14, -7),
        (-17, -9),
        (-20, -9),
        (-20, 9),
        (-17, 9),
        (-14, 7),
        (12, 7),
        (16, 5),
    ]

    def polygon(self):
        cos_a = math.cos(self.angle)
        sin_a = math.sin(self.angle)
        return [
            (px * cos_a - py * sin_a + self.x,
             px * sin_a + py * cos_a + self.y)
            for px, py in self._SHAPE
        ]

    # -- track awareness ----------------------------------------------------
    def check_on_track(self, centerline, track_width):
        half = track_width / 2
        min_d = float("inf")
        for pt in centerline:
            d = math.hypot(self.x - pt[0], self.y - pt[1])
            if d < min_d:
                min_d = d
        self.on_track = min_d < half
        return self.on_track

    def update_progress(self, centerline):
        n = len(centerline)
        min_d = float("inf")
        nearest = 0
        for i, pt in enumerate(centerline):
            d = (self.x - pt[0]) ** 2 + (self.y - pt[1]) ** 2
            if d < min_d:
                min_d = d
                nearest = i

        old_wp = self.current_wp
        self.current_wp = nearest
        self.progress = nearest / n

        # Lap detection
        if old_wp > n * 0.85 and nearest < n * 0.15:
            self.lap += 1
        elif old_wp < n * 0.15 and nearest > n * 0.85:
            self.lap = max(0, self.lap - 1)

        self.total_progress = self.lap + self.progress

    # -- drawing ------------------------------------------------------------
    def draw(self, surface, camera):
        pts = [camera.w2s(px, py) for px, py in self.polygon()]
        if not any(-60 < sx < SCREEN_WIDTH + 60 and -60 < sy < SCREEN_HEIGHT + 60
                   for sx, sy in pts):
            return
        pygame.draw.polygon(surface, self.color, pts)
        pygame.draw.polygon(surface, BLACK, pts, 2)
        # Cockpit dot
        cos_a = math.cos(self.angle)
        sin_a = math.sin(self.angle)
        cx, cy = camera.w2s(self.x + 3 * cos_a, self.y + 3 * sin_a)
        pygame.draw.circle(surface, DARK_GRAY, (cx, cy), 3)


# ---------------------------------------------------------------------------
# Player car
# ---------------------------------------------------------------------------
class PlayerCar(Car):
    def __init__(self, x, y, angle, color):
        super().__init__(x, y, angle, color, "Player")
        self.max_speed = 9.0
        self.accel = 0.18

    def handle_input(self, keys):
        # Throttle / brake
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.speed += self.accel
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            if self.speed > 0:
                self.speed -= self.brake
            else:
                self.speed -= self.accel * 0.3

        # Steering (more effect at higher speed, minimum at low speed)
        steer = min(1.0, abs(self.speed) / 3.0) * self.steer_rate
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.angle -= steer
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.angle += steer

        # Friction
        if self.on_track:
            self.speed *= self.friction
            cap = self.max_speed
        else:
            self.speed *= self.off_friction
            cap = self.off_max_speed

        self.speed = max(-2.0, min(cap, self.speed))

        # Move
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed


# ---------------------------------------------------------------------------
# AI car
# ---------------------------------------------------------------------------
class AICar(Car):
    def __init__(self, x, y, angle, color, name, track_points):
        super().__init__(x, y, angle, color, name)
        self.track_points = track_points
        self.base_max_speed = 7.0 + random.uniform(-0.5, 0.5)
        self.max_speed = self.base_max_speed
        self.skill = random.uniform(0.75, 1.0)
        self.wobble = random.uniform(0.0, 0.008)
        self.look_ahead = random.randint(8, 18)
        self.race_ticks = 0  # frames since race start (for rubber-band grace)

    def update(self, player_progress, all_ai=None):
        n = len(self.track_points)
        target_idx = (self.current_wp + self.look_ahead) % n
        target = self.track_points[target_idx]

        # Steer toward target waypoint
        desired = math.atan2(target[1] - self.y, target[0] - self.x)
        diff = desired - self.angle
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi

        steer = max(-self.steer_rate, min(self.steer_rate, diff * 0.1 * self.skill))

        # --- AI-to-AI avoidance ---
        # Nudge steering away from nearby AI cars to prevent pile-ups.
        if all_ai:
            avoid_radius = 60
            for other in all_ai:
                if other is self:
                    continue
                dx = other.x - self.x
                dy = other.y - self.y
                d = math.hypot(dx, dy)
                if 0 < d < avoid_radius:
                    # Angle from self to other car
                    to_other = math.atan2(dy, dx)
                    rel = to_other - self.angle
                    while rel > math.pi:
                        rel -= 2 * math.pi
                    while rel < -math.pi:
                        rel += 2 * math.pi
                    # Only avoid cars roughly ahead (within ±90°)
                    if abs(rel) < math.pi * 0.5:
                        strength = (avoid_radius - d) / avoid_radius * 0.04
                        # Steer away: if other is to the left (rel<0) steer right
                        if rel >= 0:
                            steer -= strength
                        else:
                            steer += strength

        self.angle += steer + random.uniform(-self.wobble, self.wobble)

        # --- Rubberbanding ---
        # Grace period: no rubber-banding for the first ~15 seconds so
        # the start is a fair race and the player must genuinely overtake.
        self.race_ticks += 1
        grace_period = 900  # 15 s at 60 fps
        rubber_strength = max(0.0, min(1.0, (self.race_ticks - grace_period) / 300))

        gap = player_progress - self.total_progress
        if gap > 0.3:
            boost = min(2.5, gap * 2.0) * rubber_strength
            self.max_speed = self.base_max_speed + boost
        elif gap < -0.3:
            penalty = min(1.5, abs(gap) * 0.9) * rubber_strength
            self.max_speed = self.base_max_speed - penalty
        else:
            self.max_speed = self.base_max_speed
        self.max_speed = max(4.0, self.max_speed)

        # Accelerate
        if self.speed < self.max_speed:
            self.speed += self.accel * self.skill

        # Friction
        if self.on_track:
            self.speed *= self.friction
        else:
            self.speed *= self.off_friction
            self.speed = min(self.speed, self.off_max_speed)
        self.speed = max(0, min(self.max_speed, self.speed))

        # Move
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed


# ---------------------------------------------------------------------------
# Car-to-car collisions
# ---------------------------------------------------------------------------
def resolve_collisions(cars):
    """Simple circle-based collision resolution."""
    min_dist = 28
    for i in range(len(cars)):
        for j in range(i + 1, len(cars)):
            dx = cars[j].x - cars[i].x
            dy = cars[j].y - cars[i].y
            d = math.hypot(dx, dy)
            if 0 < d < min_dist:
                overlap = min_dist - d
                nx = dx / d
                ny = dy / d
                cars[i].x -= nx * overlap * 0.5
                cars[i].y -= ny * overlap * 0.5
                cars[j].x += nx * overlap * 0.5
                cars[j].y += ny * overlap * 0.5
                cars[i].speed *= 0.92
                cars[j].speed *= 0.92


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.screen = pygame.display.get_surface()
        self.clock = pygame.time.Clock()
        self.font_xl = pygame.font.Font(None, 100)
        self.font_lg = pygame.font.Font(None, 48)
        self.font_md = pygame.font.Font(None, 36)
        self.font_sm = pygame.font.Font(None, 24)

        # Track
        self.centerline = generate_smooth_track(CONTROL_POINTS)
        self.inner, self.outer = compute_track_edges(self.centerline, TRACK_WIDTH)

        # Grid setup – F1-style grid just behind the start/finish line.
        # Waypoint 0 is the start/finish.  Cars are placed BEHIND it
        # (high indices) so they cross the line shortly after the start.
        n = len(self.centerline)
        grid_spacing = 8  # waypoint gap between grid slots

        # AI cars occupy the front grid rows (P1 closest to the line)
        self.ai_cars = []
        for i in range(NUM_AI):
            idx = (n - (i + 1) * grid_spacing) % n  # P1 at n-8, P2 at n-16 …
            ap = self.centerline[idx]
            nxt = self.centerline[(idx + 1) % n]
            aa = math.atan2(nxt[1] - ap[1], nxt[0] - ap[0])
            color, name = TEAM_COLORS[(i + 1) % len(TEAM_COLORS)]
            ai = AICar(ap[0], ap[1], aa, color, name, self.centerline)
            ai.current_wp = idx
            self.ai_cars.append(ai)

        # Player starts at the back of the grid (last slot, P6)
        player_idx = (n - (NUM_AI + 1) * grid_spacing) % n
        sp = self.centerline[player_idx]
        nxt = self.centerline[(player_idx + 1) % n]
        sa = math.atan2(nxt[1] - sp[1], nxt[0] - sp[0])
        self.player = PlayerCar(sp[0], sp[1], sa, TEAM_COLORS[0][0])
        self.player.current_wp = player_idx

        self.camera = Camera(sp[0], sp[1])

        # State
        self.state = "countdown"  # countdown | racing | finished
        self.countdown = 180  # 3 s
        self.race_time = 0
        self.positions = []

        # Pre-render track
        self._track_surf = None
        self._track_offset = (0.0, 0.0)
        self._prerender_track()

    # -- pre-render ---------------------------------------------------------
    def _prerender_track(self):
        all_pts = self.inner + self.outer
        min_x = min(p[0] for p in all_pts) - 80
        min_y = min(p[1] for p in all_pts) - 80
        max_x = max(p[0] for p in all_pts) + 80
        max_y = max(p[1] for p in all_pts) + 80
        w = int(max_x - min_x)
        h = int(max_y - min_y)
        self._track_offset = (min_x, min_y)
        surf = pygame.Surface((w, h))
        surf.fill(GRASS_COLOR)

        # Shift helper
        def s(pt):
            return (int(pt[0] - min_x), int(pt[1] - min_y))

        center_s = [s(p) for p in self.centerline]

        # Draw road as thick line segments + joint circles
        tw = int(TRACK_WIDTH)
        for i in range(len(center_s)):
            ni = (i + 1) % len(center_s)
            pygame.draw.line(surf, TRACK_COLOR, center_s[i], center_s[ni], tw)
        for p in center_s:
            pygame.draw.circle(surf, TRACK_COLOR, p, tw // 2)

        # Curbs on edges
        outer_s = [s(p) for p in self.outer]
        inner_s = [s(p) for p in self.inner]
        for i in range(0, len(outer_s) - 1, 4):
            color = CURB_RED if (i // 4) % 2 == 0 else CURB_WHITE
            pygame.draw.line(surf, color, outer_s[i], outer_s[i + 1], 4)
        for i in range(0, len(inner_s) - 1, 4):
            color = CURB_RED if (i // 4) % 2 == 0 else CURB_WHITE
            pygame.draw.line(surf, color, inner_s[i], inner_s[i + 1], 4)

        # Dashed center line
        for i in range(0, len(center_s) - 4, 8):
            pygame.draw.line(surf, (90, 90, 95), center_s[i], center_s[i + 3], 1)

        # Start / finish line
        if outer_s and inner_s:
            pygame.draw.line(surf, WHITE, outer_s[0], inner_s[0], 5)
            # Chequered pattern near start
            for k in range(0, 10, 2):
                sx = outer_s[0][0] + (inner_s[0][0] - outer_s[0][0]) * k / 10
                sy = outer_s[0][1] + (inner_s[0][1] - outer_s[0][1]) * k / 10
                pygame.draw.rect(surf, WHITE, (int(sx) - 3, int(sy) - 3, 6, 6))

        self._track_surf = surf

    # -- update -------------------------------------------------------------
    def update(self):
        if self.state == "countdown":
            self.countdown -= 1
            if self.countdown <= 0:
                self.state = "racing"
            self.camera.update(self.player.x, self.player.y)
            return

        if self.state == "finished":
            return

        self.race_time += 1

        # Player
        keys = pygame.key.get_pressed()
        self.player.handle_input(keys)
        self.player.check_on_track(self.centerline, TRACK_WIDTH)
        self.player.update_progress(self.centerline)

        # AI
        for ai in self.ai_cars:
            ai.update(self.player.total_progress, self.ai_cars)
            ai.check_on_track(self.centerline, TRACK_WIDTH)
            ai.update_progress(self.centerline)

        # Collisions
        resolve_collisions([self.player] + self.ai_cars)

        # Standings
        all_cars = [self.player] + self.ai_cars
        all_cars.sort(key=lambda c: c.total_progress, reverse=True)
        self.positions = all_cars

        # Check finish
        if self.player.lap >= NUM_LAPS:
            self.state = "finished"

        # Camera
        self.camera.update(self.player.x, self.player.y)

    # -- draw ---------------------------------------------------------------
    def draw(self):
        self.screen.fill(GRASS_COLOR)

        # Track surface
        if self._track_surf:
            ox, oy = self._track_offset
            sx = ox - self.camera.x + SCREEN_WIDTH // 2
            sy = oy - self.camera.y + SCREEN_HEIGHT // 2
            self.screen.blit(self._track_surf, (int(sx), int(sy)))

        # Cars (sorted for visual layering)
        all_cars = sorted([self.player] + self.ai_cars, key=lambda c: c.y)
        for car in all_cars:
            car.draw(self.screen, self.camera)

        # HUD
        self._draw_hud()

        # Overlays
        if self.state == "countdown":
            self._draw_countdown()
        elif self.state == "finished":
            self._draw_finish()

        pygame.display.flip()

    # -- HUD ----------------------------------------------------------------
    def _draw_hud(self):
        # Speed
        kmh = int(abs(self.player.speed) * 30)
        self._text(self.font_md, f"{kmh} km/h", WHITE, 20, SCREEN_HEIGHT - 50)

        # Gear-like speed bar
        bar_w = 150
        bar_h = 10
        bar_x = 20
        bar_y = SCREEN_HEIGHT - 25
        pygame.draw.rect(self.screen, DARK_GRAY, (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        fill = int(bar_w * min(1.0, abs(self.player.speed) / self.player.max_speed))
        bar_color = RED if kmh > 240 else YELLOW if kmh > 160 else GREEN
        pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, fill, bar_h), border_radius=4)

        # Lap
        display_lap = min(self.player.lap + 1, NUM_LAPS)
        self._text(self.font_md, f"Lap {display_lap}/{NUM_LAPS}", WHITE, 20, 20)

        # Position
        pos = self._player_position()
        self._text(self.font_lg, f"P{pos}", YELLOW, 20, 55)
        self._text(self.font_sm, f"of {len(self.positions)}", WHITE, 75, 72)

        # Time
        secs = self.race_time / FPS
        m, s = int(secs // 60), secs % 60
        self._text(self.font_sm, f"{m}:{s:05.2f}", WHITE, SCREEN_WIDTH - 110, 20)

        # Standings board
        bx = SCREEN_WIDTH - 185
        by = 48
        total = 1 + NUM_AI
        pygame.draw.rect(self.screen, HUD_BG,
                         (bx - 8, by - 4, 188, 26 + 22 * total),
                         border_radius=6)
        self._text(self.font_sm, "STANDINGS", YELLOW, bx, by)
        for i, car in enumerate(self.positions):
            label = "YOU" if car is self.player else car.name
            color = YELLOW if car is self.player else WHITE
            self._text(self.font_sm, f"P{i + 1}  {label}", color, bx, by + 22 + i * 22)

        # Mini-map
        self._draw_minimap()

    def _draw_minimap(self):
        sz = 150
        mx = SCREEN_WIDTH - sz - 15
        my = SCREEN_HEIGHT - sz - 15
        ms = pygame.Surface((sz, sz), pygame.SRCALPHA)
        pygame.draw.rect(ms, (0, 0, 0, 160), (0, 0, sz, sz), border_radius=8)

        pts = self.centerline
        lo_x = min(p[0] for p in pts)
        lo_y = min(p[1] for p in pts)
        hi_x = max(p[0] for p in pts)
        hi_y = max(p[1] for p in pts)
        scale = (sz - 20) / max(hi_x - lo_x, hi_y - lo_y)

        def m(wx, wy):
            return (int((wx - lo_x) * scale + 10), int((wy - lo_y) * scale + 10))

        mp = [m(p[0], p[1]) for p in pts]
        if len(mp) > 2:
            pygame.draw.lines(ms, GRAY, True, mp, 3)

        for ai in self.ai_cars:
            pygame.draw.circle(ms, ai.color, m(ai.x, ai.y), 3)
        pp = m(self.player.x, self.player.y)
        pygame.draw.circle(ms, self.player.color, pp, 4)
        pygame.draw.circle(ms, WHITE, pp, 4, 1)

        self.screen.blit(ms, (mx, my))

    # -- overlays -----------------------------------------------------------
    def _draw_countdown(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        self.screen.blit(overlay, (0, 0))

        n = self.countdown // 60 + 1
        if n > 3:
            n = 3
        txt = str(n) if self.countdown > 0 else "GO!"
        col = RED if self.countdown > 0 else GREEN
        surf = self.font_xl.render(txt, True, col)
        r = surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(surf, r)

    def _draw_finish(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        pos = self._player_position()
        if pos == 1:
            txt, col = "YOU WIN!", YELLOW
        else:
            txt, col = f"FINISHED P{pos}", WHITE

        surf = self.font_xl.render(txt, True, col)
        r = surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40))
        self.screen.blit(surf, r)

        secs = self.race_time / FPS
        m, s = int(secs // 60), secs % 60
        self._text_center(self.font_md, f"Time: {m}:{s:05.2f}", WHITE, SCREEN_HEIGHT // 2 + 20)
        self._text_center(self.font_sm, "Press R to restart  |  ESC to quit", WHITE, SCREEN_HEIGHT // 2 + 60)

    # -- helpers ------------------------------------------------------------
    def _player_position(self):
        for i, c in enumerate(self.positions):
            if c is self.player:
                return i + 1
        return 1

    def _text(self, font, text, color, x, y):
        self.screen.blit(font.render(text, True, color), (x, y))

    def _text_center(self, font, text, color, y):
        s = font.render(text, True, color)
        self.screen.blit(s, s.get_rect(center=(SCREEN_WIDTH // 2, y)))

    # -- main loop ----------------------------------------------------------
    def run(self):
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        running = False
                    if ev.key == pygame.K_r and self.state == "finished":
                        self.__init__()
            self.update()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    pygame.init()
    pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("F1 Top-Down Racing")
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
