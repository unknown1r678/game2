import math
import random
from array import array

import pygame

RATE = 22050


def make_wave(freq, length, volume=0.3, shape="square", end_freq=None, decay=1.0):
    """Return a list of 16-bit samples for one tone. The pitch can slide to end_freq."""
    n = int(RATE * length)
    end_freq = end_freq or freq
    samples, phase = [], 0.0
    for i in range(n):
        f = freq + (end_freq - freq) * i / n
        phase += f / RATE
        if shape == "square":
            v = 1.0 if (phase % 1) < 0.5 else -1.0
        elif shape == "sine":
            v = math.sin(2 * math.pi * phase)
        else:                                   # "noise" (used for explosions)
            v = random.uniform(-1, 1)
        fade = 1 - decay * i / n                # fade out -> no clicking sound
        samples.append(int(v * volume * fade * 32767))
    return samples


def melody(notes, step, volume, shape="square", decay=1.0):
    samples = []
    for f in notes:
        samples += make_wave(f, step, volume, shape, decay=decay)
    return samples

class Sounds:
    def __init__(self):
        self.ok = False
        self.effects, self.music = {}, {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 1, 512)
            self.channels = pygame.mixer.get_init()[2]
            pygame.mixer.set_reserved(1)            # channel 0 is kept for the music
            self.music_channel = pygame.mixer.Channel(0)
            self.build()
            self.ok = True
        except Exception as err:
            print("Sound disabled:", err)

    def to_sound(self, samples):
        data = array("h")
        for s in samples:
            data.append(s)
            if self.channels == 2:                  # stereo mixer: copy to both speakers
                data.append(s)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def build(self):
        fx = {
            "shoot": make_wave(900, 0.07, 0.12, "square", end_freq=500),
            "hit": make_wave(150, 0.12, 0.30, "noise"),
            "explosion": make_wave(100, 0.40, 0.35, "noise"),
            "boss_hit": make_wave(220, 0.08, 0.25, "square", end_freq=120),
            "select": make_wave(700, 0.05, 0.15, "square"),
            "upgrade": melody([330, 440, 550, 660, 880], 0.10, 0.25),
            "warning": melody([600, 400, 600, 400], 0.30, 0.25, decay=0.2),
            "victory": melody([523, 659, 784, 1046, 784, 1046, 1318], 0.15, 0.25),
            "gameover": melody([400, 330, 260, 190], 0.25, 0.25),
        }
        for name, samples in fx.items():
            self.effects[name] = self.to_sound(samples)
        # background music: a short bass loop (normal) and a faster, tenser one (boss)
        self.music["normal"] = self.to_sound(
            melody([110, 110, 165, 110, 131, 110, 165, 196] * 2, 0.22, 0.10, decay=0.6))
        self.music["boss"] = self.to_sound(
            melody([110, 117, 110, 156, 110, 117, 175, 156] * 2, 0.13, 0.12, decay=0.6))

    def play(self, name):
        if self.ok and name in self.effects:
            self.effects[name].play()

    def play_music(self, name):
        if self.ok:
            self.music_channel.play(self.music[name], loops=-1)

    def stop_music(self):
        if self.ok:
            self.music_channel.stop()
