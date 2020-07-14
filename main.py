import os
from fnmatch import fnmatch
from threading import Thread, Timer
from time import sleep

from pulsectl import Pulse
from pynput.keyboard import Listener

import micmute
from keys import Modifier, Modifiers, KeyMap, toggle_keys, all_ckb
from utils import State, write_ckb, Setup, limit_between, volume_function

"""
General behavior:
volume scroll/mute, as before (color adjusts), numpad lights
pps row - as before, (active)[[music, game, discord],[speakers,headset,?BT]]{none,ctrl}
ihp row - select (active)[music, game, discord] / shows color accordingly
dep row - edit selected to (active)[speakers,headset,?BT] <set,toggle>{none,ctrl} / rgb
stop - [one-time,toggle,lights]{none,ctrl,shift}
meta+m - mute mic, show light on 'm' (red: muted, green: unmuted)
"""

# accepts wildcards
setup = Setup()
setup.relevant_sinks = [
    ["Music", "Game", "Discord"],
    [
        "alsa_output.pci-0000_01_00.1.hdmi-*",
        "alsa_output.pci-0000_00_1f.3.analog-stereo",
        "bluez_sink.38_18_4C_BF_47_B8.*"
    ]
]
setup.mic_source = micmute.mic
setup.blink_interval = (250, 500)  # ms (on time, off time)
setup.pulse_update_interval = 500
setup.state_colors = {
    State.INACTIVE: '0000ff88', State.ACTIVE: '00ffffff',
    State.ONE_TIME_S1: 'ffff00ff', State.ONE_TIME_S2: '00ff00ff'
}
setup.sink_input_defaults = [
    ("Google Chrome", 0),
    ("*Celluloid", 0),
    ("kdenlive", 0),
    ("Steam", 1),
    ("*VoiceEngine", 2),
    ("Chromium", 2),
    ("*", 1),
]

ckb_pipe = "001"
mod = Modifiers()
keymap = KeyMap()
state = State(setup)


