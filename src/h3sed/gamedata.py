# -*- coding: utf-8 -*-
"""
Reads hero portraits and artifact icons from an installed Heroes3 game.

Game art is not distributed with h3sed; it is read from the game's own LOD
archives, and everything degrades to no icon at all if the game is not found.

------------------------------------------------------------------------------
This file is part of h3sed - Heroes3 Savegame Editor.
Released under the MIT License.

@created   20.09.2026
@modified  20.09.2026
------------------------------------------------------------------------------
"""
import glob
import logging
import os
import struct
import zlib

try: import wx
except ImportError: wx = None

from . import conf

logger = logging.getLogger(__name__)


"""Archives holding hero portraits and artifact icons, in order of preference."""
BITMAP_ARCHIVES = ["H3ab_bmp.lod", "H3bitmap.lod"]
SPRITE_ARCHIVES = ["H3ab_spr.lod", "H3sprite.lod"]

"""Sprite archive holding artifact icons, and its frame count for real artifacts."""
ARTIFACT_SPRITE, ARTIFACT_FRAMES = "Artifact.def", 144

"""Hero class codes in savefile hero order, eight heroes each."""
HERO_CLASSES = ["KN", "CL", "RN", "DR", "AL", "WZ", "HR", "DM",
                "DK", "NC", "OV", "WL", "BR", "BM", "BS", "WH"]

"""Hero classes numbering their portraits from zero rather than by hero id."""
HERO_CLASSES_RESTARTING = ["PL", "EL"]

"""
Portrait files for heroes whose names do not follow from their class.

Campaign heroes were added late and kept one-off file names; identified by
matching their portraits against the hero images on heroes.thelazy.net.
"""
HERO_PORTRAITS = {
    144: "HPS130KN.pcx",  # Sir Mullich
    145: "HPS000SH.pcx",  # Adrienne
    146: "HPS128QC.pcx",  # Catherine
    147: "HPS003SH.pcx",  # Dracon
    148: "HPS004SH.pcx",  # Gelu
    149: "HPS005SH.pcx",  # Kilgor
    150: "HPS006SH.pcx",  # Lord Haart, the death knight one
    151: "HPS007SH.pcx",  # Mutare
    152: "HPS009SH.pcx",  # Roland
    153: "HPS008SH.pcx",  # Mutare Drake
    154: "HPS001SH.pcx",  # Boragus
    155: "HPS131DM.pcx",  # Xeron
}

"""Sizes to fit icons into, keeping combobox rows to a sensible height."""
ICON_SIZE = (22, 22)
HERO_ICON_SIZE = (33, 22)  # Portraits are wider than tall

"""Palette indexes standing for transparency and shadow in sprite frames."""
SPRITE_TRANSPARENT = (0, 1, 4, 5, 6, 7)

"""Common install locations to look for game data under."""
DEFAULT_DIRECTORIES = [
    "C:/GOG Games/Heroes of Might and Magic 3 Complete/Data",
    "C:/Program Files (x86)/GOG Galaxy/Games/Heroes of Might and Magic 3/Data",
    "C:/Program Files (x86)/Ubisoft/Heroes of Might and Magic III/Data",
    "C:/Games/Heroes3/Data",
]


class LodArchive(object):
    """Index of a Heroes3 LOD archive, reading entries on demand."""

    MAGIC, HEADER_SIZE, ENTRY_SIZE = b"LOD", 92, 32


    def __init__(self, filename):
        self.filename = filename
        self.entries = {}  # {lowercase name: (offset, size, compressed size)}
        self.read_index()


    def read_index(self):
        """Populates the archive entry index, raises on unreadable file."""
        with open(self.filename, "rb") as f:
            header = f.read(self.HEADER_SIZE)
            if header[:len(self.MAGIC)] != self.MAGIC:
                raise ValueError("Not a LOD archive: %s" % self.filename)
            count = struct.unpack_from("<I", header, 8)[0]
            table = f.read(self.ENTRY_SIZE * count)
        for i in range(count):
            name, offset, size, _, csize = struct.unpack_from("<16sIIII", table,
                                                              self.ENTRY_SIZE * i)
            name = name.split(b"\0")[0].decode("latin1")
            self.entries[name.lower()] = (offset, size, csize)


    def __contains__(self, name):
        return name.lower() in self.entries


    def read(self, name):
        """Returns decompressed contents of the named entry, or None."""
        entry = self.entries.get(name.lower())
        if not entry: return None
        offset, size, csize = entry
        with open(self.filename, "rb") as f:
            f.seek(offset)
            data = f.read(csize or size)
        return zlib.decompress(data) if csize else data


