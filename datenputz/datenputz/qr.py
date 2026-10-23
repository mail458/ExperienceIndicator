"""QR-Codes ohne Abhängigkeiten (Byte-Modus, Fehlerkorrektur L/M, Versionen 1–40).

Für ntfy-Abos, WireGuard-Konfigurationen und den Login-Link am Handy.
Tabellen aus ISO/IEC 18004 (Blockaufteilung, Positionen der Ausrichtungsmuster).
"""

RS_BLOCKS = {
    "L": [(1, 26, 19), (1, 44, 34), (1, 70, 55), (1, 100, 80), (1, 134, 108), (2, 86, 68), (2, 98, 78), (2, 121, 97), (2, 146, 116), (2, 86, 68, 2, 87, 69), (4, 101, 81), (2, 116, 92, 2, 117, 93), (4, 133, 107), (3, 145, 115, 1, 146, 116), (5, 109, 87, 1, 110, 88), (5, 122, 98, 1, 123, 99), (1, 135, 107, 5, 136, 108), (5, 150, 120, 1, 151, 121), (3, 141, 113, 4, 142, 114), (3, 135, 107, 5, 136, 108), (4, 144, 116, 4, 145, 117), (2, 139, 111, 7, 140, 112), (4, 151, 121, 5, 152, 122), (6, 147, 117, 4, 148, 118), (8, 132, 106, 4, 133, 107), (10, 142, 114, 2, 143, 115), (8, 152, 122, 4, 153, 123), (3, 147, 117, 10, 148, 118), (7, 146, 116, 7, 147, 117), (5, 145, 115, 10, 146, 116), (13, 145, 115, 3, 146, 116), (17, 145, 115), (17, 145, 115, 1, 146, 116), (13, 145, 115, 6, 146, 116), (12, 151, 121, 7, 152, 122), (6, 151, 121, 14, 152, 122), (17, 152, 122, 4, 153, 123), (4, 152, 122, 18, 153, 123), (20, 147, 117, 4, 148, 118), (19, 148, 118, 6, 149, 119)],
    "M": [(1, 26, 16), (1, 44, 28), (1, 70, 44), (2, 50, 32), (2, 67, 43), (4, 43, 27), (4, 49, 31), (2, 60, 38, 2, 61, 39), (3, 58, 36, 2, 59, 37), (4, 69, 43, 1, 70, 44), (1, 80, 50, 4, 81, 51), (6, 58, 36, 2, 59, 37), (8, 59, 37, 1, 60, 38), (4, 64, 40, 5, 65, 41), (5, 65, 41, 5, 66, 42), (7, 73, 45, 3, 74, 46), (10, 74, 46, 1, 75, 47), (9, 69, 43, 4, 70, 44), (3, 70, 44, 11, 71, 45), (3, 67, 41, 13, 68, 42), (17, 68, 42), (17, 74, 46), (4, 75, 47, 14, 76, 48), (6, 73, 45, 14, 74, 46), (8, 75, 47, 13, 76, 48), (19, 74, 46, 4, 75, 47), (22, 73, 45, 3, 74, 46), (3, 73, 45, 23, 74, 46), (21, 73, 45, 7, 74, 46), (19, 75, 47, 10, 76, 48), (2, 74, 46, 29, 75, 47), (10, 74, 46, 23, 75, 47), (14, 74, 46, 21, 75, 47), (14, 74, 46, 23, 75, 47), (12, 75, 47, 26, 76, 48), (6, 75, 47, 34, 76, 48), (29, 74, 46, 14, 75, 47), (13, 74, 46, 32, 75, 47), (40, 75, 47, 7, 76, 48), (18, 75, 47, 31, 76, 48)],
}
ALIGN = [[], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50], [6, 30, 54], [6, 32, 58], [6, 34, 62], [6, 26, 46, 66], [6, 26, 48, 70], [6, 26, 50, 74], [6, 30, 54, 78], [6, 30, 56, 82], [6, 30, 58, 86], [6, 34, 62, 90], [6, 28, 50, 72, 94], [6, 26, 50, 74, 98], [6, 30, 54, 78, 102], [6, 28, 54, 80, 106], [6, 32, 58, 84, 110], [6, 30, 58, 86, 114], [6, 34, 62, 90, 118], [6, 26, 50, 74, 98, 122], [6, 30, 54, 78, 102, 126], [6, 26, 52, 78, 104, 130], [6, 30, 56, 82, 108, 134], [6, 34, 60, 86, 112, 138], [6, 30, 58, 86, 114, 142], [6, 34, 62, 90, 118, 146], [6, 30, 54, 78, 102, 126, 150], [6, 24, 50, 76, 102, 128, 154], [6, 28, 54, 80, 106, 132, 158], [6, 32, 58, 84, 110, 136, 162], [6, 26, 54, 82, 110, 138, 166], [6, 30, 58, 86, 114, 142, 170]]

