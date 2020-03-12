from pynput.keyboard import Key, Listener, KeyCode
from threading import Thread, Timer
from colorsys import hsv_to_rgb
from pulsectl import Pulse
from time import sleep
import os

from modifiers import Modifiers, Modifier


def ckb(txt):
    sleep(1 / 30)
    print("rgb " + txt, file=open("/tmp/ckbpipe001", "w"))


def hsv_to_rgb_str(h=0.0, s=1.0, v=1.0, o=1.0):
    rgb = "".join(map(lambda n: f"{int(n*255):02x}", hsv_to_rgb(h, s, v)))
    return f"{rgb}{int(o*255):02x}"


class KeyCombo:
    def __init__(self, ckb_text, key):
        self.ckb = ckb_text
        self.key = key


class SinkControl:
    def __init__(self, sink, keys):
        self.sink = sink
        self.keys = keys
        self.active = None


class Config:
    pass


settings = Config()
settings.sinkOrder = [
    'alsa_output.pci-0000_00_1f.3.analog-stereo', 'combined', 'alsa_output.pci-0000_01_00.1.hdmi-stereo-extra1'
]
settings.secondarySinkOrder = ['Music', 'Game', 'Discord']
settings.globalSinkOrder = settings.sinkOrder + settings.secondarySinkOrder
settings.sinks = [
    SinkControl("Music", [KeyCombo("ins", Key.insert), KeyCombo("home", Key.home), KeyCombo("pgup", Key.page_up)]),
    SinkControl("Game", [KeyCombo("del", Key.delete), KeyCombo("end", Key.end), KeyCombo("pgdn", Key.page_down)])
]
settings.secondarySinkModifiers = [Modifier.ctrl]
settings.displayKeys = [
    KeyCombo("prtscn", Key.print_screen), KeyCombo("scroll", Key.scroll_lock), KeyCombo("pause", Key.pause)
]

settings.volumeKeys = {KeyCode(vk=269025041): -1, KeyCode(vk=269025043): +1}
settings.maxVolume = 150
settings.volumeKey = KeyCombo("mute", KeyCode(vk=269025042))
settings.toggleKey = KeyCombo("stop", KeyCode(vk=269025045))
settings.subactiveModifiers = [Modifier.ctrl]
settings.volumeDigits = ["num0", "num1", "num2", "num3", "num4", "num5", "num6", "num7", "num8", "num9"]
settings.volumeDigitsModifiers = [Modifier.cmd]

settings.colors = Config()
settings.colors.active = {(True, False): "00ff00ff", (False, True): "0000ffff", (True, True): "00ffffff"}
settings.colors.activeSink = ["ffffff", "ffff00"]
settings.colors.volumeDigits = [0x0000ff, 0x00ff00, 0xff0000]
settings.colors.sinkOutput = "00ffff"
settings.colors.off = "00000000"

settings.colors.volumeFn = lambda v: \
    hsv_to_rgb_str(v/300, 1, 1, v/100) if 0 < v <= 100 else \
    hsv_to_rgb_str((v+60)/300, 1, 1, 1) if v > 100 else "ff0000ff"

settings.xmodmap = [  # xmodmap -pke
    (118, "Insert NoSymbol Insert"), (110, "Home NoSymbol Home"), (112, "Prior NoSymbol Prior"),
    (119, "Delete NoSymbol Delete"), (115, "End NoSymbol End"),   (117, "Next NoSymbol Next")
]


mod = Modifiers()
active = False
subactive = True
showVolumeDigits = True
activeSink = 3
volumeList = [-1] * len(settings.globalSinkOrder)
muteList = [False] * len(settings.globalSinkOrder)
volumeTimer = None


def shortcut(key):
    if active:
        return
    if key == Key.print_screen and mod.nothing():
        os.system("mate-screenshot -a")
    elif key == Key.print_screen and mod.only(Modifier.ctrl):
        os.system("mate-screenshot")


def volume(key):
    global volumeTimer
    if key in settings.volumeKeys:
        volumeList[activeSink] = max(0, min(volumeList[activeSink] + settings.volumeKeys[key], settings.maxVolume))
    elif key == settings.volumeKey.key:
        muteList[activeSink] = not muteList[activeSink]
    else:
        return
    with Pulse() as pulse:
        curr_sink = {i.name: i for i in pulse.sink_list()}[settings.globalSinkOrder[activeSink]]
        pulse.volume_set_all_chans(curr_sink, volumeList[activeSink]/100)
        pulse.mute(curr_sink, muteList[activeSink])
        # pulse.sink_volume_set
    if volumeTimer:
        volumeTimer.cancel()
    volumeTimer = Timer(1 / 30, display)
    volumeTimer.start()
    # display()