def decode_pcx(data):
    """
    Returns (width, height, RGB bytes) for a Heroes3 paletted image, or None.

    Not the standard PCX format: a small header, one byte of palette index per
    pixel, and a 256-colour palette at the end.
    """
    if not data or len(data) < 12: return None
    size, width, height = struct.unpack_from("<III", data, 0)
    if size != width * height or len(data) < 12 + size + 768: return None
    pixels, palette = data[12:12 + size], data[12 + size:12 + size + 768]
    rgb = bytearray(size * 3)
    for i, value in enumerate(pixels):
        rgb[i * 3:i * 3 + 3] = palette[value * 3:value * 3 + 3]
    return width, height, bytes(rgb)


def parse_def(data):
    """Returns (palette, [frame offset, ]) for a sprite archive, in frame order."""
    blocks = struct.unpack_from("<IIII", data, 0)[3]
    palette, pos, offsets = data[16:16 + 768], 16 + 768, []
    for _ in range(blocks):
        count = struct.unpack_from("<II", data, pos)[1]
        pos += 16 + 13 * count
        offsets.extend(struct.unpack_from("<%dI" % count, data, pos))
        pos += 4 * count
    return palette, offsets


def decode_def_frame(data, offset, palette):
    """Returns (width, height, RGB bytes, alpha bytes) for a sprite frame, or None."""
    size, fmt, width, height, w, h, left, top = struct.unpack_from("<IIIIIIii", data, offset)
    body = offset + 32
    rgb, alpha = bytearray(width * height * 3), bytearray(width * height)

    def put(x, y, index):
        if index in SPRITE_TRANSPARENT or not 0 <= x < width or not 0 <= y < height: return
        pos = y * width + x
        rgb[pos * 3:pos * 3 + 3] = palette[index * 3:index * 3 + 3]
        alpha[pos] = 255

    if 0 == fmt:
        for row in range(h):
            for col in range(w): put(left + col, top + row, data[body + row * w + col])
    elif 1 == fmt:
        for row, lineoffset in enumerate(struct.unpack_from("<%dI" % h, data, body)):
            pos, x = body + lineoffset, 0
            while x < w:
                code, length = data[pos], data[pos + 1]
                pos += 2
                for i in range(length + 1):
                    put(left + x + i, top + row, data[pos + i] if 0xFF == code else code)
                if 0xFF == code: pos += length + 1
                x += length + 1
    else:
        logger.warning("Unsupported sprite compression format %s.", fmt)
        return None
    return width, height, bytes(rgb), bytes(alpha)


