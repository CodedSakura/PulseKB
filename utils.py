from fnmatch import fnmatch
from typing import Tuple

from keys import KeyMap


def volume_function(v):
    return hsv_to_rgb_str(v / 300, 1, 1, v / 100) if 0 < v <= 100 else \
        hsv_to_rgb_str((v + 60) / 300, 1, 1, 1) if v > 100 else "ff0000ff"


class Setup:
    relevant_sinks = [[]]  # accepts wildcards
    mic_source = ""  # wildcards
    blink_interval = (1000, 1000)  # ms (on time, off time)
    pulse_update_interval = 1000  # ms
    volume_range = (0, 180)
    blinks = {
        "invalid-0": {"key": KeyMap.row_ihp[0].ckb, "color": "ff0000ff"},
        "invalid-1": {"key": KeyMap.row_ihp[1].ckb, "color": "ff0000ff"},
        "invalid-2": {"key": KeyMap.row_ihp[2].ckb, "color": "ff0000ff"},
        "selected-0": {"key": KeyMap.row_ihp[0].ckb, "color": "ffffffff"},
        "selected-1": {"key": KeyMap.row_ihp[1].ckb, "color": "ffffffff"},
        "selected-2": {"key": KeyMap.row_ihp[2].ckb, "color": "ffffffff"},
        "unavailable-0": {"key": KeyMap.row_dep[0].ckb, "color": "ff0000ff"},
        "unavailable-1": {"key": KeyMap.row_dep[1].ckb, "color": "ff0000ff"},
        "unavailable-2": {"key": KeyMap.row_dep[2].ckb, "color": "ff0000ff"},
        "mic-err": {"key": KeyMap.m.ckb, "color": "ff0000ff"},
    }
    state_colors = {}
    sink_input_defaults = []  # (sink_input: str, sink: int)[] accepts wildcards

    def relevancy(self, sink_str: str) -> None or Tuple[int, int]:
        for i1, v1 in enumerate(self.relevant_sinks):
            for i2, v2 in enumerate(v1):
                if fnmatch(sink_str, v2):
                    return i1, i2
        return None


class State:
    DEAD = -1
    INACTIVE = 0
    ACTIVE = 1
    ONE_TIME_S1 = 2
    ONE_TIME_S2 = 3

    def __init__(self, setup: Setup):
        self.state = State.INACTIVE
        self.display = State.ACTIVE
        self.volume = [(0, 0), 0, False, None]  # pos in layout, volume, muted, timer
        self.sink_layouts = [None] * len(setup.relevant_sinks[0])
        self.active_sink = 0
        self.blinking = set()
        self.mic_mute = False


def hsv_to_rgb_str(h: float = 0.0, s: float = 1.0, v: float = 1.0, o: float = 1.0) -> str:
    from colorsys import hsv_to_rgb
    rgb = "".join(map(lambda n: f"{int(n * 255):02x}", hsv_to_rgb(h, s, v)))
    return f"{rgb}{int(o * 255):02x}"


def write_ckb(string_data: str, pipe: str = "001"):
    # print(string_data)
    f = open(f"/tmp/ckbpipe{pipe}", "w")
    f.write(f"rgb {string_data}")
    f.close()


def limit_between(mn, vl, mx):
    return max(mn, min(vl, mx))


def pulse_get_input_sinks(pulse, setup):
    pulse.connect(wait=True)
    sink_list = pulse.sink_list()
    sinks = {i.index: i.name for i in sink_list}
    sink_input_list = pulse.sink_input_list()
    sink_inputs = {
        i.name[25:]: (sinks[i.sink], i)
        for i in sink_input_list
        if i.driver == "module-loopback.c" and setup.relevancy(i.name[25:]) is not None
    }
    combined = {
        sinks[i.sink]: (bool(i.mute), i)
        for i in sink_input_list
        if i.driver == "module-combine-sink.c" and setup.relevancy(sinks[i.sink]) is not None
    }
    return sink_list, sink_inputs, combined
