import numpy as np
import h5py as h5
import h5py
import os
import epics
import epics.devices
import sys
import matplotlib as mpl
import matplotlib.pyplot as plt
import time
import warnings

sys.path.append(os.path.dirname(__file__))
try:
    import stellarnet_driver3 as sn  # usb driver
    STELLARNET_AVAILABLE = True
except:
    warnings.warn("stellarnet_driver3 not available, XEOL will not be available")
    STELLARNET_AVAILABLE = False
# you cant import stellarnet unless you are in the right directory regardless of env


class Stellarnet:
    """Object to interface with Stellarnet spectrometer"""

    def __init__(self, address="ttyS0"):
        self.id, self.__wl = sn.array_get_spec(address)
        self.SETTING_DELAY = (
            0.2  # seconds between changing a setting and having it take effect
        )

        print("Connected to spectrometer")
        self.dwelltime = 100 # ms
        self.numscans = 1  # one scan per spectrum
        self.smooth = 0  # smoothing factor, units unclear

        self.__baseline_dark = {}
        self.__baseline_light = {}

    ##
    # function to convert dict to .h5 from
    # https://codereview.stackexchange.com/questions/120802/recursively-save-python-dictionaries-to-hdf5-files-using-h5py/121308

    def save_dict_to_hdf5(self, dic, filename):
        """
        ....
        """
        with h5py.File(filename, "w") as h5file:
            self.recursively_save_dict_contents_to_group(h5file, "/", dic)

    def recursively_save_dict_contents_to_group(self, h5file, path, dic):
        """
        ....
        """
        for key, item in dic.items():
            if isinstance(item, (np.ndarray, np.int64, np.float64, str, bytes)):
                h5file[path + key] = item
            elif isinstance(item, dict):
                self.recursively_save_dict_contents_to_group(
                    h5file, path + key + "/", item
                )
            else:
                raise ValueError("Cannot save %s type" % type(item))

    def load_dict_from_hdf5(self, filename):
        """
        ....
        """
        with h5py.File(filename, "r") as h5file:
            return self.recursively_load_dict_contents_from_group(h5file, "/")

    def recursively_load_dict_contents_from_group(self, h5file, path):
        """
        ....
        """
        ans = {}
        for key, item in h5file[path].items():
            if isinstance(item, h5py._hl.dataset.Dataset):
                ans[key] = item.value
            elif isinstance(item, h5py._hl.group.Group):
                ans[key] = self.recursively_load_dict_contents_from_group(
                    h5file, path + key + "/"
                )
        return ans

    def open_h5(self, filename):
        out = {}
        with h5py.File(filename, "r") as dat:
            out["wavelength"] = dat["wavelength"][:]
            out["time_data"] = dat["time_data"][:]

        return out

    @property
    def dwelltime(self):
        return self.__integrationtime

    @dwelltime.setter
    def dwelltime(self, t):
        self.id["device"].set_config(int_time=int(t))
        time.sleep(self.SETTING_DELAY)
        self.__integrationtime = t

    @property
    def numscans(self):
        return self.__numscans

    @numscans.setter
    def numscans(self, n):
        self.id["device"].set_config(scans_to_avg=n)
        time.sleep(self.SETTING_DELAY)
        self.__numscans = n

    @property
    def smooth(self):
        return self.__smooth

    @smooth.setter
    def smooth(self, n):
        if n not in [0, 1, 2, 3, 4]:
            raise ValueError("Smoothing factor must be 0, 1, 2, 3, or 4")
        self.id["device"].set_config(x_smooth=n)
        time.sleep(self.SETTING_DELAY)
        self.__smooth = n

    def take_light_baseline(self, skip_repeats=False):
        """takes an illuminated baseline at each integration time from HDR timings"""
        numscans0 = self.numscans
        self.numscans = 3
        for t in self._hdr_times:
            if skip_repeats and t in self.__baseline_light:
                continue  # already taken
            self.dwelltime = t
            wl, cts = self._capture_raw()
            self.__baseline_light[t] = cts
        self.numscans = numscans0

    def take_dark_baseline(self, skip_repeats=False):
        """takes an dark baseline at each integration time from HDR timings"""
        numscans0 = self.numscans
        self.numscans = 3
        for t in self._hdr_times:
            if skip_repeats and t in self.__baseline_dark:
                continue  # already taken
            self.dwelltime = t
            wl, cts = self._capture_raw()
            self.__baseline_dark[t] = cts
        self.numscans = numscans0

    def __is_dark_baseline_taken(self, dwelltime=None):
        """Check whether a baseline has been taken at the current integration time
        Raises:
            ValueError: Dark baseline has not been taken at the current integration time
        Returns True if dark baseline has been taken at the current integration time
        """
        if dwelltime is None:
            dwelltime = self.dwelltime
        if dwelltime not in self.__baseline_dark:
            raise ValueError(
                f"Dark baseline not taken for current integration time ({self.dwelltime} ms). Taken for {list(self.__baseline_dark.keys())}"
            )

        return True

    def __is_light_baseline_taken(self, dwelltime=None):
        """Check whether a baseline has been taken at the current integration time
        Raises:
            ValueError: Light baseline has not been taken at the current integration time
        Returns True if light baseline has been taken at the current integration time
        """
        if dwelltime is None:
            dwelltime = self.dwelltime
        if dwelltime not in self.__baseline_light:
            raise ValueError(
                f"Illuminated baseline not taken for current integration time ({self.dwelltime}). Taken for {list(self.__baseline_light.keys())}"
            )

        return True

    # first taking a background before scanning starts
    def capture_raw(self):
        """
        captures a spectrum from the usb spectrometer
        returns raw wavelength + counts read from spectrometer
        """
        t0 = time.time()
        spectrum = sn.array_spectrum(self.id, self.__wl)  # actual function
        # spectrum = np.random.rand(2048,2)
        t1 = time.time()

        # spectrum.shape
        # spectrum[:, 1] /= self.integrationtime / 1000  # convert to counts per second
        wl, cts = (
            spectrum[:, 0].round(2),
            spectrum[:, 1],
        )  # wavelength bins are reported as way more precise than they actually are for our slit width
        tot_time = t1 - t0
        return wl, cts, tot_time


"""
code to run:

from XEOL_driver_v0 import Spectrometer
s = Spectrometer()
s.dwelltime = 500 #in ms
s.XEOL_start()

test = open_h5('/Volumes/GoogleDrive/My Drive/Inorganic_PSK/s2_analysis/scan100_XEOL.h5')
test
"""