ECC_BITS = {"L": 1, "M": 0}

# --- Reed-Solomon über GF(256), Polynom 0x11D -------------------------------
_EXP, _LOG = [0] * 512, [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _generator(n):
    g = [1]
    for i in range(n):
        g = [a ^ _mul(b, _EXP[i]) for a, b in zip(g + [0], [0] + g)]
    return g


def _ecc(data, n):
    gen = _generator(n)
    rem = list(data) + [0] * n
    for i in range(len(data)):
        coef = rem[i]
        if coef:
            for j, g in enumerate(gen):
                rem[i + j] ^= _mul(g, coef)
    return rem[len(data):]


# --- Kodierung --------------------------------------------------------------
def _blocks(version, level):
    t = RS_BLOCKS[level][version - 1]
    out = []
    for i in range(0, len(t), 3):
        count, total, data = t[i:i + 3]
        out += [(total, data)] * count
    return out


def _capacity(version, level):
    return sum(d for _, d in _blocks(version, level))


def _codewords(data, version, level):
    ccbits = 8 if version < 10 else 16
    bits = [0, 1, 0, 0] + [(len(data) >> i) & 1 for i in reversed(range(ccbits))]
    for byte in data:
        bits += [(byte >> i) & 1 for i in reversed(range(8))]
    cap = _capacity(version, level) * 8
    bits += [0] * min(4, cap - len(bits))
    bits += [0] * (-len(bits) % 8)
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0
    while len(words) < cap // 8:
        words.append((0xEC, 0x11)[pad % 2])
        pad += 1
    blocks, pos = [], 0
    for total, n in _blocks(version, level):
        blocks.append((words[pos:pos + n], _ecc(words[pos:pos + n], total - n)))
        pos += n
    out = []
    for i in range(max(len(d) for d, _ in blocks)):
        out += [d[i] for d, _ in blocks if i < len(d)]
    for i in range(len(blocks[0][1])):
        out += [e[i] for _, e in blocks]
    return out


class QR:
    def __init__(self, text, level="M", mask=None):
        data = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        for v in range(1, 41):
            need = 4 + (8 if v < 10 else 16) + 8 * len(data)
            if need <= _capacity(v, level) * 8:
                break
        else:
            raise ValueError("Text zu lang für einen QR-Code")
        self.version, self.level = v, level
        self.size = 17 + 4 * v
        self._modules = [[False] * self.size for _ in range(self.size)]
        self._function = [[False] * self.size for _ in range(self.size)]
        self._draw_function_patterns()
        self._place(_codewords(data, v, level))
        if mask is None:
            mask = min(range(8), key=self._trial_penalty)
        self.mask = mask
        self._apply_mask(mask)
        self._draw_format(mask)

    # Hilfen
    def _set(self, x, y, dark):
        self._modules[y][x] = dark
        self._function[y][x] = True

    def _draw_function_patterns(self):
        s = self.size
        for i in range(s):
            self._set(6, i, i % 2 == 0)
            self._set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (s - 4, 3), (3, s - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < s and 0 <= y < s:
                        self._set(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = ALIGN[self.version - 1]
        last = len(pos) - 1
        for i, a in enumerate(pos):
            for j, b in enumerate(pos):
                if (i, j) in ((0, 0), (0, last), (last, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self._set(a + dx, b + dy, max(abs(dx), abs(dy)) != 1)
        self._draw_format(0)  # reserviert die Formatbereiche
        if self.version >= 7:
            rem = self.version
            for _ in range(12):
                rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
            bits = self.version << 12 | rem
            for i in range(18):
                bit = (bits >> i) & 1 == 1
                a, b = s - 11 + i % 3, i // 3
                self._set(a, b, bit)
                self._set(b, a, bit)

    def _draw_format(self, mask):
        data = ECC_BITS[self.level] << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        s = self.size

        def bit(i):
            return (bits >> i) & 1 == 1
        for i in range(6):
            self._set(8, i, bit(i))
        self._set(8, 7, bit(6))
        self._set(8, 8, bit(7))
        self._set(7, 8, bit(8))
        for i in range(9, 15):
            self._set(14 - i, 8, bit(i))
        for i in range(8):
            self._set(s - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self._set(8, s - 15 + i, bit(i))
        self._set(8, s - 8, True)

    def _place(self, words):
        s, i, total = self.size, 0, len(words) * 8
        right = s - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(s):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = s - 1 - vert if upward else vert
                    if not self._function[y][x]:
                        if i < total:
                            self._modules[y][x] = (words[i >> 3] >> (7 - (i & 7))) & 1 == 1
                        i += 1
            right -= 2

    @staticmethod
    def _mask_bit(mask, y, x):
        return (
            (x + y) % 2 == 0, y % 2 == 0, x % 3 == 0, (x + y) % 3 == 0,
            (x // 3 + y // 2) % 2 == 0, x * y % 2 + x * y % 3 == 0,
            (x * y % 2 + x * y % 3) % 2 == 0, ((x + y) % 2 + x * y % 3) % 2 == 0,
        )[mask]

    def _apply_mask(self, mask):
        for y in range(self.size):
            for x in range(self.size):
                if not self._function[y][x] and self._mask_bit(mask, y, x):
                    self._modules[y][x] = not self._modules[y][x]

    def _trial_penalty(self, mask):
        self._apply_mask(mask)
        self._draw_format(mask)
        p = self._penalty()
        self._apply_mask(mask)  # XOR rückgängig machen
        return p

    def _penalty(self):
        m, s, p = self._modules, self.size, 0
        lines = m + [list(col) for col in zip(*m)]
        for line in lines:  # Regel 1: Läufe gleicher Farbe; Regel 3: Finder-ähnliche Muster
            run, prev = 0, None
            for v in line:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        p += run - 2
                    run, prev = 1, v
            if run >= 5:
                p += run - 2
            row = "".join("1" if v else "0" for v in line)
            p += 40 * (row.count("10111010000") + row.count("00001011101"))
        for y in range(s - 1):  # Regel 2: 2×2-Blöcke
            for x in range(s - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    p += 3
        dark = sum(map(sum, m))  # Regel 4: Verhältnis hell/dunkel
        k = abs(dark * 20 - s * s * 10) // (s * s)
        return p + k * 10

    # --- Ausgabe -------------------------------------------------------------
    @property
    def matrix(self):
        return [row[:] for row in self._modules]

    def svg(self, border=4, scale=1, title="QR-Code"):
        n = self.size + 2 * border
        path = "".join(f"M{x + border},{y + border}h1v1h-1z" for y, row in enumerate(self._modules)
                       for x, v in enumerate(row) if v)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{n * scale}" height="{n * scale}" '
                f'role="img" aria-label="{title}" shape-rendering="crispEdges"><rect width="{n}" height="{n}" '
                f'fill="#fff"/><path d="{path}" fill="#000"/></svg>')

    def terminal(self, border=2):
        """Halbblöcke mit festen Farben (schwarz auf weiß) – unabhängig vom Terminal-Design."""
        s = self.size + 2 * border

        def dark(x, y):
            x, y = x - border, y - border
            return 0 <= x < self.size and 0 <= y < self.size and self._modules[y][x]
        lines = []
        for y in range(0, s, 2):
            line = []
            for x in range(s):
                top, bottom = dark(x, y), y + 1 < s and dark(x, y + 1)
                line.append(f"\033[{30 if top else 97};{40 if bottom else 107}m▀")
            lines.append("".join(line) + "\033[0m")
        return "\n".join(lines)


def svg(text, level="M", scale=4, title="QR-Code"):
    return QR(text, level).svg(scale=scale, title=title)
