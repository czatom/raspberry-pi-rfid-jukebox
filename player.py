#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Tomasz Czaja'
__version__ = '0.0.1'

import sys
import time
from pathlib import Path
import signal
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
from ST7789 import ST7789
from audioplayer import AudioPlayer


class RfidJukebox(object):
    # Hardcoded list of files
    FILES = {
        '3373707988': "07. Dans Les Jardins de Baya.mp3",
        '1': "01. Awaya Baka.mp3",
        '2': "02. Braighe Locheil (The Brais of Loch Eil).mp3"
    }

    SPI_SPEED_MHZ = 80

    _st7789 = ST7789(
        rotation=90,  # Needed to display the right way up on Pirate Audio
        port=0,  # SPI port
        cs=1,  # SPI port Chip-select channel
        dc=9,  # BCM pin used for data/command
        backlight=13,
        spi_speed_hz=SPI_SPEED_MHZ * 1000 * 1000
    )

    # The buttons on Pirate Audio are connected to pins 5, 6, 16 and 24
    # Boards prior to 23 January 2020 used 5, 6, 16 and 20
    # try changing 24 to 20 if your Y button doesn't work.
    BUTTONS = [5, 6, 16, 24]

    # These correspond to buttons A, B, X and Y respectively
    LABELS = ['A', 'B', 'X', 'Y']

    # Stuff for drawing on screen
    _image = None
    _draw = None
    _font = None

    @property
    def font(self):
        return self._font

    @font.setter
    def font(self, new_font):
        self._font = new_font

    # Player settings
    _last_selected_key = None

    _min_volume = 0
    _max_volume = 100
    _volume = 50

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, new_volume):
        self._volume = new_volume

    _player = None

    @property
    def player(self):
        return self._player

    def __init__(self):
        """
        Init the _player
        :return: void
        """

        # Set up RPi.GPIO with the "BCM" numbering scheme
        GPIO.setmode(GPIO.BCM)

        # Buttons connect to ground when pressed, so we should set them up
        # with a "PULL UP", which weakly pulls the input signal to 3.3V.
        GPIO.setup(self.BUTTONS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Loop through out buttons and attach the "handle_button" function to each
        # We're watching the "FALLING" edge (transition from 3.3V to Ground) and
        # picking a generous bouncetime of 100ms to smooth out button presses.
        for pin in self.BUTTONS:
            GPIO.add_event_detect(pin, GPIO.FALLING, self._handle_button, bouncetime=100)

        # Get initial value - first in the dictionary
        self._last_selected_key = list(self.FILES.keys())[0]

        # Set image and draw objects
        self._image = Image.new("RGB", (240, 240), (0, 0, 0))
        self._draw = ImageDraw.Draw(self._image)

        # Set font type and size
        self._font = ImageFont.truetype("/home/pi/Fonts/FreeMono.ttf", 42)

        # Draw default background
        self._draw_background()
        label_length = self._font.getsize('version')[0]
        label_x_pos = int(round(240 / 2 - label_length / 2))
        self._draw.text((label_x_pos, 100), 'version', font=self.font, fill=(255, 255, 255, 255))
        label_length = self._font.getsize(str(__version__))[0]
        label_x_pos = int(round(240 / 2 - label_length / 2))
        self._draw.text((label_x_pos, 135), __version__, font=self.font, fill=(255, 255, 255, 255))
        self._st7789.display(self._image)

    def _get_previous_key(self):
        temp = list(self.FILES.keys())
        try:
            key = temp[temp.index(self._last_selected_key) - 1]
        except (ValueError, IndexError):
            # If no more keys - use last one - this is probably obsolete
            key = temp[-1]
        return key

    def _get_next_key(self):
        temp = list(self.FILES.keys())
        try:
            key = temp[temp.index(self._last_selected_key) + 1]
        except (ValueError, IndexError):
            # If no more keys - use first one
            key = temp[0]
        return key

    def _draw_background(self):
        self._draw.rectangle((0, 0, 240, 240), (0, 0, 0))  # Draw background
        # Draw related _image if exists
        if self._player and self._last_selected_key:
            picture = Path(f'/home/pi/Pictures/{self._last_selected_key}.jpg')
            if picture.is_file():
                with Image.open(str(picture)) as im:
                    im_resized = im.resize((240, 240))
                    self._image.paste(im_resized)

        # Left navigation button
        self._draw.polygon([(25, 20), (10, 30), (25, 40)], fill=(0x60, 0x60, 0x60), outline=(255, 255, 255))
        self._draw.polygon([(40, 20), (25, 30), (40, 40)], fill=(0x60, 0x60, 0x60), outline=(255, 255, 255))
        # Right navigation button
        self._draw.polygon([(240 - 25, 20), (240 - 10, 30), (240 - 25, 40)], fill=(0x60, 0x60, 0x60),
                           outline=(255, 255, 255))
        self._draw.polygon([(240 - 40, 20), (240 - 25, 30), (240 - 40, 40)], fill=(0x60, 0x60, 0x60),
                           outline=(255, 255, 255))

    def play_song(self, key):
        if key in self.FILES:
            audio_file = Path(f'/home/pi/Music/{self.FILES[key]}')
            if audio_file.is_file():
                # Stop _player if running
                if self._player:
                    self._player.stop()
                # Play audio file
                print(f"Playing {audio_file.name} ({key})")
                self._last_selected_key = key
                self._draw_background()
                self._draw.text((100, 140), str(key), font=self.font, fill=(255, 255, 255, 255))
                self._st7789.display(self._image)
                self._player = AudioPlayer(f"Music/{audio_file.name}")
                self._player.volume = self._volume
                self._player.play()

    def play_next_song(self):
        next_key = self._get_next_key()
        self.play_song(next_key)

    def play_previous_song(self):
        prev_key = self._get_previous_key()
        self.play_song(prev_key)

    def _draw_volume_indicators(self, new_volume):
        self._draw_background()
        label_length = self._font.getsize(str(new_volume))[0]
        label_x_pos = int(round(240 / 2 - label_length / 2))  # Volume label start pos
        self._draw.text((label_x_pos, 140), str(new_volume), font=self._font,
                        fill=(255, 255, 255, 255))  # Draw _volume label
        volume_bar_x = int(round(10 + (220 * new_volume / self._max_volume)))
        self._draw.rectangle((10, 200, volume_bar_x, 210), (0x30, 0x30, 0x30))  # Draw _volume bar
        self._st7789.display(self._image)

    # "handle_button" will be called every time a button is pressed
    # It receives one argument: the associated input pin.
    def _handle_button(self, pin):
        label = self.LABELS[self.BUTTONS.index(pin)]
        print("Button press detected on pin: {} label: {}".format(pin, label))
        if label == 'B':
            # Decrease volume
            new_volume = self._volume - 10
            if new_volume < self._min_volume:
                new_volume = self._min_volume
            self._volume = new_volume  # Store _volume for new instances of _player
            # Draw value and _volume bar
            self._draw_volume_indicators(new_volume)
            # Set new volume for player
            if self._player:
                self._player.volume = new_volume

        elif label == 'Y':
            # Increase volume
            new_volume = self._volume + 10
            if new_volume > self._max_volume:
                new_volume = self._max_volume
            self._volume = new_volume  # Store _volume for new instances of _player
            # Draw value and _volume bar
            self._draw_volume_indicators(new_volume)
            # Set new volume for player
            if self._player:
                self._player.volume = new_volume

        elif label == 'A':
            # Play previous song
            self.play_previous_song()
            message = "Prev song"
            self._draw_background()
            self._draw.text((10, 140), message, font=self._font, fill=(255, 255, 255, 255))
            self._st7789.display(self._image)
        elif label == 'X':
            # Play next song
            self.play_next_song()
            message = "Next song"
            self._draw_background()
            self._draw.text((10, 140), message, font=self._font, fill=(255, 255, 255, 255))
            self._st7789.display(self._image)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    jukebox = RfidJukebox()
    while True:
        try:
            value = input("Enter song key:\n")
            if value.isdigit():
                jukebox.play_song(value)
            time.sleep(0.3)
        except KeyboardInterrupt:
            if jukebox.player:
                jukebox.player.stop()
            print("Bye")
            sys.exit()