def set_output_sink(key):
    for i in settings.sinks:
        keys = [j.key for j in i.keys]
        if key in keys:
            with Pulse() as pulse:
                sink_inputs = {i.name[25:]: i.index for i in pulse.sink_input_list() if i.name.startswith("Loopback")}
                sinks = {i.name: i.index for i in pulse.sink_list()}
                pulse.sink_input_move(sink_inputs[i.sink], sinks[settings.sinkOrder[keys.index(key)]])
                update_from_pulse()


def display(exiting=False):
    out = {i.ckb: settings.colors.off for i in (
            settings.displayKeys +
            [b for a in settings.sinks for b in a.keys] +
            [settings.toggleKey, settings.volumeKey]
    )}
    out.update({i: settings.colors.off for i in settings.volumeDigits})
    if exiting:
        ckb(" ".join(["%s:%s" % (k, v) for k, v in out.items()]))
        return

    curr_vol = volumeList[activeSink] * (not muteList[activeSink])
    if active or subactive:
        out[settings.toggleKey.ckb] = settings.colors.active[active, subactive]
        out[settings.displayKeys[activeSink % len(settings.sinkOrder)].ckb] = \
            settings.colors.activeSink[activeSink // len(settings.sinkOrder)] + ("ff" if active else "80")
        for i in settings.sinks:
            out[i.keys[settings.sinkOrder.index(i.active)].ckb] = \
                settings.colors.sinkOutput + ("ff" if active else "80")
        if showVolumeDigits:
            digits = {i: 0 for i in settings.volumeDigits}
            for i in range(3):
                digits[settings.volumeDigits[(curr_vol // 10**i) % 10]] += settings.colors.volumeDigits[i]
            for k, v in digits.items():
                out[k] = f"{v:06x}{'ff' if active else '80'}"
    out[settings.volumeKey.ckb] = settings.colors.volumeFn(curr_vol)

    ckb(" ".join(["%s:%s" % (k, v) for k, v in out.items()]))


def disable_keys():
    if active:
        for i in settings.xmodmap:
            os.system(f"xmodmap -e 'keycode {i[0]} = 0x0000'")
    else:
        for i in settings.xmodmap:
            os.system(f"xmodmap -e 'keycode {i[0]} = {i[1]}'")


def check_activate(key):
    global active, subactive, showVolumeDigits
    if key == settings.toggleKey.key:
        if mod.nothing():
            active = not active
            update_from_pulse()
            disable_keys()
        elif mod.exactly(settings.subactiveModifiers):
            subactive = not subactive
            update_from_pulse()
        elif mod.exactly(settings.volumeDigitsModifiers):
            showVolumeDigits = not showVolumeDigits
            display()
        elif mod.exactly([Modifier.cmd]):
            os.system("paprefs")
        elif mod.exactly([Modifier.ctrl, Modifier.alt]):
            os.system("pulseaudio -k")
        elif mod.exactly([Modifier.alt, Modifier.cmd]):
            shutdown()


def set_active_sink(key):
    global activeSink
    keys = [k.key for k in settings.displayKeys]
    if key in keys:
        if mod.nothing():
            activeSink = keys.index(key)
        elif mod.exactly(settings.secondarySinkModifiers):
            activeSink = keys.index(key) + len(keys)
        display()


def key_down(key):
    mod.listener(key, True)
    shortcut(key)
    volume(key)
    check_activate(key)
    if active:
        set_active_sink(key)
        set_output_sink(key)


def key_up(key):
    mod.listener(key, False)


def update_from_pulse():
    with Pulse() as pulse:
        sink_list = pulse.sink_list()
        sinks = {i.index: i.name for i in sink_list}
        sink_inputs = {i.name[25:]: i for i in pulse.sink_input_list() if i.name.startswith("Loopback")}
        for s in settings.sinks:
            s.active = sinks[sink_inputs[s.sink].sink]
        for s in sink_list:
            if s.name in settings.globalSinkOrder:
                index = settings.globalSinkOrder.index(s.name)
                volumeList[index] = round(sum(s.volume.values) / len(s.volume.values) * 100)
                muteList[index] = bool(s.mute)
        display()


def ufp_loop():
    try:
        while True:
            update_from_pulse()
            sleep(1)
    except KeyboardInterrupt:
        exit()


def shutdown():
    global active, subactive, volumeList
    active = False
    subactive = False
    disable_keys()
    display(exiting=True)
    exit()


thr = Thread(target=ufp_loop)
thr.start()
disable_keys()
try:
    with Listener(on_press=key_down, on_release=key_up) as listener:
        listener.join()
except KeyboardInterrupt:
    shutdown()
