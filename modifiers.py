from pynput.keyboard import Key


class Modifier:
    shift = 0
    ctrl = 1
    alt = 2
    cmd = 3


class ModKey:
    def __init__(self, keys, mod):
        self.keys = keys
        self.full = [False for _ in keys]
        self.mod = mod


class Modifiers:
    keys = [
        ModKey([Key.shift, Key.shift_l, Key.shift_r], Modifier.shift),
        ModKey([Key.ctrl, Key.ctrl_l, Key.ctrl_r], Modifier.ctrl),
        ModKey([Key.alt, Key.alt_l, Key.alt_gr, Key.alt_r], Modifier.alt),
        ModKey([Key.cmd, Key.cmd_l, Key.cmd_r], Modifier.cmd)
    ]

    def key(self, modifier):
        for k in self.keys:
            if modifier == k.mod:
                return any(k.full)

    def bin(self):
        out = 0
        for i in [Modifier.shift, Modifier.ctrl, Modifier.alt, Modifier.cmd]:
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