def display(clear_all: bool = False):
    ckb_out = {i: "00000000" for i in all_ckb}
    if clear_all:
        write_ckb(" ".join([f"{k}:{v}" for k, v in ckb_out.items()]), ckb_pipe)
        return
    ckb_out[keymap.stop.ckb] = setup.state_colors[state.state]

    if state.display != State.INACTIVE or state.state != State.INACTIVE:
        sink_colors = [
            (f"{sum(0xff0000 >> i * 8 for i in (x or [])):06x}ff" if (x or [0])[0] != -1 else None)
            for x in state.sink_layouts
        ]
        for k, v in enumerate(keymap.row_ihp):
            if sink_colors[k] is not None:
                ckb_out[v.ckb] = sink_colors[k]

        # if state.state == State.ACTIVE:
        #     ckb_out[keymap.row_ihp[state.active_sink].ckb] = "00000000"

        ckb_out[keymap.row_psp[state.volume[0][1]].ckb] = ["ffffff88", "ffff0088"][state.volume[0][0]]

    if state.volume[2]:
        ckb_out[keymap.volMute.ckb] = "ff0000ff"
    else:
        if state.display != State.INACTIVE or state.state != State.INACTIVE:
            digits = {i.ckb: 0 for i in keymap.nums}
            for i in range(3):
                digits[keymap.nums[(state.volume[1] // 10**i) % 10].ckb] += [0x0000ff, 0x00ff00, 0xff0000][i]
            for k, v in digits.items():
                ckb_out[k] = f"{v:06x}ff"
        ckb_out[keymap.volMute.ckb] = volume_function(state.volume[1])

    if state.mic_mute is not None:
        ckb_out[keymap.m.ckb] = 'ff0000b0' if state.mic_mute else '00ff00b0'

    for i in state.blinking:
        blink = setup.blinks[i]
        if "key" in blink:
            ckb_out[blink['key']] = "00000000"
        elif "keys" in blink:
            ckb_out.update({k: "00000000" for k in blink["keys"]})

    write_ckb(" ".join([f"{k}:{v}" for k, v in ckb_out.items()]), ckb_pipe)


# <editor-fold desc="Key checks">
# screenshot shortcuts
def screenshot_check(key):
    if state.state != State.INACTIVE:
        return
    if keymap.prtscn == key and mod.nothing():
        os.system("mate-screenshot -a")
    elif keymap.prtscn == key and mod.only(Modifier.CTRL):
        os.system("mate-screenshot")
    elif keymap.prtscn == key and mod.only(Modifier.SHIFT):
        os.system("mate-screenshot -w")


def volume_check(key):
    change = 2
    if mod.only(Modifier.SHIFT):
        change = 5
    if mod.only(Modifier.CTRL):
        change = 1

    if keymap.volUp == key:
        state.volume[1] += change
    elif keymap.volDn == key:
        state.volume[1] -= change
    elif keymap.volMute == key:
        state.volume[2] = not state.volume[2]
    else:
        return
    state.volume[1] = limit_between(setup.volume_range[0], state.volume[1], setup.volume_range[1])
    with Pulse() as pulse:
        curr_sink = [i for i in pulse.sink_list() if setup.relevancy(i.name) == state.volume[0]]
        if len(curr_sink) == 0:
            state.volume[2] = True
            return
        pulse.volume_set_all_chans(curr_sink[0], state.volume[1]/100)
        pulse.mute(curr_sink[0], state.volume[2])
    if state.volume[3]:
        state.volume[3].cancel()
    state.volume[3] = Timer(1 / 30, display)
    state.volume[3].start()
    # display()


def activate_check(key):
    if keymap.stop == key:
        if mod.nothing():
            if state.state != State.INACTIVE:
                state.state = State.INACTIVE
                toggle_keys(False)
                for i in range(3):
                    state.blinking.discard(f"selected-{i}")
            else:
                state.state = State.ONE_TIME_S1
                toggle_keys(True)
        elif mod.only(Modifier.CTRL):
            state.display = State.ACTIVE if state.display == State.INACTIVE else State.INACTIVE
        display()
    elif keymap.eject == key:
        if state.state == State.INACTIVE:
            state.state = State.ACTIVE
            state.blinking.add(f"selected-{state.active_sink}")
        else:
            state.state = State.INACTIVE
            for i in range(3):
                state.blinking.discard(f"selected-{i}")
        toggle_keys(state.state != State.INACTIVE)
        display()


def key_check(key):
    if state.state in (State.INACTIVE, State.DEAD):
        return
    if key in keymap.row_psp:
        if mod.nothing():
            row = 0
        elif mod.only(Modifier.CTRL):
            row = 1
        else:
            return
        state.volume[0] = (row, keymap.row_psp.index(key))
    elif key in keymap.row_ihp:
        if state.state == State.ONE_TIME_S1:
            state.state = State.ONE_TIME_S2
        elif state.state != State.ACTIVE:
            return
        for i in range(3):
            state.blinking.discard(f"selected-{i}")
        state.active_sink = keymap.row_ihp.index(key)
        state.blinking.add(f"selected-{state.active_sink}")
        display()
    elif key in keymap.row_dep:
        with Pulse() as pulse:
            sink_input_list = pulse.sink_input_list()
            sink_input_relevancy = [(setup.relevancy(i.name[25:]), i) for i in sink_input_list]
            sink_inputs = {i[0][1]: i[1] for i in sink_input_relevancy if i[0] is not None}
            sink_list = pulse.sink_list()
            sink_relevancy = [(setup.relevancy(i.name), i) for i in sink_list]
            sinks = {i[0][1]: i[1] for i in sink_relevancy if i[0] is not None and i[0][0] == 1}
            selected_index = keymap.row_dep.index(key)
            if state.state == State.ONE_TIME_S1:
                state.state = State.INACTIVE
                toggle_keys(False)
                if mod.nothing():
                    if selected_index not in sinks:
                        return
                    for _, v in sink_inputs.items():
                        pulse.sink_input_move(v.index, sinks[selected_index].index)
                elif mod.only(Modifier.CTRL):
                    # TODO:
                    print("if any sink_input not set to combined:")
                    print(f"  set all sink_inputs to combined, mute [combined] all except {selected_index}")
                    print("else:")
                    print(f"  unmute/mute [combined] {selected_index}")
            elif state.state in (State.ONE_TIME_S2, State.ACTIVE):
                if state.state == State.ONE_TIME_S2:
                    state.state = State.INACTIVE
                    for i in range(3):
                        state.blinking.discard(f"selected-{i}")
                    toggle_keys(False)
                if mod.nothing():
                    if selected_index not in sinks:
                        return
                    pulse.sink_input_move(sink_inputs[state.active_sink].index, sinks[selected_index].index)
                elif mod.only(Modifier.CTRL):
                    # TODO:
                    print(f"if {state.active_sink} not set to combined:")
                    print(f"  set {state.active_sink} to combined, mute [combined] all except prev and "
                          f"{selected_index}")
                    print("else:")
                    print(f"  unmute/mute [combined] {selected_index}")

        display()


def mute_check(key):
    # print(key == keymap.m.key, mod)
    if keymap.m == key and mod.exactly([Modifier.CMD, Modifier.ALT]):
        # print("*")
        # with Pulse() as pulse:
        #     mic_source = [p for p in pulse.source_list() if fnmatch(p.name, setup.mic_source)]
        #     if len(mic_source) > 0:
        #         pulse.mute(mic_source[0], not bool(mic_source[0].mute))
        pass
# </editor-fold>


# <editor-fold desc="Loops">
def blink_loop():
    def blinking():
        try:
            while state.state != State.DEAD:
                ckb = dict()
                for i in state.blinking:
                    blink = setup.blinks[i]
                    if "key" in blink:
                        ckb[blink['key']] = blink['color']
                    elif "keys" in blink:
                        ckb.update({k: blink['color'] for k in blink["keys"]})
                write_ckb(" ".join([f"{k}:{c}" for k, c in ckb.items()]), ckb_pipe)
                sleep(setup.blink_interval[0] / 1000)
                write_ckb(" ".join([f"{k}:00000000" for k, c in ckb.items()]), ckb_pipe)
                sleep(setup.blink_interval[1] / 1000)
        except KeyboardInterrupt:
            pass
    thr = Thread(target=blinking)
    thr.start()
    return thr


def pulse_loop():
    def update_from_pulse(pulse):
        pulse.connect(wait=True)
        sink_list = pulse.sink_list()
        sinks = {i.index: i.name for i in sink_list}
        sink_relevancy = [(setup.relevancy(i.name), i) for i in sink_list]
        indexed_sinks = {i[0]: i[1].index for i in sink_relevancy if i[0] is not None}
        sink_input_list = pulse.sink_input_list()
        sink_inputs = {
            i.name[25:]: sinks[i.sink]
            for i in sink_input_list
            if i.driver == "module-loopback.c" and setup.relevancy(i.name[25:]) is not None
        }
        combined = {
            sinks[i.sink]: bool(i.mute)
            for i in sink_input_list
            if i.driver == "module-combine-sink.c" and setup.relevancy(sinks[i.sink]) is not None
        }
        for i, s in sink_inputs.items():
            pos_a = setup.relevancy(i)[1]
            if s == "combined":
                pos_b = [setup.relevancy(i)[1] for i, b in combined.items() if not b]
            else:
                r = setup.relevancy(s)
                pos_b = [r[1] if r is not None and r[0] != 0 else -1]
            state.sink_layouts[pos_a] = pos_b
            if (len(pos_b) == 0 or pos_b[0] == -1) and f"invalid-{pos_a}" not in state.blinking:
                state.blinking.add(f"invalid-{pos_a}")
            elif pos_b[0] != -1 and f"invalid-{pos_a}" in state.blinking:
                state.blinking.remove(f"invalid-{pos_a}")

        for s in sink_list:
            if setup.relevancy(s.name) == state.volume[0]:
                state.volume[1] = round(sum(s.volume.values) / len(s.volume.values) * 100)
                state.volume[2] = bool(s.mute)

        for si in sink_input_list:
            if si.name.startswith("Loopback") or si.driver == "module-combine-sink.c":
                continue
            relevancy = setup.relevancy(sinks[si.sink])
            if relevancy is not None and relevancy[0] != 1:
                continue
            for i in setup.sink_input_defaults:
                if fnmatch(si.proplist["application.name"], i[0]):
                    print(si.proplist["application.name"], "->", setup.relevant_sinks[0][i[1]])
                    pulse.sink_input_move(si.index, indexed_sinks[0, i[1]])
                    break
        mic_source = [p for p in pulse.source_list() if fnmatch(p.name, setup.mic_source)]
        if len(mic_source) == 0:
            state.blinking.add("mic-err")
            state.mic_mute = None
        else:
            if "mic-err" in state.blinking:
                state.blinking.remove("mic-err")
            state.mic_mute = bool(mic_source[0].mute)
        display()

    def loop():
        try:
            with Pulse() as pulse:
                while state.state != State.DEAD:
                    update_from_pulse(pulse)
                    sleep(setup.pulse_update_interval / 1000)
        except KeyboardInterrupt:
            pass
    thr = Thread(target=loop)
    thr.start()
    return thr
# </editor-fold>


def shutdown():
    global state
    state.state = State.DEAD
    state.display = State.INACTIVE
    toggle_keys(False)
    display(clear_all=True)
    exit()


def key_down(key):
    mod.listener(key, True)
    screenshot_check(key)
    volume_check(key)
    # mute_check(key)
    activate_check(key)
    key_check(key)


def key_up(key):
    mod.listener(key, False)


pulse_tread = pulse_loop()
blink_tread = blink_loop()
toggle_keys(False)
try:
    with Listener(on_press=key_down, on_release=key_up) as listener:
        print("Startup: OK")
        listener.join()
except KeyboardInterrupt:
    shutdown()
