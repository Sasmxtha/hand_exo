"""
game.py
Author: S. Sasmitha

PyGame 2.1.3 sorting game — the core of the rehabilitation platform.

Paper (Section III-C):
  - 60 FPS rendering, 5 lives, 10 pts correct / -1 life incorrect
  - Objects spawn randomly in non-overlapping positions
  - Spawn rate scales dynamically with player accuracy
  - AABB collision detection (eq. 3)
  - Dual-camera feed shown as overlays
  - Supports VISION mode (MediaPipe) and GLOVE mode (Arduino)
  - All session data written to MySQL after each game
"""

import sys
import time
import random
import argparse

import cv2
import pygame
import numpy as np

from src.config          import GAME
from src.gesture_recognition import GestureRecognizer
from src.object_tracker  import ObjectTracker
from src.voice_control   import VoiceController
from src.glove_controller import GloveController
from src.database        import DatabaseManager


# ── Game objects ──────────────────────────────────────────────────────────────

FRUIT_TYPES = [
    {"name": "apple",  "basket": 0, "color": GAME.RED},
    {"name": "grape",  "basket": 1, "color": GAME.PURPLE},
    {"name": "orange", "basket": 2, "color": GAME.YELLOW},
]


class FallingObject:
    W = H = 40

    def __init__(self, spawn_rate: float = 1.0):
        ft = random.choice(FRUIT_TYPES)
        self.name   = ft["name"]
        self.color  = ft["color"]
        self.basket = ft["basket"]   # correct basket index
        self.x      = float(random.randint(self.W, GAME.SCREEN_W - self.W))
        self.y      = 0.0
        self.speed  = 2.0 * spawn_rate
        self.rect   = pygame.Rect(int(self.x), 0, self.W, self.H)

    def update(self):
        self.y += self.speed
        self.rect.y = int(self.y)

    def draw(self, surf: pygame.Surface, font: pygame.font.Font):
        pygame.draw.ellipse(surf, self.color, self.rect)
        lbl = font.render(self.name[:3], True, GAME.WHITE)
        surf.blit(lbl, (self.rect.x + 2, self.rect.y - 14))


class Basket:
    def __init__(self, x: int, w: int, label: str, color):
        self.rect  = pygame.Rect(x, GAME.SCREEN_H - 90, w, 80)
        self.label = label
        self.color = color

    def draw(self, surf: pygame.Surface, font: pygame.font.Font):
        pygame.draw.rect(surf, self.color, self.rect, 3)
        lbl = font.render(self.label, True, self.color)
        surf.blit(lbl, (self.rect.x + 8, self.rect.y + 8))


class VirtualGlove:
    W = H = 60

    def __init__(self):
        self.x     = GAME.SCREEN_W // 2
        self.y     = GAME.SCREEN_H // 2
        self.state = "OPEN"
        self.rect  = pygame.Rect(0, 0, self.W, self.H)

    def update(self, x: int, y: int, state: str):
        self.x, self.y, self.state = x, y, state
        self.rect = pygame.Rect(x - self.W // 2, y - self.H // 2,
                                self.W, self.H)

    def draw(self, surf: pygame.Surface, font: pygame.font.Font):
        col = GAME.GREEN if self.state == "OPEN" else GAME.RED
        pygame.draw.rect(surf, col, self.rect, 2)
        lbl = font.render(self.state, True, col)
        surf.blit(lbl, (self.rect.x, self.rect.y - 18))


# ── AABB collision (paper eq. 3) ──────────────────────────────────────────────

def aabb(r1: pygame.Rect, r2: pygame.Rect) -> bool:
    """
    Axis-Aligned Bounding Box collision.

    Collision = True if
        |glove_x - obj_x| < (w_g + w_o) / 2  AND
        |glove_y - obj_y| < (h_g + h_o) / 2
    """
    return r1.colliderect(r2)


# ── Main game class ───────────────────────────────────────────────────────────

