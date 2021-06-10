from fnmatch import fnmatch

from pulsectl import Pulse

mic = "alsa_input.pci-0000_00_1f.3.analog-stereo"

if __name__ == '__main__':
    with Pulse() as pulse:
        mic_source = [p for p in pulse.source_list() if fnmatch(p.name, mic)]
        if len(mic_source) > 0:
            pulse.mute(mic_source[0], not bool(mic_source[0].mute))