class GameData(object):
    """Hero portraits and artifact icons from an installed game, loaded on demand."""

    def __init__(self):
        self.directory = None
        self._archives = {}   # {filename: LodArchive or None if unreadable}
        self._heroes   = {}   # {hero id: wx.Bitmap or None}
        self._artifacts = {}  # {artifact id: wx.Bitmap or None}
        self._sprite   = None # (data, palette, [frame offset, ]) for artifact icons
        self._portraits = None  # {lowercase portrait file name: archive}


    def find_directory(self):
        """Returns the game data directory, looking in configured and usual places."""
        if self.directory: return self.directory
        candidates = [conf.GameDataDirectory] if getattr(conf, "GameDataDirectory", None) else []
        candidates += DEFAULT_DIRECTORIES
        for path in filter(bool, candidates):
            if any(os.path.isfile(os.path.join(path, x)) for x in BITMAP_ARCHIVES):
                self.directory = path
                logger.info("Using game data from %s.", path)
                return path
        return None


    def available(self):
        """Returns whether game art is available."""
        return bool(self.find_directory())


    def archive(self, filename):
        """Returns LodArchive for the given archive name, or None."""
        if filename not in self._archives:
            path = os.path.join(self.find_directory() or "", filename)
            try: self._archives[filename] = LodArchive(path) if os.path.isfile(path) else None
            except Exception:
                logger.warning("Failed to read %s.", path, exc_info=True)
                self._archives[filename] = None
        return self._archives[filename]


    def get_portrait_name(self, hero_id):
        """Returns the portrait file name for a hero id, or None if unknown."""
        if hero_id < 8 * len(HERO_CLASSES):
            return "HPS%03d%s.pcx" % (hero_id, HERO_CLASSES[hero_id // 8])
        index = hero_id - 8 * len(HERO_CLASSES)
        if index < 8 * len(HERO_CLASSES_RESTARTING):
            return "HPS%03d%s.pcx" % (index % 8, HERO_CLASSES_RESTARTING[index // 8])
        return HERO_PORTRAITS.get(hero_id)


    def get_hero_bitmap(self, hero_id, size=None):
        """Returns wx.Bitmap portrait for a hero id, scaled to size if given, or None."""
        key = (hero_id, size)
        if key not in self._heroes:
            self._heroes[key] = self.scaled(self._load_hero_bitmap(hero_id), size)
        return self._heroes[key]


    def _load_hero_bitmap(self, hero_id):
        if not wx or not self.available(): return None
        name = self.get_portrait_name(hero_id)
        if not name: return None
        for filename in BITMAP_ARCHIVES:
            archive = self.archive(filename)
            if archive and name in archive:
                decoded = decode_pcx(archive.read(name))
                if not decoded: return None
                width, height, rgb = decoded
                return wx.Image(width, height, rgb).ConvertToBitmap()
        return None


    def get_artifact_bitmap(self, artifact_id, size=ICON_SIZE):
        """Returns wx.Bitmap icon for an artifact id, scaled to size, or None."""
        key = (artifact_id, size)
        if key not in self._artifacts:
            self._artifacts[key] = self.scaled(self._load_artifact_bitmap(artifact_id), size)
        return self._artifacts[key]


    def _load_artifact_bitmap(self, artifact_id):
        if not wx or not self.available(): return None
        if self._sprite is None:
            self._sprite = ()
            for filename in SPRITE_ARCHIVES:
                archive = self.archive(filename)
                data = archive.read(ARTIFACT_SPRITE) if archive else None
                if data:
                    palette, offsets = parse_def(data)
                    self._sprite = (data, palette, offsets)
                    break # for filename
        if not self._sprite: return None
        data, palette, offsets = self._sprite
        if not 0 <= artifact_id < min(len(offsets), ARTIFACT_FRAMES): return None
        decoded = decode_def_frame(data, offsets[artifact_id], palette)
        if not decoded: return None
        width, height, rgb, alpha = decoded
        image = wx.Image(width, height, rgb)
        image.SetAlpha(alpha)
        return image.ConvertToBitmap()


    def scaled(self, bitmap, size):
        """Returns the bitmap scaled to fit within (width, height), or None."""
        if not bitmap or not bitmap.IsOk() or not size: return bitmap or None
        w, h = bitmap.Width, bitmap.Height
        ratio = min(float(size[0]) / w, float(size[1]) / h)
        if ratio >= 1: return bitmap
        image = bitmap.ConvertToImage()
        image.Rescale(max(1, int(w * ratio)), max(1, int(h * ratio)), wx.IMAGE_QUALITY_HIGH)
        return image.ConvertToBitmap()


## Singleton instance
DATA = GameData()