class SortingGame:
    """
    Multimodal sorting game — wires together all subsystems.

    VISION mode: gesture recognizer → virtual glove → game
    GLOVE  mode: Arduino glove  → virtual glove → game + haptic feedback
    """

    def __init__(self, player: str, mode: str = GAME.MODE_VISION):
        pygame.init()
        self.screen = pygame.display.set_mode((GAME.SCREEN_W, GAME.SCREEN_H))
        pygame.display.set_caption(
            "Hand Exoskeleton Sorting Game — S. Sasmitha"
        )
        self.clock    = pygame.time.Clock()
        self.font_lg  = pygame.font.SysFont("Arial", 26, bold=True)
        self.font_md  = pygame.font.SysFont("Arial", 18)
        self.font_sm  = pygame.font.SysFont("Arial", 13)

        self.player = player
        self.mode   = mode

        # Game state
        self.score      = 0
        self.lives      = GAME.LIVES
        self.hits       = 0
        self.misses     = 0
        self.running    = True
        self.spawn_rate = 1.0
        self._t_start   = time.time()
        self._t_spawn   = time.time()

        self._objects: list[FallingObject] = []
        self._held:    FallingObject | None = None
        self._glove    = VirtualGlove()
        self._baskets  = self._make_baskets()

        # Subsystems
        self._gesture = GestureRecognizer()
        self._tracker = ObjectTracker()
        self._voice   = VoiceController()
        self._db      = DatabaseManager()
        self._hw_glove: GloveController | None = (
            GloveController() if mode == GAME.MODE_GLOVE else None
        )

    # ── Setup ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_baskets():
        w = GAME.SCREEN_W // 3
        return [
            Basket(0,     w, "Apple",  GAME.RED),
            Basket(w,     w, "Grape",  GAME.PURPLE),
            Basket(w * 2, w, "Orange", GAME.YELLOW),
        ]

    # ── Main loop ──────────────────────────────────────────────────────────────

    def run(self):
        self._db.ensure_player(self.player)
        sid = self._db.start_session(self.player)

        try:
            while self.running:
                self._handle_events()
                self._update()
                self._draw()
                self.clock.tick(GAME.FPS)
        finally:
            dur = int(time.time() - self._t_start)
            acc = self.hits / (self.hits + self.misses) \
                  if (self.hits + self.misses) else 0.0
            self._db.end_session(sid, self.score, acc, dur)
            fb = self._db.get_adaptive_feedback(self.player)
            self._show_end_screen(acc, dur, fb)
            self._cleanup()

    # ── Events ─────────────────────────────────────────────────────────────────

    def _handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    self.running = False
                elif ev.key == pygame.K_SPACE:
                    self._emergency_stop()

        # Voice priority: last valid input wins (paper Section III-A)
        cmd = self._voice.get_latest_command()
        if cmd == "stop":
            self._emergency_stop()

    # ── Update ─────────────────────────────────────────────────────────────────

    def _update(self):
        # 1. Get hand input
        if self.mode == GAME.MODE_VISION:
            hx, hy, hstate = self._gesture.get_hand_state()
        else:
            hx, hy, hstate = self._hw_glove.get_hand_state()

        # 2. Update virtual glove
        self._glove.update(hx, hy, hstate)

        # 3. Mirror to physical glove
        if self._hw_glove:
            self._hw_glove.set_state(hstate)

        # 4. Spawn objects
        interval = GAME.SPAWN_SEC / self.spawn_rate
        if time.time() - self._t_spawn >= interval:
            self._objects.append(FallingObject(self.spawn_rate))
            self._t_spawn = time.time()

        # 5. Grab / drop with AABB
        if hstate == "CLOSED" and self._held is None:
            for obj in self._objects:
                if aabb(self._glove.rect, obj.rect):
                    self._held = obj
                    break

        if hstate == "OPEN" and self._held is not None:
            self._drop_held()

        if self._held:
            self._held.rect.center = (hx, hy)

        # 6. Update falling objects
        for obj in self._objects[:]:
            if obj is self._held:
                continue
            obj.update()
            for i, basket in enumerate(self._baskets):
                if aabb(obj.rect, basket.rect):
                    self._score_object(obj, i)
                    self._objects.remove(obj)
                    break
            else:
                if obj.y > GAME.SCREEN_H and obj in self._objects:
                    self._objects.remove(obj)
                    self.misses += 1
                    self.lives  -= 1

        # 7. Adaptive spawn rate (Section III-C)
        total = self.hits + self.misses
        if total:
            acc = self.hits / total
            if acc > 0.75:
                self.spawn_rate = min(GAME.SPAWN_MAX,
                                      self.spawn_rate + 0.010)
            elif acc < 0.50:
                self.spawn_rate = max(GAME.SPAWN_MIN,
                                      self.spawn_rate - 0.005)

        if self.lives <= 0:
            self.running = False

    def _score_object(self, obj: FallingObject, basket_idx: int):
        if obj.basket == basket_idx:
            self.score += GAME.POINTS
            self.hits  += 1
        else:
            self.lives  -= 1
            self.misses += 1

    def _drop_held(self):
        obj = self._held
        self._held = None
        for i, basket in enumerate(self._baskets):
            if aabb(obj.rect, basket.rect):
                self._score_object(obj, i)
                if obj in self._objects:
                    self._objects.remove(obj)
                return
        # not on a basket — keep falling
        if obj not in self._objects:
            self._objects.append(obj)

    # ── Draw ───────────────────────────────────────────────────────────────────

    def _draw(self):
        self.screen.fill(GAME.SKY)
        for basket in self._baskets:
            basket.draw(self.screen, self.font_md)
        for obj in self._objects:
            obj.draw(self.screen, self.font_sm)
        self._glove.draw(self.screen, self.font_sm)
        self._draw_hud()
        pygame.display.flip()

    def _draw_hud(self):
        lines = [
            f"Score: {self.score}",
            f"Lives: {self.lives}",
            f"Object: {'HELD' if self._held else 'FREE'}",
            f"Hand:  {self._glove.state}",
        ]
        for i, line in enumerate(lines):
            surf = self.font_md.render(line, True, GAME.BLACK)
            self.screen.blit(surf, (10, 10 + i * 28))

        mode_lbl = self.font_sm.render(f"Input: {self.mode}", True, GAME.BLACK)
        self.screen.blit(mode_lbl,
                         (GAME.SCREEN_W - mode_lbl.get_width() - 10, 10))

    # ── End screen ─────────────────────────────────────────────────────────────

    def _show_end_screen(self, acc: float, dur: int, feedback: str):
        self.screen.fill((15, 20, 35))
        lines = [
            ("GAME OVER", (56, 189, 248), 40),
            (f"Player   : {self.player}", (255, 255, 255), 22),
            (f"Score    : {self.score}",  (255, 255, 255), 22),
            (f"Accuracy : {acc*100:.1f}%", (52, 211, 153), 22),
            (f"Duration : {dur}s",        (255, 255, 255), 22),
            (feedback, (148, 163, 184), 16),
            ("Press ESC to exit", (100, 116, 139), 14),
        ]
        y = 160
        for text, col, sz in lines:
            f = pygame.font.SysFont("Arial", sz, bold=(sz > 20))
            s = f.render(text, True, col)
            self.screen.blit(s, (GAME.SCREEN_W // 2 - s.get_width() // 2, y))
            y += sz + 16
        pygame.display.flip()
        waiting = True
        while waiting:
            for ev in pygame.event.get():
                if ev.type in (pygame.QUIT, pygame.KEYDOWN):
                    waiting = False
            self.clock.tick(30)

    # ── Misc ───────────────────────────────────────────────────────────────────

    def _emergency_stop(self):
        if self._hw_glove:
            self._hw_glove.emergency_stop()
        self.running = False

    def _cleanup(self):
        self._gesture.release()
        self._tracker.release()
        self._voice.stop()
        if self._hw_glove:
            self._hw_glove.close()
        self._db.close()
        pygame.quit()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Hand Exoskeleton Sorting Game — S. Sasmitha"
    )
    ap.add_argument("--player", default="Player1")
    ap.add_argument("--mode",   default="VISION",
                    choices=["VISION", "GLOVE"])
    args = ap.parse_args()
    SortingGame(player=args.player, mode=args.mode).run()
