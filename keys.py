from pynput.keyboard import Key as pKey, KeyCode
import os


# <editor-fold desc="KeyMap & population">
all_ckb = []


class Key:
    def __init__(self, ckb=None, key=None):
        self.ckb = ckb
        self.key = key
        if ckb is not None:
            all_ckb.append(ckb)

    def __eq__(self, other):
        return self.key == other


class KeyMap:

    prtscn = Key("prtscn", pKey.print_screen)
    scroll = Key("scroll", pKey.scroll_lock)
    pause = Key("pause", pKey.pause)
    row_psp = [prtscn, scroll, pause]

    ins = Key("ins", pKey.insert)
    home = Key("home", pKey.home)
    pgup = Key("pgup", pKey.page_up)
    row_ihp = [ins, home, pgup]

    delete = Key("del", pKey.delete)
    end = Key("end", pKey.end)
    pgdn = Key("pgdn", pKey.page_down)
    row_dep = [delete, end, pgdn]

    volUp = Key(key=KeyCode(vk=269025043))
    volDn = Key(key=KeyCode(vk=269025041))
    volMute = Key("mute", KeyCode(vk=269025042))

    stop = Key("stop", KeyCode(vk=269025045))
    eject = Key(key=KeyCode(vk=269025068))

    m = Key("m", KeyCode(char="m"))

    nums = [Key(ckb=f"num{i}") for i in range(10)]
# </editor-fold>


# <editor-fold desc="xmodmap/key toggling">
xmodmap = [  # xmodmap -pke
    (118, "Insert NoSymbol Insert"), (110, "Home NoSymbol Home"), (112, "Prior NoSymbol Prior"),
    (119, "Delete NoSymbol Delete"), (115, "End NoSymbol End"),   (117, "Next NoSymbol Next")
]


def toggle_keys(turn_off):
    if turn_off:
        for i in xmodmap:
            os.system(f"xmodmap -e 'keycode {i[0]} = 0x0000'")
    else:
        for i in xmodmap:
            os.system(f"xmodmap -e 'keycode {i[0]} = {i[1]}'")
# </editor-fold>


# <editor-fold desc="Modifier keys">
class Modifier:
    SHIFT = 0
    CTRL = 1
    ALT = 2
    CMD = 3


class ModKey:
    def __init__(self, keys, mod):
        self.keys = keys
        self.full = [False for _ in keys]
        self.mod = mod


class Modifiers:
    keys = [
        ModKey([pKey.shift, pKey.shift_l, pKey.shift_r], Modifier.SHIFT),
        ModKey([pKey.ctrl, pKey.ctrl_l, pKey.ctrl_r], Modifier.CTRL),
        ModKey([pKey.alt, pKey.alt_l, pKey.alt_gr, pKey.alt_r], Modifier.ALT),
        ModKey([pKey.cmd, pKey.cmd_l, pKey.cmd_r], Modifier.CMD)
    ]

    def key(self, modifier):
        for k in self.keys:
            if modifier == k.mod:
                return any(k.full)

    def bin(self):
        out = 0
        for i in [Modifier.SHIFT, Modifier.CTRL, Modifier.ALT, Modifier.CMD]:
            out |= self.key(i) << i
        return out

    def only(self, modifier):
        return self.bin() == 1 << modifier

    def nothing(self):
        return self.bin() == 0

    def exactly(self, modifiers):
        exp = 0
        for i in modifiers:
            exp |= 1 << i
        # print("comp", exp, self.bin(), "in:", modifiers)
        return self.bin() == exp

    def listener(self, key, down):
        for k in self.keys:
            if key in k.keys:
                # print(key, v, down, k.full)
                k.full[k.keys.index(key)] = down
                # print(key, down, k.full, self.bin())

    def __repr__(self):
        return "; ".join([str(k.mod) + ":" + str(any(k.full)) for k in self.keys])
# </editor-fold>
