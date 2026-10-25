"""
GALAXIAN - a 2D arcade space shooter.
Python + Pygame (game)  +  MySQL (leaderboard, see database.py).

Run:   python galaxian.py
"""
import math
import random
import sys
import pygame

import database
from sounds import Sounds
 # ============================================================ SETTINGS
WIDTH, HEIGHT, FPS = 800, 600, 60
PLAY_TOP, PLAY_BOTTOM = 230, HEIGHT - 70     # the player can only move between these y values
MAX_HEALTH, START_LIVES = 100, 3
NO_LIFE_LOST_BONUS = 1000

BACKGROUND = (6, 6, 20)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
CYAN, PINK, YELLOW = (0, 230, 255), (255, 60, 200), (255, 225, 60)
RED, GREEN, ORANGE = (255, 70, 70), (80, 255, 120), (255, 150, 40)
PURPLE, GOLD, BLUE = (150, 90, 255), (255, 200, 40), (70, 140, 255)
GRAY = (150, 160, 175)

# --- the 4 ship configurations (upgrades keep for the rest of the run) ---
SHIPS = {
        1: {"name": "MK-I",   "cooldown": 0.35, "damage": 1, "speed": 280, "info": "Single laser"},
        2: {"name": "MK-II",  "cooldown": 0.22, "damage": 2, "speed": 280, "info": "Faster fire + stronger laser"},
        3: {"name": "MK-III", "cooldown": 0.22, "damage": 3, "speed": 340, "info": "Twin cannons + stronger laser + better handling"},
        4: {"name": "MK-IV",  "cooldown": 0.14, "damage": 3, "speed": 340, "info": "Triple spread shot + rapid fire"},
    }
SHIP_COLORS = {1: (CYAN, (0, 120, 200)), 2: (ORANGE, (200, 90, 20)),
                3: (GREEN, (30, 160, 70)), 4: (YELLOW, (230, 40, 200))}
UPGRADE_AT_START = {3: 2, 7: 4}       # level -> ship given when that level begins
UPGRADE_AFTER_LEVEL = {5: 3}          # level -> ship given after that level is won

    # --- waves: S = Self-destruct, L = Laser shooter, G = Golden perk mob, T = Attack tanker ---
LEVELS = {
        1: ["SSS", "SSSS", "SSSSS"],
        2: ["SSLL", "SSSLL", "SSSLLL"],
        3: ["SLLG", "SSLLL", "TSS"],
        4: ["SSLLL", "TLLG", "SSSSLL", "TTS"],
        5: ["SSLLT"],                                  # then boss VORLON
        6: ["TSSLL", "GSSSLLL", "TTLLL", "TSSSSLL"],
        7: ["TLLSSS", "TTGLL"],                        # then boss SENTINEL
    }
BOSS_LEVELS = {5: "VORLON", 7: "SENTINEL"}

BRIEFINGS = {
        1: ["Training sortie: move with arrows / WASD, shoot with SPACE.",
            "Threat: SELF-DESTRUCT drones lock on and dive at you. Keep moving!"],
        2: ["Bigger waves and faster attacks.",
            "Threat: LASER SHOOTERS fire beams from a safe distance."],
        3: ["Ship upgrade ahead: MK-II (faster, stronger lasers).",
            "Threat: GOLDEN PERK MOBS (shoot them for rewards) and ATTACK TANKERS."],
        4: ["Advanced formations and more projectiles.",
            "Tankers need sustained fire. Focus on them."],
        5: ["WARNING: mini-boss VORLON guards this sector.",
            "It lunges at you - dodge the strike! Reward: MK-III ship."],
        6: ["Elite fleet. Faster projectiles, heavy attack formations.",
            "Use your twin cannons and stay mobile."],
        7: ["FINAL LEVEL: the war machine SENTINEL awaits.",
            "MK-IV installed. It slams, sweeps and summons - end it!"],
    }

    # ============================================================ HELPERS
_fonts = {}


def text(surf, msg, size, color, x, y, center=True):
        """Draw plain text."""
        if size not in _fonts:
            _fonts[size] = pygame.font.Font(None, size)
        font = _fonts[size]
        if not msg:                          # an empty string cannot be rendered
            return
        img = font.render(msg, True, color)
        rect = img.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        surf.blit(img, rect)


def clamp(v, lo, hi):
        return max(lo, min(hi, v))


def aim_angle(x, y, tx, ty):
        """Angle from (x, y) to the target. 0 = straight down."""
        return math.atan2(tx - x, ty - y)


    # ============================================================ SMALL EFFECT CLASSES
class Starfield:
        """Scrolling stars in 3 layers (slow = far away, fast = close)."""

        def __init__(self):
            self.stars = [[random.randint(0, WIDTH), random.randint(0, HEIGHT),
                        random.choice([40, 90, 170])] for _ in range(90)]

        def update(self, dt):
            for s in self.stars:
                s[1] += s[2] * dt
                if s[1] > HEIGHT:
                    s[0], s[1] = random.randint(0, WIDTH), 0

        def draw(self, surf):
            for x, y, speed in self.stars:
                shade = 80 + speed
                size = 1 if speed < 100 else 2
                pygame.draw.rect(surf, (shade, shade, 255), (x, y, size, size))


class Particle:
        """One spark of an explosion."""

        def __init__(self, x, y, color, speed, life, size):
            angle = random.uniform(0, 2 * math.pi)
            s = random.uniform(0.3, 1.0) * speed
            self.x, self.y = x, y
            self.vx, self.vy = math.cos(angle) * s, math.sin(angle) * s
            self.life = self.max_life = life * random.uniform(0.6, 1.0)
            self.color, self.size = color, size

        def update(self, dt):
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.vx *= 0.98
            self.vy *= 0.98
            self.life -= dt

        def draw(self, surf):
            r = max(1, int(self.size * self.life / self.max_life))
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r)


class FloatText:
        """Text that floats upwards and fades away (+100, SHIELD, ...)."""

        def __init__(self, msg, x, y, color):
            self.msg, self.x, self.y, self.color, self.life = msg, x, y, color, 1.2

        def update(self, dt):
            self.y -= 40 * dt
            self.life -= dt

        def draw(self, surf):
            text(surf, self.msg, 26, self.color, self.x, self.y)


class Ring:
        """Expanding shockwave ring (kamikaze blasts and boss slams). Its size shows the damage radius."""

        def __init__(self, x, y, radius, color, life=0.45):
            self.x, self.y, self.max_r, self.color = x, y, radius, color
            self.life = self.max_life = life

        def update(self, dt):
            self.life -= dt

        def draw(self, surf):
            k = 1 - self.life / self.max_life
            shade = tuple(int(c * (1 - k * 0.7)) for c in self.color)
            pygame.draw.circle(surf, shade, (int(self.x), int(self.y)), max(2, int(self.max_r * k)), 3)


class Bullet:
        """Used for both player lasers (laser=True) and enemy orbs."""

        def __init__(self, x, y, vx, vy, damage, color, radius=5, laser=False):
            self.x, self.y, self.vx, self.vy = x, y, vx, vy
            self.damage, self.color, self.radius, self.laser = damage, color, radius, laser
            self.dead = False

        def update(self, dt):
            self.x += self.vx * dt
            self.y += self.vy * dt

        def off_screen(self):
            return not (-30 < self.x < WIDTH + 30 and -30 < self.y < HEIGHT + 30)

        def rect(self):
            if self.laser:
                return pygame.Rect(self.x - 3, self.y - 12, 6, 24)
            r = self.radius
            return pygame.Rect(self.x - r, self.y - r, 2 * r, 2 * r)

        def draw(self, surf):
            if self.laser:
                pygame.draw.rect(surf, self.color, self.rect(), border_radius=3)
                pygame.draw.rect(surf, WHITE, (self.x - 1, self.y - 10, 2, 20))
            else:
                pos = (int(self.x), int(self.y))
                pygame.draw.circle(surf, tuple(c // 2 for c in self.color), pos, self.radius + 3, 2)
                pygame.draw.circle(surf, self.color, pos, self.radius)
                pygame.draw.circle(surf, WHITE, pos, max(1, self.radius // 2))


    # ============================================================ PERK PICKUPS
PERKS = {"health": (GREEN, "+", "+30 HEALTH"), "rapid": (ORANGE, "R", "RAPID FIRE 8s"), "shield": (BLUE, "S", "SHIELD 6s"),
            "bomb": (RED, "B", "SMART BOMB!"), "life": (PINK, "1UP", "EXTRA LIFE!")}


class Pickup:
        """Falls from a dead enemy / boss. Fly into it to collect the perk."""

        def __init__(self, x, y, kind):
            self.x, self.y, self.kind, self.t, self.dead = x, y, kind, 0.0, False

        def update(self, dt):
            self.t += dt
            self.y += 90 * dt
            self.x = clamp(self.x + math.sin(self.t * 3) * 30 * dt, 20, WIDTH - 20)
            self.dead = self.y > PLAY_BOTTOM + 40

        def rect(self):
            return pygame.Rect(self.x - 15, self.y - 15, 30, 30)

        def draw(self, surf):
            col, ch, _ = PERKS[self.kind]
            pygame.draw.circle(surf, tuple(c // 4 for c in col), (int(self.x), int(self.y)), 15)
            pygame.draw.circle(surf, col, (int(self.x), int(self.y)), 15 + int(2 * math.sin(self.t * 8)), 2)
            text(surf, ch, 22, col, self.x, self.y)


    # ============================================================ PLAYER
def draw_player_ship(surf, x, y, mk, scale=1.0, t=0.0):
        """Draw the ship. Each upgrade (mk 1-4) has its own colours, wings and cannons."""
        main, accent = SHIP_COLORS[mk]

        def pts(*p):
            return [(x + a * scale, y + b * scale) for a, b in p]

        wing = 14 + 5 * (mk - 1)                     # wings grow with every upgrade
        if mk == 4:                                  # golden aura for the final ship
            pygame.draw.circle(surf, (120, 90, 20), (int(x), int(y)), int(36 * scale), 2)
        flame = 10 + 5 * math.sin(t * 30)
        pygame.draw.polygon(surf, ORANGE, pts((-6, 12), (6, 12), (0, 12 + flame)))
        pygame.draw.polygon(surf, YELLOW, pts((-3, 12), (3, 12), (0, 8 + flame / 2)))
        for s in (-1, 1):
            pygame.draw.polygon(surf, accent, pts((s * 6, -4), (s * (10 + wing), 16),
                                                (s * (10 + wing), 23), (s * 6, 14)))
            if mk >= 3:                              # side cannons
                pygame.draw.rect(surf, GRAY, (x + s * (wing + 6) * scale - 2 * scale,
                                            y - 12 * scale, 4 * scale, 18 * scale))
        if mk == 4:                                  # centre cannon
            pygame.draw.rect(surf, GRAY, (x - 2 * scale, y - 36 * scale, 4 * scale, 12 * scale))
        pygame.draw.polygon(surf, main, pts((0, -28), (9, -4), (11, 14), (0, 9), (-11, 14), (-9, -4)))
        pygame.draw.circle(surf, WHITE, (int(x), int(y - 8 * scale)), max(2, int(4 * scale)))


class Player:
        def __init__(self):
            self.x, self.y = WIDTH / 2, PLAY_BOTTOM
            self.ship = 1
            self.health, self.lives = MAX_HEALTH, START_LIVES
            self.cooldown = self.invuln = self.rapid = self.shield = self.t = 0.0
            self.lost_this_level = 0          # lives lost in the current level (for the bonus)

        def rect(self):
            return pygame.Rect(self.x - 14, self.y - 16, 28, 32)

        def update(self, dt, keys, game):
            cfg = SHIPS[self.ship]
            dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
            dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
            if dx and dy:
                dx, dy = dx * 0.707, dy * 0.707
            self.x = clamp(self.x + dx * cfg["speed"] * dt, 25, WIDTH - 25)
            self.y = clamp(self.y + dy * cfg["speed"] * dt, PLAY_TOP, PLAY_BOTTOM)
            self.t += dt
            self.cooldown -= dt
            self.invuln = max(0, self.invuln - dt)
            self.rapid = max(0, self.rapid - dt)
            self.shield = max(0, self.shield - dt)
            if keys[pygame.K_SPACE] and self.cooldown <= 0:
                self.shoot(game)

        def shoot(self, game):
            cfg = SHIPS[self.ship]
            self.cooldown = cfg["cooldown"] * (0.5 if self.rapid > 0 else 1)
            # (x offset, sideways speed) for every laser fired
            if self.ship <= 2:
                shots = [(0, 0)]
            elif self.ship == 3:
                shots = [(-12, 0), (12, 0)]                  # double cannons
            else:
                shots = [(0, 0), (-10, -160), (10, 160)]     # triple spread shot
            for ox, vx in shots:
                game.player_bullets.append(Bullet(self.x + ox, self.y - 26, vx, -650,
                                                cfg["damage"], SHIP_COLORS[self.ship][0], laser=True))
            game.sounds.play("shoot")

        def take_damage(self, amount, game):
            if self.invuln > 0:
                return
            if self.shield > 0:                              # shield blocks the hit
                self.invuln = 0.2
                game.sounds.play("hit")
                return
            self.health -= amount
            self.invuln = 1.0
            game.sounds.play("hit")
            game.shake = 0.15 + amount / 150                 # bigger hit = bigger shake
            game.hurt = 0.3
            game.explode(self.x, self.y, ORANGE, 8)
            if self.health <= 0:                             # lose a life
                self.lives -= 1
                self.lost_this_level += 1
                self.health = MAX_HEALTH
                self.invuln = 2.5                            # safe time after respawn
                game.enemy_bullets.clear()
                game.explode(self.x, self.y, CYAN, 35)
                game.sounds.play("explosion")
                game.shake = 0.3

        def draw(self, surf):
            if self.invuln > 0 and int(self.t * 12) % 2:     # blink while invulnerable
                return
            draw_player_ship(surf, self.x, self.y, self.ship, 1.0, self.t)
            if self.shield > 0:
                pygame.draw.circle(surf, BLUE, (int(self.x), int(self.y)), 32, 2)


    # ============================================================ ENEMIES
class Enemy:
        """Base class. The four enemy types below inherit from it."""
        kind, score, w, h, color = "enemy", 0, 40, 40, WHITE

        def __init__(self, x, y, hp):
            self.x, self.y = x, y
            self.hp = self.max_hp = hp
            self.alive = True
            self.flash = 0.0                 # white flash when hit
            self.t = 0.0

        def rect(self):
            return pygame.Rect(self.x - self.w / 2, self.y - self.h / 2, self.w, self.h)

        def hit(self, damage):
            self.hp -= damage
            self.flash = 0.08

        def tick(self, dt):
            self.t += dt
            self.flash = max(0, self.flash - dt)

        def tint(self, color):
            return WHITE if self.flash > 0 else color


BLAST_RADIUS, BLAST_DAMAGE = 130, 30          # kamikaze explosion (twice the old radius)


class SelfDestruct(Enemy):
        """Kamikaze: drifts in, shakes while it locks on (warning!), accelerates and explodes in a BIG blast."""
        kind, score, w, h, color = "selfdestruct", 100, 34, 34, RED

        def __init__(self, x, level):
            super().__init__(x, -30, 2)
            self.state, self.speed, self.lock = "enter", 120, 0.6
            self.wait = random.uniform(0.5, 7)           # random delay before it may attack (max 7 s)

        def update(self, dt, game):
            self.tick(dt)
            p = game.player
            if self.state == "enter":
                self.y += 90 * dt
                self.x += math.sin(self.t * 3) * 40 * dt
                if self.y > 80 or self.t > 1.3:
                    self.state = "wait"
            elif self.state == "wait":                       # hovers; attacks only when timer ends AND no other kamikaze is attacking
                self.wait -= dt
                self.x += math.sin(self.t * 3) * 30 * dt
                if self.wait <= 0 and not any(o is not self and o.kind == "selfdestruct" and o.state in ("lock", "dive")
                                            for o in game.enemies):
                    self.state = "lock"
            elif self.state == "lock":                       # shakes: the player has 0.6 s to run
                self.lock -= dt
                self.x += random.uniform(-3, 3)
                if self.lock <= 0:
                    self.state = "dive"
                    self.tx = p.x + random.randint(-30, 30)  # approximate position
                    self.ty = p.y + random.randint(-30, 30)
            else:
                self.speed += 380 * dt                       # accelerate
                dx, dy = self.tx - self.x, self.ty - self.y
                dist = math.hypot(dx, dy) or 1
                self.x += dx / dist * self.speed * dt
                self.y += dy / dist * self.speed * dt
                if dist < 15 or self.y > HEIGHT + 20 or math.hypot(p.x - self.x, p.y - self.y) < 40:
                    self.explode(game)

        def explode(self, game):
            self.alive = False                               # no points for a self-destruct
            game.explode(self.x, self.y, ORANGE, 45, 330)
            game.rings.append(Ring(self.x, self.y, BLAST_RADIUS, ORANGE))
            game.sounds.play("explosion")
            game.shake = 0.3
            if math.hypot(game.player.x - self.x, game.player.y - self.y) < BLAST_RADIUS:
                game.player.take_damage(BLAST_DAMAGE, game)

        def draw(self, surf):
            x, y = int(self.x), int(self.y)
            if self.state in ("lock", "dive"):               # faint preview of the blast radius
                pygame.draw.circle(surf, (110, 30, 30), (x, y), BLAST_RADIUS, 1)
            rate = 14 if self.state in ("lock", "dive") else 4
            glow = int(120 + 120 * abs(math.sin(self.t * rate)))
            body = [(x, y - 20), (x + 8, y - 6), (x + 20, y), (x + 8, y + 6),
                    (x, y + 20), (x - 8, y + 6), (x - 20, y), (x - 8, y - 6)]
            pygame.draw.polygon(surf, self.tint((190, 30, 40)), body)
            pygame.draw.polygon(surf, RED, body, 2)
            pygame.draw.circle(surf, (255, glow, 0), (x, y), 6)


class LaserShooter(Enemy):
        """Keeps its distance, moves sideways/diagonally and fires lasers at intervals."""
        kind, score, w, h, color = "shooter", 150, 46, 30, PURPLE

        def __init__(self, x, level):
            super().__init__(x, -30, int(6 * (1 + 0.1 * (level - 1))))
            self.dir = random.choice([-1, 1])
            self.target_y = random.randint(70, 190)
            self.arrived = False
            self.cooldown = max(0.9, 1.7 - 0.1 * level)
            self.shoot_timer = random.uniform(0.5, self.cooldown)

        def update(self, dt, game):
            self.tick(dt)
            if not self.arrived:                             # fly in from the top
                self.y += 110 * dt
                self.arrived = self.y >= self.target_y
                return
            self.x += self.dir * 85 * dt                     # horizontal ...
            self.y += math.sin(self.t * 2.5) * 50 * dt       # ... plus a wave = diagonal movement
            if game.player.y - self.y < 220:                 # player too close: back off
                self.y -= 70 * dt
            self.y = clamp(self.y, 40, 260)
            if self.x < 30 or self.x > WIDTH - 30:
                self.dir = -self.dir
                self.x = clamp(self.x, 30, WIDTH - 30)
            self.shoot_timer -= dt
            if self.shoot_timer <= 0:
                self.shoot_timer = self.cooldown
                count = 2 if game.level >= 6 else 1
                game.fire_fan(self.x, self.y + 15, count, 10, 280, 10, 5, PINK, aimed=game.level >= 4)

        def draw(self, surf):
            x, y = int(self.x), int(self.y)
            pygame.draw.rect(surf, GRAY, (x - 4, y + 6, 8, 14))                     # gun
            pygame.draw.ellipse(surf, self.tint((130, 60, 210)), (x - 23, y - 8, 46, 20))
            pygame.draw.ellipse(surf, PURPLE, (x - 23, y - 8, 46, 20), 2)
            pygame.draw.ellipse(surf, (120, 255, 255), (x - 10, y - 16, 20, 14))     # dome
            for dx in (-14, 0, 14):                                                 # blinking lights
                on = int(self.t * 6 + dx) % 2
                pygame.draw.circle(surf, YELLOW if on else (90, 70, 20), (x + dx, y + 3), 2)


class GoldenPerk(Enemy):
        """Rare golden ship that flies across the screen. Destroy it for a reward."""
        kind, score, w, h, color = "golden", 300, 42, 30, GOLD

        def __init__(self, x, level):
            side = random.choice([-1, 1])
            super().__init__(-40 if side == 1 else WIDTH + 40, random.randint(90, 200), 8)
            self.vx = side * 170
            self.base_y = self.y

        def update(self, dt, game):
            self.tick(dt)
            self.x += self.vx * dt
            self.y = self.base_y + math.sin(self.t * 3) * 50
            if random.random() < 0.3:
                game.sparkle(self.x, self.y)
            if self.x < -70 or self.x > WIDTH + 70:          # got away
                self.alive = False

        def draw(self, surf):
            x, y = int(self.x), int(self.y)
            glow = 24 + 4 * math.sin(self.t * 8)
            pygame.draw.circle(surf, (110, 80, 10), (x, y), int(glow + 8), 2)        # golden glow
            pygame.draw.circle(surf, (200, 150, 20), (x, y), int(glow), 2)
            pygame.draw.ellipse(surf, self.tint(GOLD), (x - 21, y - 8, 42, 20))
            pygame.draw.ellipse(surf, (255, 245, 160), (x - 12, y - 15, 24, 15))
            pygame.draw.ellipse(surf, (255, 255, 255), (x - 21, y - 8, 42, 20), 2)


class AttackTanker(Enemy):
        """Big, slow and tough. Fires wide spreads of heavy shots. Shows damage as it loses HP."""
        kind, score, w, h, color = "tanker", 500, 90, 64, (120, 140, 170)

        def __init__(self, x, level):
            super().__init__(x, -50, int(60 * (1 + 0.1 * (level - 1))))
            self.dir = random.choice([-1, 1])
            self.cooldown = max(1.3, 2.3 - 0.1 * level)
            self.shoot_timer = self.cooldown

        def update(self, dt, game):
            self.tick(dt)
            if self.y < 110:
                self.y += 40 * dt
            self.x += self.dir * 50 * dt
            if self.x < 60 or self.x > WIDTH - 60:
                self.dir = -self.dir
                self.x = clamp(self.x, 60, WIDTH - 60)
            ratio = self.hp / self.max_hp
            if ratio < 0.5 and random.random() < 0.2:        # smoke from a damaged ship
                game.explode(self.x + random.randint(-30, 30), self.y, GRAY, 1, 30)
            self.shoot_timer -= dt
            if self.shoot_timer <= 0 and self.y > 60:
                self.shoot_timer = self.cooldown
                count = 5 if game.level >= 5 else 3
                game.fire_fan(self.x, self.y + 30, count, 50, 200, 15, 8, ORANGE)

        def draw(self, surf):
            x, y = int(self.x), int(self.y)
            ratio = self.hp / self.max_hp
            hull = [(x - 45, y - 10), (x - 25, y - 32), (x + 25, y - 32), (x + 45, y - 10),
                    (x + 35, y + 28), (x - 35, y + 28)]
            pygame.draw.polygon(surf, self.tint((70, 80, 105)), hull)
            pygame.draw.polygon(surf, self.color, hull, 3)
            pygame.draw.rect(surf, self.tint((95, 110, 140)), (x - 24, y - 22, 48, 26))   # armour plate
            for dx in (-30, 0, 30):                                                      # cannons
                pygame.draw.rect(surf, ORANGE, (x + dx - 4, y + 22, 8, 12))
            if ratio < 0.66:                                                              # damage stages
                pygame.draw.line(surf, RED, (x - 20, y - 28), (x - 5, y - 5), 2)
                pygame.draw.line(surf, RED, (x + 25, y - 20), (x + 10, y + 5), 2)
            if ratio < 0.33:
                pygame.draw.line(surf, ORANGE, (x - 35, y + 10), (x - 10, y + 24), 3)
                pygame.draw.circle(surf, (255, 120, 0), (x + 20, y + 8), 7)
            bar = int(60 * ratio)                                                         # small health bar
            pygame.draw.rect(surf, (60, 20, 20), (x - 30, y - 42, 60, 5))
            pygame.draw.rect(surf, GREEN if ratio > 0.33 else RED, (x - 30, y - 42, bar, 5))


    # ============================================================ BOSSES
class Boss:
        """Base class for VORLON and SENTINEL. hp counts HITS (each laser = 1 hit)."""
        name, score, w, h, max_hp = "BOSS", 0, 150, 100, 100

        touch = 25                           # damage when the player rams the boss

        def touch_damage(self):
            return self.touch

        def __init__(self, start_y):
            self.x, self.y = WIDTH / 2, start_y
            self.hp = self.max_hp
            self.alive = True
            self.entering = True             # invulnerable while flying in
            self.flash = self.t = 0.0

        def rect(self):
            return pygame.Rect(self.x - self.w / 2, self.y - self.h / 2, self.w, self.h)

        def hit(self):
            self.hp -= 1
            self.flash = 0.06

        @property
        def stage(self):                     # 0 = healthy, 1 = damaged, 2 = critical
            ratio = self.hp / self.max_hp
            return 0 if ratio > 0.66 else (1 if ratio > 0.33 else 2)

        def tick(self, dt):
            self.t += dt
            self.flash = max(0, self.flash - dt)


class Vorlon(Boss):
        """Mini-boss. Attacks: spread, aimed volley, charge->laser burst, charge->dive-and-fire and the
        STRIKE: it locks on and lunges at the player for huge damage. Faster and angrier as it is hurt."""
        name, score, w, h, max_hp = "VORLON", 2500, 150, 100, 120
        touch = 35

        def __init__(self):
            super().__init__(-120)
            self.dir, self.mode, self.mode_time = 1, "move", 0.0
            self.attack_timer, self.fire_timer = 1.6, 0.0
            self.shots, self.after, self.last = 0, "", ""
            self.vx = self.vy = 0.0

        def touch_damage(self):
            return 65 if self.mode == "strike" else self.touch      # a strike hits very hard

        def go(self, mode):
            self.mode, self.mode_time, self.fire_timer, self.shots = mode, 0.0, 0.0, 7

        def start_attack(self, game, frac):
            attack = random.choice([a for a in ("spread", "aimed", "burst", "dive", "strike", "ring") if a != self.last])
            self.last = attack
            if attack == "spread":
                game.fire_fan(self.x, self.y + 50, 11 if frac <= 0.5 else 9, 90, 250, 11, 6, PINK)
            elif attack == "aimed":
                game.fire_fan(self.x, self.y + 50, 7 if frac <= 0.5 else 5, 30, 360, 12, 5, YELLOW, aimed=True)
            elif attack == "ring":
                game.fire_ring(self.x, self.y + 50, 16 if frac > 0.5 else 22, 200, 11, 6, ORANGE, random.randint(0, 20))
            elif attack == "strike":
                self.go("strike_warn")
            else:
                self.after = attack
                self.go("charge")

        def update(self, dt, game):
            self.tick(dt)
            p = game.player
            if self.entering:
                self.y += 90 * dt
                if self.y >= 100:
                    self.y, self.entering = 100, False
                return
            frac = self.hp / self.max_hp
            self.mode_time += dt
            m = self.mode
            if m == "move":
                self.x += self.dir * 170 * (2 - frac) * dt          # "escape mode": faster after damage
                if self.x < 100 or self.x > WIDTH - 100:
                    self.dir = -self.dir
                    self.x = clamp(self.x, 100, WIDTH - 100)
                if frac <= 0.5:                                     # enraged: shoots while moving
                    self.fire_timer -= dt
                    if self.fire_timer <= 0:
                        self.fire_timer = 0.7
                        game.fire_fan(self.x, self.y + 50, 1, 0, 360, 10, 5, RED, aimed=True)
                self.attack_timer -= dt
                if self.attack_timer <= 0:                          # angrier as health drops
                    self.attack_timer = 0.35 if frac <= 0.25 else (0.7 if frac <= 0.5 else 1.1)
                    self.start_attack(game, frac)
            elif m == "charge":                                     # glows and shakes: a warning
                if self.mode_time > 0.55:
                    self.go(self.after)
            elif m == "burst":                                      # rapid aimed lasers
                self.fire_timer -= dt
                if self.fire_timer <= 0:
                    self.fire_timer, self.shots = 0.11, self.shots - 1
                    game.fire_fan(self.x, self.y + 50, 1, 0, 420, 12, 5, RED, aimed=True)
                    if self.shots <= 0:
                        self.go("move")
            elif m == "dive":                                       # rush down while firing
                self.y += 330 * dt
                self.fire_timer -= dt
                if self.fire_timer <= 0:
                    self.fire_timer = 0.25
                    game.fire_fan(self.x, self.y + 50, 3, 30, 240, 10, 5, PINK)
                if self.y >= 320:
                    self.go("return")
            elif m == "strike_warn":                                # shakes and tracks the player
                self.x += random.uniform(-4, 4) + clamp(p.x - self.x, -1, 1) * 140 * dt
                if self.mode_time > 0.5:
                    dx, dy = p.x - self.x, p.y - self.y
                    dist = math.hypot(dx, dy) or 1
                    self.vx, self.vy = dx / dist * 820, dy / dist * 820
                    self.go("strike")
            elif m == "strike":                                     # the lunge
                self.x = clamp(self.x + self.vx * dt, 60, WIDTH - 60)
                self.y += self.vy * dt
                if self.y >= min(HEIGHT - 40, p.y + 90) or self.mode_time > 1.2:
                    self.go("return")
            else:                                                   # fly back up
                self.y -= 260 * dt
                self.x += (WIDTH / 2 - self.x) * min(1, 1.5 * dt)
                if self.y <= 100:
                    self.y = 100
                    self.go("move")

        def draw(self, surf):
            x, y, stage = int(self.x), int(self.y), self.stage
            if self.mode in ("charge", "strike_warn"):
                x += random.randint(-3, 3)
            if self.mode in ("strike_warn", "strike"):                    # red danger aura
                pygame.draw.circle(surf, (170, 30, 30), (x, y), 85 + int(8 * math.sin(self.t * 25)), 4)
            body = WHITE if self.flash > 0 else (85, 70, 200)             # blue-purple body
            pulse = int(150 + 100 * math.sin(self.t * 6))
            reach = 70 if stage < 2 else 48                               # wings get shorter when critical
            for s in (-1, 1):                                             # red energy wings
                pygame.draw.polygon(surf, (pulse, 30, 40), [
                    (x + s * 30, y - 20), (x + s * (30 + reach), y - 48),
                    (x + s * (15 + reach), y + 5), (x + s * (reach), y + 38), (x + s * 30, y + 20)])
            hull = [(x - 45, y - 32), (x + 45, y - 32), (x + 62, y), (x + 36, y + 46), (x - 36, y + 46), (x - 62, y)]
            pygame.draw.polygon(surf, body, hull)
            pygame.draw.polygon(surf, (45, 30, 120), hull, 3)
            for dx in (-30, 30):                                          # cannons
                pygame.draw.rect(surf, GRAY, (x + dx - 5, y + 40, 10, 16))
            core = 14 + 3 * math.sin(self.t * 6)
            if self.mode == "charge":
                core = 14 + 16 * min(1, self.mode_time / 0.8)             # core grows while charging
            pygame.draw.circle(surf, (255, 255, 120), (x, y), int(core + 5), 2)
            pygame.draw.circle(surf, YELLOW, (x, y), int(core))
            if stage >= 1:                                                # damage stage 1: cracks
                pygame.draw.line(surf, BLACK, (x - 40, y - 28), (x - 15, y - 5), 3)
                pygame.draw.line(surf, BLACK, (x + 38, y - 25), (x + 18, y + 15), 3)
            if stage >= 2:                                                # damage stage 2: fire + sparks
                pygame.draw.circle(surf, (255, 120, 0), (x - 38, y + 22), 9)
                pygame.draw.line(surf, ORANGE, (x + 10, y + 40), (x + 40, y + 10), 4)
                pygame.draw.circle(surf, RED, (x + 45, y - 5), 6)


    # what the Sentinel fires in each phase: seconds between attacks (None = not used)
SENTINEL_ATTACKS = {
        1: {"heavy": 1.5, "aim": 1.0, "fan": 2.8, "shell": None, "ring": None},
        2: {"heavy": 1.8, "aim": 0.8, "fan": 1.2, "shell": 2.2, "ring": 4.0},
        3: {"heavy": 1.2, "aim": 0.5, "fan": 0.8, "shell": 1.6, "ring": 1.9},
    }
SPECIAL_INTERVAL = {1: 4.5, 2: 3.4, 3: 2.2}


class Sentinel(Boss):
        """Final boss. 3 phases. Always-on guns get nastier each phase, plus special moves:
        BULLET WALL (with a gap), rotating SWEEP beam, ground SLAM + shockwave (phase 2+)
        and SUMMON kamikaze drones (phase 3)."""
        name, score, w, h, max_hp = "SENTINEL", 10000, 260, 160, 500
        touch = 40

        def __init__(self):
            super().__init__(-200)
            self.angle = self.recoil = self.mode_time = self.sweep_t = self.wall_t = 0.0
            self.timers = {k: 1.0 + 0.4 * i for i, k in enumerate(("heavy", "aim", "fan", "shell", "ring"))}
            self.last_phase, self.mode, self.last_special = 1, "fight", ""
            self.special_timer, self.wall_left = 5.0, 0

        @property
        def phase(self):
            return self.stage + 1

        def touch_damage(self):
            return 60 if self.mode in ("slam_down", "slam_up") else self.touch

        def go(self, mode):
            self.mode, self.mode_time = mode, 0.0

        def update(self, dt, game):
            self.tick(dt)
            self.recoil = max(0, self.recoil - dt)
            if self.entering:                                 # slow cinematic entrance with a rumble
                self.y += 55 * dt
                game.shake = max(game.shake, 0.08)
                if self.y >= 120:
                    self.y, self.entering = 120, False
                    game.shake = 0.5
                    game.sounds.play("explosion")
                return
            if self.phase != self.last_phase:                 # a new phase begins
                self.last_phase = self.phase
                game.shake = 0.4
                game.float_text("PHASE %d%s" % (self.phase, " - ENRAGED!" if self.phase == 3 else ""),
                                WIDTH / 2, 300, RED)
            p, ph, m = game.player, self.phase, self.mode
            self.mode_time += dt
            if m == "fight":
                self.angle += (0.8, 1.1, 1.6)[ph - 1] * dt
                self.x = WIDTH / 2 + math.sin(self.angle) * 220
                self.y = 120
                for attack, interval in SENTINEL_ATTACKS[ph].items():
                    if interval is None:
                        continue
                    self.timers[attack] -= dt
                    if self.timers[attack] <= 0:
                        self.timers[attack] = interval
                        self.attack(attack, game)
                self.wall_t -= dt                             # rows of bullets with a gap near the player
                if self.wall_left > 0 and self.wall_t <= 0:
                    self.wall_left, self.wall_t = self.wall_left - 1, 0.55
                    for x in range(25, WIDTH, 50):
                        if abs(x - p.x) > 60:
                            game.enemy_bullets.append(Bullet(x, self.y + 90, 0, 230 * game.speed_mult, 12, PINK, 6))
                self.special_timer -= dt
                if self.special_timer <= 0:
                    self.start_special(game)
            elif m == "sweep":                                # rotating stream of shots
                self.sweep_t -= dt
                if self.sweep_t <= 0:
                    self.sweep_t = 0.055
                    game.fire_fan(self.x, self.y + 80, 1, 0, 230, 10, 5, YELLOW, base=55 * math.sin(self.t * 3.2))
                if self.mode_time > 2.0 + 0.4 * ph:
                    self.end_special()
            elif m == "slam_warn":                            # hovers over the player, then drops
                if self.mode_time < 0.55:
                    self.x += clamp(p.x - self.x, -1, 1) * 260 * dt
                self.y = 120 - 20 * min(1, self.mode_time / 0.9) + random.uniform(-2, 2)
                if self.mode_time > 0.9:
                    self.go("slam_down")
            elif m == "slam_down":
                self.y += 900 * dt
                if self.y >= 340:
                    self.y = 340
                    game.fire_ring(self.x, self.y + 60, 20, 230, 13, 6, ORANGE)
                    game.rings.append(Ring(self.x, self.y + 60, 220, ORANGE, 0.6))
                    game.explode(self.x, self.y + 60, ORANGE, 40, 300)
                    game.sounds.play("explosion")
                    game.shake = 0.6
                    self.go("slam_up")
            else:                                             # slam_up: a short pause, then climb back
                if self.mode_time > 0.5:
                    self.y -= 280 * dt
                    if self.y <= 120:
                        self.y = 120
                        self.end_special()

        def start_special(self, game):
            ph = self.phase
            options = ["wall", "sweep"] + (["slam", "summon"] if ph >= 2 else [])
            move = self.last_special = random.choice([o for o in options if o != self.last_special])
            if move == "wall":
                self.wall_left, self.wall_t = 2 + ph, 0.0
                self.end_special()
            elif move == "sweep":
                self.go("sweep")
            elif move == "slam":
                self.go("slam_warn")
            else:                                             # summon two kamikaze drones
                for x in (60, WIDTH - 60, WIDTH / 2)[:2 + (ph == 3)]:
                    if len(game.enemies) < 6:
                        d = SelfDestruct(x, game.level)
                        d.y, d.state, d.wait = self.y + 60, "wait", random.uniform(0.5, 4)
                        game.enemies.append(d)
                self.end_special()

        def end_special(self):
            self.go("fight")
            self.special_timer = SPECIAL_INTERVAL[self.phase] + random.uniform(0, 1.5)

        def attack(self, name, game):
            self.recoil = 0.2
            cx, cy, ph = self.x, self.y + 80, self.phase
            if name == "heavy":                                # heavy laser cannons (left + right)
                for dx in (-92, 92):
                    game.fire_fan(self.x + dx, cy, 1, 0, 250, 18, 9, ORANGE)
            elif name == "aim":                                # aimed shots, more of them each phase
                count, spread = {1: (1, 0), 2: (3, 24), 3: (5, 40)}[ph]
                game.fire_fan(cx, cy, count, spread, 270, 12, 5, YELLOW, aimed=True)
            elif name == "fan":                                # wide spread of projectiles
                count, spread = (9, 110) if ph == 2 else (13, 140)
                game.fire_fan(cx, cy, count, spread, 220, 12, 5, PINK)
            elif name == "shell":                              # slow, heavy aimed shells
                game.fire_fan(cx, cy, 3, 40, 200, 20, 10, RED, aimed=True)
            else:                                              # ring of bullets in all directions
                game.fire_ring(cx, cy, 18, 190, 12, 5, PINK, random.randint(0, 20))

        def draw(self, surf):
            x, y, ph = int(self.x), int(self.y), self.phase
            silver, dark, yellow = (190, 195, 205), (85, 90, 105), (240, 190, 30)
            if self.flash > 0:
                silver = WHITE
            glow = int(120 + 120 * abs(math.sin(self.t * (4 if ph < 3 else 10))))
            core_color = (255, 255, 160) if ph < 3 else (255, glow // 2, 40)
            if ph == 3:                                        # enraged: glowing armour
                yellow = (255, 110 + glow // 3, 20)
            if self.mode == "slam_warn":                       # danger zone under the boss
                pygame.draw.circle(surf, (170, 30, 30), (x, y + 80), 90 + int(15 * math.sin(self.t * 25)), 4)
            # layered armour
            pygame.draw.rect(surf, dark, (x - 130, y - 60, 260, 120), border_radius=6)
            pygame.draw.rect(surf, silver, (x - 120, y - 78, 240, 62), border_radius=4)
            pygame.draw.rect(surf, yellow, (x - 120, y - 30, 240, 14))
            pygame.draw.rect(surf, silver, (x - 100, y - 14, 200, 56))
            pygame.draw.rect(surf, yellow, (x - 100, y + 30, 200, 10))
            for s in (-1, 1):                                  # shoulder armour
                pygame.draw.rect(surf, silver, (x + s * 105 - 25, y - 55, 50, 70), border_radius=4)
                pygame.draw.rect(surf, yellow, (x + s * 105 - 25, y - 55, 50, 10))
            # animated cannons (recoil when firing)
            kick = int(10 * self.recoil / 0.2)
            for dx, wd in ((-92, 34), (0, 28), (92, 34)):
                pygame.draw.rect(surf, dark, (x + dx - wd // 2, y + 40 - kick, wd, 36))
                pygame.draw.rect(surf, GRAY, (x + dx - 5, y + 66 - kick, 10, 16))
                pygame.draw.rect(surf, yellow, (x + dx - wd // 2, y + 40 - kick, wd, 5))
            # glowing energy cores
            for cx_, r in ((0, 20), (-70, 10), (70, 10)):
                pygame.draw.circle(surf, core_color, (x + cx_, y - 20), r)
                pygame.draw.circle(surf, WHITE, (x + cx_, y - 20), r, 2)
            # appearance changes as health drops
            if ph >= 2:
                pygame.draw.line(surf, BLACK, (x - 110, y - 70), (x - 70, y - 40), 3)
                pygame.draw.line(surf, BLACK, (x + 60, y - 72), (x + 95, y - 30), 3)
                pygame.draw.rect(surf, dark, (x - 120, y - 78, 40, 18))         # armour plate torn off
            if ph == 3:
                pygame.draw.circle(surf, (255, 120, 0), (x - 60, y + 15), 10)
                pygame.draw.line(surf, RED, (x + 20, y - 60), (x + 50, y - 10), 4)
                pygame.draw.rect(surf, RED, (x - 130, y - 60, 260, 120), 3, border_radius=6)


    # ============================================================ GAME
class Game:
        def __init__(self):
            pygame.mixer.pre_init(22050, -16, 1, 512)
            pygame.init()
            pygame.display.set_caption("GALAXIAN")
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
            self.canvas = pygame.Surface((WIDTH, HEIGHT))      # everything is drawn here, then shaken
            self.dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            self.dim.fill((0, 0, 0, 160))
            self.clock = pygame.time.Clock()
            self.sounds = Sounds()
            self.stars = Starfield()
            self.username = ""
            self.scores, self.score_error = [], None
            self.leaderboard_back = "menu"
            self.cursor = 0
            self.t = self.shake = self.hurt = 0.0
            self.vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)      # red edges when hit
            pygame.draw.rect(self.vignette, (255, 0, 0, 110), (0, 0, WIDTH, HEIGHT), 26)
            self.reset_run()
            self.set_state("menu")
            self.sounds.play_music("normal")

        # ---------------------------------------------------------- setup
        def reset_run(self):
            self.player = Player()
            self.score = self.enemies_defeated = self.levels_completed = 0
            self.next_life = 5000                 # extra life every 5000 points (like the arcade)
            self.level = 1
            self.save_message = self.level_message = ""
            self.clear_field()

        def clear_field(self):
            self.enemies, self.player_bullets, self.enemy_bullets = [], [], []
            self.particles, self.texts, self.rings, self.pickups = [], [], [], []
            self.boss, self.boss_dying = None, 0.0
            self.spawn_queue, self.wave_index = [], 0
            self.wave_delay, self.wave_banner, self.spawn_timer = 1.0, 0.0, 0.0

        def set_state(self, state):
            self.state, self.state_time, self.cursor = state, 0.0, 0

        @property
        def speed_mult(self):                  # projectiles get faster every level
            return 1 + 0.06 * (self.level - 1)

        def start_game(self):
            self.reset_run()
            self.begin_level(1)

        def begin_level(self, n):
            self.level = n
            self.clear_field()
            self.player.lost_this_level = 0
            self.sounds.play_music("normal")
            self.set_state("transition")

        def start_play(self):
            self.level_message = ""
            self.wave_delay = 0.8
            self.set_state("play")

        def give_upgrade(self, ship, then):
            self.player.ship = ship
            self.player.health = MAX_HEALTH
            self.upgrade_then = then
            self.sounds.play("upgrade")
            self.set_state("upgrade")

        def finish_level(self):
            self.levels_completed = self.level
            self.level_message = "LEVEL %d CLEARED!" % self.level
            if self.player.lost_this_level == 0:               # bonus: level finished without losing a life
                self.score += NO_LIFE_LOST_BONUS
                self.level_message += "   NO-LIFE-LOST BONUS +%d" % NO_LIFE_LOST_BONUS
            if self.level == 7:
                self.end_run(True)
            elif self.level in UPGRADE_AFTER_LEVEL:
                self.give_upgrade(UPGRADE_AFTER_LEVEL[self.level], "next")
            else:
                self.begin_level(self.level + 1)

        def end_run(self, victory):
            _, self.save_message = database.save_score(self.username, self.score,
                                                    self.levels_completed, self.enemies_defeated)
            self.sounds.stop_music()
            self.sounds.play("victory" if victory else "gameover")
            self.set_state("victory" if victory else "gameover")

        def open_leaderboard(self, back):
            self.scores, self.score_error = database.get_top_scores(10)
            self.leaderboard_back = back
            self.set_state("leaderboard")

        # ---------------------------------------------------------- effects
        def explode(self, x, y, color, count=20, speed=220):
            for _ in range(count):
                self.particles.append(Particle(x, y, color, speed, 0.7, 5))

        def sparkle(self, x, y):
            self.particles.append(Particle(x + random.randint(-20, 20), y + random.randint(-10, 10),
                                        GOLD, 30, 0.5, 3))

        def float_text(self, msg, x, y, color):
            self.texts.append(FloatText(msg, x, y, color))

        def fire_fan(self, x, y, count, spread, speed, damage, radius, color, aimed=False, base=0):
            """Enemy fires `count` bullets in a fan. spread = total angle in degrees."""
            centre = aim_angle(x, y, self.player.x, self.player.y) if aimed else math.radians(base)
            speed *= self.speed_mult
            for i in range(count):
                offset = 0 if count == 1 else math.radians(spread) * (i / (count - 1) - 0.5)
                a = centre + offset
                self.enemy_bullets.append(Bullet(x, y, math.sin(a) * speed, math.cos(a) * speed,
                                                damage, color, radius))

        def fire_ring(self, x, y, count, speed, damage, radius, color, offset=0):
            """Bullets in a full circle."""
            speed *= self.speed_mult
            for i in range(count):
                a = math.radians(offset + 360 * i / count)
                self.enemy_bullets.append(Bullet(x, y, math.sin(a) * speed, math.cos(a) * speed, damage, color, radius))

        # ---------------------------------------------------------- main loop
        def run(self):
            while True:
                dt = min(self.clock.tick(FPS) / 1000, 0.05)     # delta time in seconds
                for event in pygame.event.get():
                    self.handle_event(event)
                self.update(dt)
                self.draw()

        def quit(self):
            pygame.quit()
            sys.exit()

        def handle_event(self, event):
            if event.type == pygame.QUIT:
                self.quit()
            if event.type == pygame.KEYDOWN:
                handler = getattr(self, "key_" + self.state, None)
                if handler:
                    handler(event)

        def update(self, dt):
            self.t += dt
            self.state_time += dt
            self.stars.update(dt)
            handler = getattr(self, "update_" + self.state, None)
            if handler:
                handler(dt)
            if self.state != "pause":
                for p in self.particles:
                    p.update(dt)
                for f in self.texts + self.rings:
                    f.update(dt)
                self.rings = [r for r in self.rings if r.life > 0]
                self.hurt = max(0, self.hurt - dt)
                self.particles = [p for p in self.particles if p.life > 0]
                self.texts = [f for f in self.texts if f.life > 0]
                self.shake = max(0, self.shake - dt)

        def draw(self):
            self.canvas.fill(BACKGROUND)
            self.stars.draw(self.canvas)
            getattr(self, "draw_" + self.state)()
            ox = oy = 0
            if self.shake > 0:                                  # screen shake
                amount = min(8, int(self.shake * 30))
                ox, oy = random.randint(-amount, amount), random.randint(-amount, amount)
            self.screen.fill(BLACK)
            self.screen.blit(self.canvas, (ox, oy))
            pygame.display.flip()

        # ---------------------------------------------------------- key handlers
        def menu_move(self, event, count):
            if event.key in (pygame.K_UP, pygame.K_w):
                self.cursor = (self.cursor - 1) % count
                self.sounds.play("select")
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.cursor = (self.cursor + 1) % count
                self.sounds.play("select")

        def key_menu(self, event):
            self.menu_move(event, 4)
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.cursor == 0:
                    self.set_state("name")
                elif self.cursor == 1:
                    self.open_leaderboard("menu")
                elif self.cursor == 2:
                    self.set_state("instructions")
                else:
                    self.quit()

        def key_name(self, event):
            if event.key == pygame.K_RETURN:
                if self.username.strip():
                    self.username = self.username.strip()
                    self.start_game()
            elif event.key == pygame.K_ESCAPE:
                self.set_state("menu")
            elif event.key == pygame.K_BACKSPACE:
                self.username = self.username[:-1]
            elif event.unicode and (event.unicode.isalnum() or event.unicode in "_- ") \
                    and len(self.username) < 12:
                self.username += event.unicode

        def key_instructions(self, event):
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.set_state("menu")

        def key_leaderboard(self, event):
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.set_state(self.leaderboard_back)

        def skip_screen(self, event):
            if event.key == pygame.K_RETURN:
                self.state_time = 99                            # the update method sees this and moves on

        key_transition = key_upgrade = key_warning = skip_screen

        def key_play(self, event):
            if event.key == pygame.K_ESCAPE:
                self.set_state("pause")

        def key_pause(self, event):
            self.menu_move(event, 3)
            if event.key == pygame.K_ESCAPE:
                self.state = "play"
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.cursor == 0:
                    self.state = "play"
                elif self.cursor == 1:
                    self.start_game()
                else:
                    self.sounds.play_music("normal")
                    self.set_state("menu")

        def key_end(self, event):                               # game over + victory screens
            if event.key == pygame.K_RETURN:
                self.start_game()
            elif event.key == pygame.K_l:
                self.open_leaderboard(self.state)
            elif event.key in (pygame.K_m, pygame.K_ESCAPE):
                self.sounds.play_music("normal")
                self.set_state("menu")

        key_gameover = key_victory = key_end

        # ---------------------------------------------------------- update per state
        def update_transition(self, dt):
            if self.state_time > 4:
                if self.level in UPGRADE_AT_START:
                    self.give_upgrade(UPGRADE_AT_START[self.level], "play")
                else:
                    self.start_play()

        def update_upgrade(self, dt):
            if self.state_time > 4.5:
                if self.upgrade_then == "play":
                    self.start_play()
                else:
                    self.begin_level(self.level + 1)

        def update_warning(self, dt):
            if self.state_time > 3.5:
                self.boss = Vorlon() if self.level == 5 else Sentinel()
                self.sounds.play_music("boss")
                self.set_state("play")

        def update_victory(self, dt):
            if random.random() < 0.08:                          # fireworks
                self.explode(random.randint(100, 700), random.randint(80, 300),
                            random.choice([GOLD, CYAN, PINK, GREEN]), 30, 260)

        def update_play(self, dt):
            p = self.player
            p.update(dt, pygame.key.get_pressed(), self)
            if self.boss_dying > 0:
                self.update_boss_dying(dt)
            else:
                if self.boss:
                    self.boss.update(dt, self)
                else:
                    self.update_waves(dt)
                for e in self.enemies:
                    e.update(dt, self)
                self.check_collisions()
            for k in self.pickups:
                k.update(dt)
                if p.rect().colliderect(k.rect()):
                    k.dead = True
                    self.collect(k.kind)
            self.pickups = [k for k in self.pickups if not k.dead]
            if self.score >= self.next_life:
                self.next_life += 5000
                self.collect("life")
            for b in self.player_bullets + self.enemy_bullets:
                b.update(dt)
            # remove used / off-screen objects so lists never grow forever
            self.player_bullets = [b for b in self.player_bullets if not b.dead and not b.off_screen()]
            self.enemy_bullets = [b for b in self.enemy_bullets if not b.dead and not b.off_screen()]
            self.enemies = [e for e in self.enemies if e.alive]
            if p.lives <= 0 and self.state == "play":
                self.explode(p.x, p.y, CYAN, 50, 300)
                self.end_run(False)

        def update_waves(self, dt):
            self.wave_banner = max(0, self.wave_banner - dt)
            if self.spawn_queue:                                # enemies enter one by one
                self.spawn_timer -= dt
                if self.spawn_timer <= 0:
                    kind, x = self.spawn_queue.pop(0)
                    cls = {"S": SelfDestruct, "L": LaserShooter, "G": GoldenPerk, "T": AttackTanker}[kind]
                    self.enemies.append(cls(x, self.level))
                    self.spawn_timer = 0.6
            elif not self.enemies:                              # wave cleared
                self.wave_delay -= dt
                if self.wave_delay <= 0:
                    self.next_wave()

        def next_wave(self):
            waves = LEVELS[self.level]
            if self.wave_index < len(waves):
                kinds = list(waves[self.wave_index])
                random.shuffle(kinds)
                slots = [WIDTH * (i + 1) / (len(kinds) + 1) for i in range(len(kinds))]
                self.spawn_queue = list(zip(kinds, slots))
                self.wave_index += 1
                self.wave_banner, self.spawn_timer, self.wave_delay = 2.0, 0.0, 1.5
            elif self.level in BOSS_LEVELS:
                self.sounds.stop_music()
                self.sounds.play("warning")
                self.set_state("warning")
            else:
                self.finish_level()

        def update_boss_dying(self, dt):
            self.boss_dying -= dt
            b = self.boss
            if random.random() < 0.4:                           # chain of explosions on the wreck
                self.explode(b.x + random.randint(-b.w // 2, b.w // 2),
                            b.y + random.randint(-b.h // 2, b.h // 2),
                            random.choice([ORANGE, YELLOW, RED]), 12)
                if random.random() < 0.15:
                    self.sounds.play("explosion")
            if self.boss_dying <= 0:
                self.explode(b.x, b.y, WHITE, 80, 500)
                self.shake = 0.6
                self.boss = None
                self.finish_level()

        # ---------------------------------------------------------- collisions + scoring
        def boss_hittable(self):
            return self.boss is not None and self.boss.alive and not self.boss.entering

        def check_collisions(self):
            p = self.player
            pr = p.rect()
            for b in self.player_bullets:
                br = b.rect()
                for e in self.enemies:
                    if e.alive and br.colliderect(e.rect()):
                        b.dead = True
                        e.hit(b.damage)
                        self.explode(b.x, b.y, WHITE, 3, 120)
                        if e.hp <= 0:
                            self.kill_enemy(e)
                        break
                if not b.dead and self.boss_hittable() and br.colliderect(self.boss.rect()):
                    b.dead = True
                    stage = self.boss.stage
                    self.boss.hit()
                    if self.boss.stage != stage and self.boss.hp > 0:     # phase change: boss drops a perk
                        self.drop(self.boss.x, self.boss.y + 60, ["health", "shield", "bomb"])
                    self.explode(b.x, b.y, YELLOW, 3, 150)
                    self.sounds.play("boss_hit")
                    if self.boss.hp <= 0:
                        self.kill_boss()
            for b in self.enemy_bullets:
                if pr.colliderect(b.rect()):
                    b.dead = True
                    p.take_damage(b.damage, self)
            for e in self.enemies:                              # ramming damage
                if e.alive and e.kind in ("shooter", "tanker") and pr.colliderect(e.rect()):
                    p.take_damage(15, self)
            if self.boss_hittable() and pr.colliderect(self.boss.rect()):
                p.take_damage(self.boss.touch_damage(), self)

        def collect(self, kind):
            p = self.player
            self.float_text(PERKS[kind][2], p.x, p.y - 40, PERKS[kind][0])
            self.sounds.play("upgrade")
            if kind == "health":
                p.health = min(MAX_HEALTH, p.health + 30)
            elif kind == "rapid":
                p.rapid = 8
            elif kind == "shield":
                p.shield = 6
            elif kind == "life":
                p.lives = min(5, p.lives + 1)
            else:                                               # smart bomb: wipes bullets, hurts everything
                self.enemy_bullets.clear()
                self.rings.append(Ring(p.x, p.y, 500, RED, 0.6))
                self.shake = 0.4
                for e in self.enemies:
                    e.hit(15)
                    if e.hp <= 0 and e.alive:
                        self.kill_enemy(e)
                if self.boss_hittable():
                    self.boss.hp -= 10
                    if self.boss.hp <= 0:
                        self.kill_boss()

        def drop(self, x, y, kinds=None):
            self.pickups.append(Pickup(x, y, random.choices(kinds or list(PERKS), [4, 3, 3, 2, 1] if not kinds else None)[0]))

        def kill_enemy(self, e):
            e.alive = False                                     # points are given only once, right here
            self.score += e.score
            self.enemies_defeated += 1
            self.explode(e.x, e.y, e.color, 30 if e.kind == "tanker" else 20)
            self.sounds.play("explosion")
            self.float_text("+%d" % e.score, e.x, e.y, WHITE)
            if e.kind == "tanker":
                self.shake = 0.25
            if e.kind == "selfdestruct" and e.state == "dive":    # shooting a diver = bonus (arcade style)
                self.score += 200
                self.float_text("DIVE BONUS +200", e.x, e.y - 25, YELLOW)
            if e.kind == "golden":
                self.golden_reward(e)
                self.drop(e.x - 20, e.y)
                self.drop(e.x + 20, e.y)
            elif random.random() < (0.6 if e.kind == "tanker" else 0.12):
                self.drop(e.x, e.y)

        def golden_reward(self, e):
            p = self.player
            reward = random.choice(["health", "rapid", "shield", "bonus"])
            if reward == "health":
                p.health = min(MAX_HEALTH, p.health + 40)
                self.float_text("+40 HEALTH", e.x, e.y - 30, GREEN)
            elif reward == "rapid":
                p.rapid = 8
                self.float_text("RAPID FIRE 8s", e.x, e.y - 30, ORANGE)
            elif reward == "shield":
                p.shield = 6
                self.float_text("SHIELD 6s", e.x, e.y - 30, BLUE)
            else:
                self.score += 500
                self.float_text("BONUS +500", e.x, e.y - 30, GOLD)

        def kill_boss(self):
            b = self.boss
            b.alive = False
            self.score += b.score
            self.enemies_defeated += 1
            self.boss_dying = 2.0 if b.name == "VORLON" else 4.0
            self.enemy_bullets.clear()
            self.float_text("%s DESTROYED  +%d" % (b.name, b.score), WIDTH / 2, 250, GOLD)
            self.sounds.play("explosion")
            self.sounds.stop_music()
            self.shake = 0.5

        # ---------------------------------------------------------- drawing: gameplay
        def draw_world(self):
            c = self.canvas
            for e in self.enemies:
                e.draw(c)
            if self.boss and (self.boss.alive or int(self.t * 16) % 2 == 0):
                self.boss.draw(c)
            for b in self.player_bullets + self.enemy_bullets:
                b.draw(c)
            for k in self.pickups:
                k.draw(c)
            self.player.draw(c)
            for r in self.rings:
                r.draw(c)
            for p in self.particles:
                p.draw(c)
            for f in self.texts:
                f.draw(c)
            if self.hurt > 0:                                   # red screen edges when hit
                self.vignette.set_alpha(int(255 * self.hurt / 0.3))
                c.blit(self.vignette, (0, 0))
            if self.boss and self.boss.entering:
                text(c, self.boss.name, 90, RED, WIDTH / 2, 330)
            elif self.wave_banner > 0 and not self.boss:
                text(c, "WAVE %d / %d" % (self.wave_index, len(LEVELS[self.level])), 48, CYAN,
                    WIDTH / 2, 150)

        def draw_hud(self):
            c, p = self.canvas, self.player
            top = HEIGHT - 60
            pygame.draw.rect(c, (8, 8, 28), (0, top, WIDTH, 60))
            pygame.draw.line(c, CYAN, (0, top), (WIDTH, top))
            text(c, "LEVEL %d/7" % self.level, 26, CYAN, 12, top + 8, False)
            text(c, "SCORE %d" % self.score, 26, WHITE, 150, top + 8, False)
            text(c, "LIVES %d" % p.lives, 26, GREEN, 330, top + 8, False)
            text(c, "SHIP %s" % SHIPS[p.ship]["name"], 26, YELLOW, 450, top + 8, False)
            text(c, "HP", 22, WHITE, 12, top + 36, False)
            pygame.draw.rect(c, (60, 20, 20), (40, top + 36, 200, 14))
            ratio = clamp(p.health / MAX_HEALTH, 0, 1)
            pygame.draw.rect(c, GREEN if ratio > 0.3 else RED, (40, top + 36, int(200 * ratio), 14))
            pygame.draw.rect(c, WHITE, (40, top + 36, 200, 14), 1)
            x = 270
            if p.rapid > 0:
                text(c, "RAPID %ds" % math.ceil(p.rapid), 24, ORANGE, x, top + 36, False)
                x += 120
            if p.shield > 0:
                text(c, "SHIELD %ds" % math.ceil(p.shield), 24, BLUE, x, top + 36, False)
            if self.boss and self.boss.alive:                   # boss health bar at the top
                b = self.boss
                text(c, b.name, 24, RED, WIDTH / 2, 14)
                pygame.draw.rect(c, (60, 20, 20), (100, 26, 600, 16))
                colour = (YELLOW, ORANGE, RED)[b.stage]          # bar turns red as the boss weakens
                pygame.draw.rect(c, colour, (100, 26, int(600 * max(0, b.hp) / b.max_hp), 16))
                pygame.draw.rect(c, WHITE, (100, 26, 600, 16), 2)
                for f in (0.33, 0.66):                           # phase markers
                    pygame.draw.line(c, WHITE, (100 + int(600 * f), 26), (100 + int(600 * f), 42), 2)

        def draw_play(self):
            self.draw_world()
            self.draw_hud()

        def draw_pause(self):
            self.draw_play()
            self.canvas.blit(self.dim, (0, 0))
            text(self.canvas, "PAUSED", 90, CYAN, WIDTH / 2, 170)
            self.draw_menu_items(["Resume", "Restart", "Main Menu"], 280)
            text(self.canvas, "ESC = resume", 24, GRAY, WIDTH / 2, 520)

        def draw_menu_items(self, items, y):
            for i, item in enumerate(items):
                selected = i == self.cursor
                label = ("> %s <" % item) if selected else item
                text(self.canvas, label, 48 if selected else 40, YELLOW if selected else WHITE,
                    WIDTH / 2, y + i * 55)

        # ---------------------------------------------------------- drawing: screens
        def draw_menu(self):
            c = self.canvas
            colour = (int(150 + 100 * math.sin(self.t * 2)), 80, 255)
            text(c, "GALAXIAN", 130, colour, WIDTH / 2, 110)
            text(c, "2D ARCADE SPACE SHOOTER", 28, CYAN, WIDTH / 2, 175)
            draw_player_ship(c, WIDTH / 2, 235, int(self.t / 1.5) % 4 + 1, 1.2, self.t)
            self.draw_menu_items(["Play", "Leaderboard", "Instructions", "Quit"], 320)
            text(c, "UP / DOWN + ENTER", 22, GRAY, WIDTH / 2, 570)

        def draw_name(self):
            c = self.canvas
            text(c, "ENTER YOUR USERNAME", 64, CYAN, WIDTH / 2, 170)
            pygame.draw.rect(c, (20, 20, 50), (200, 250, 400, 60), border_radius=8)
            pygame.draw.rect(c, CYAN, (200, 250, 400, 60), 2, border_radius=8)
            cursor = "_" if int(self.t * 2) % 2 == 0 else " "
            text(c, self.username + cursor, 48, WHITE, WIDTH / 2, 280)
            text(c, "Letters, numbers, space, _ and -  (max 12)", 24, GRAY, WIDTH / 2, 340)
            text(c, "ENTER = start     ESC = back", 28, YELLOW, WIDTH / 2, 420)

        def draw_instructions(self):
            c = self.canvas
            text(c, "INSTRUCTIONS", 64, CYAN, WIDTH / 2, 50)
            lines = [
                ("Arrows / WASD", "move in all directions", WHITE),
                ("SPACE", "shoot          ESC: pause", WHITE),
                ("", "", WHITE),
                ("SELF-DESTRUCT", "kamikaze: locks on, HUGE blast (100)", RED),
                ("LASER SHOOTER", "keeps its distance, fires lasers (150)", PURPLE),
                ("GOLDEN PERK MOB", "shoot for health / rapid fire / shield / bonus (300)", GOLD),
                ("ATTACK TANKER", "big, tough, fires spreads (500)", ORANGE),
                ("VORLON", "mini-boss, level 5: lunges hard (2500)", PINK),
                ("SENTINEL", "final boss, level 7: walls, slams (10000)", YELLOW),
                ("", "", WHITE),
                ("Upgrades", "MK-II level 3, MK-III after Vorlon, MK-IV level 7", GREEN),
                ("Bonus", "+1000 for finishing a level without losing a life", GREEN),
            ]
            for i, (a, b, col) in enumerate(lines):
                text(c, a, 28, col, 60, 110 + i * 36, False)
                text(c, b, 26, WHITE, 280, 111 + i * 36, False)
            text(c, "Press ENTER to go back", 26, YELLOW, WIDTH / 2, 565)

        def draw_leaderboard(self):
            c = self.canvas
            text(c, "LEADERBOARD", 70, GOLD, WIDTH / 2, 60)
            if self.score_error:
                text(c, self.score_error, 32, RED, WIDTH / 2, 260)
                text(c, "(see README: database setup)", 24, GRAY, WIDTH / 2, 305)
            elif not self.scores:
                text(c, "No scores yet - be the first!", 36, WHITE, WIDTH / 2, 260)
            else:
                for x, head in ((90, "RANK"), (200, "USERNAME"), (480, "POINTS"), (640, "LEVELS")):
                    text(c, head, 28, CYAN, x, 120, False)
                for i, row in enumerate(self.scores[:10]):
                    y = 160 + i * 36
                    col = GOLD if i == 0 else WHITE
                    text(c, "%d" % (i + 1), 30, col, 90, y, False)
                    text(c, str(row[0]), 30, col, 200, y, False)
                    text(c, str(row[1]), 30, col, 480, y, False)
                    text(c, "%s/7" % row[2], 30, col, 640, y, False)
            text(c, "Press ENTER to go back", 26, YELLOW, WIDTH / 2, 565)

        def draw_transition(self):
            c = self.canvas
            if self.level_message:
                text(c, self.level_message, 30, GREEN, WIDTH / 2, 90)
            text(c, "LEVEL %d" % self.level, 120, CYAN, WIDTH / 2, 190)
            if self.level in BOSS_LEVELS:
                text(c, "BOSS LEVEL", 40, RED, WIDTH / 2, 270)
            text(c, "THREAT BRIEFING", 30, YELLOW, WIDTH / 2, 340)
            for i, line in enumerate(BRIEFINGS[self.level]):
                text(c, line, 28, WHITE, WIDTH / 2, 385 + i * 36)
            text(c, "ENTER = skip", 22, GRAY, WIDTH / 2, 560)

        def draw_upgrade(self):
            c = self.canvas
            ship = self.player.ship
            text(c, "SHIP UPGRADE!", 80, YELLOW, WIDTH / 2, 90)
            for i in range(3):                                   # expanding energy rings
                r = (self.state_time * 160 + i * 70) % 210
                shade = max(0, 255 - int(r * 1.2))
                pygame.draw.circle(c, (shade // 3, shade, shade), (WIDTH // 2, 300), int(r) + 20, 3)
            grow = min(1.0, 0.3 + self.state_time * 1.2)
            draw_player_ship(c, WIDTH / 2, 300, ship, 3.5 * grow, self.t)
            text(c, SHIPS[ship]["name"], 90, SHIP_COLORS[ship][0], WIDTH / 2, 450)
            text(c, SHIPS[ship]["info"], 32, WHITE, WIDTH / 2, 505)
            text(c, "Upgrades stay active for the rest of the run.   Health restored!", 24, GREEN, WIDTH / 2, 545)
            if self.state_time < 0.6:                            # white flash at the start
                flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                flash.fill((255, 255, 255, int(255 * (1 - self.state_time / 0.6))))
                c.blit(flash, (0, 0))

        def draw_warning(self):
            c = self.canvas
            if int(self.state_time * 4) % 2 == 0:
                pygame.draw.rect(c, RED, (0, 0, WIDTH, HEIGHT), 14)
            text(c, "WARNING!", 140, RED, WIDTH / 2, 200)
            name = BOSS_LEVELS[self.level]
            kind = "MINI-BOSS" if self.level == 5 else "FINAL BOSS"
            text(c, "%s %s APPROACHING" % (kind, name), 46, YELLOW, WIDTH / 2, 320)
            text(c, "Prepare for battle", 30, WHITE, WIDTH / 2, 380)
            text(c, "ENTER = skip", 22, GRAY, WIDTH / 2, 560)

        def draw_end_stats(self):
            c = self.canvas
            text(c, "FINAL SCORE: %d" % self.score, 56, WHITE, WIDTH / 2, 250)
            text(c, "Enemies defeated: %d" % self.enemies_defeated, 34, CYAN, WIDTH / 2, 310)
            text(c, "Levels completed: %d / 7" % self.levels_completed, 34, CYAN, WIDTH / 2, 350)
            text(c, "Player: %s" % self.username, 30, YELLOW, WIDTH / 2, 395)
            text(c, self.save_message, 28, GREEN if "offline" not in self.save_message else RED,
                WIDTH / 2, 440)
            text(c, "ENTER = play again     L = leaderboard     M = menu", 26, YELLOW, WIDTH / 2, 530)

        def draw_gameover(self):
            text(self.canvas, "GAME OVER", 130, RED, WIDTH / 2, 150)
            self.draw_end_stats()

        def draw_victory(self):
            for p in self.particles:
                p.draw(self.canvas)
            text(self.canvas, "VICTORY!", 130, GOLD, WIDTH / 2, 120)
            text(self.canvas, "SENTINEL is destroyed - the galaxy is saved!", 32, WHITE, WIDTH / 2, 195)
            self.draw_end_stats()


if __name__ == "__main__":
    Game().run()