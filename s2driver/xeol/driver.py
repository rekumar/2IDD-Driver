from spectrometer import Stellarnet
import numpy as np
import time
import epics
from threading import Thread
from tqdm import tqdm
from s2driver.analysis.helpers import save_dict_to_hdf5

XRF_DETECTOR_TRIGGER = (
    4  # index of scan trigger that is used to trigger the XRF detector
)


class XEOLDriver:
    def __init__(self):
        self.spectrometer = Stellarnet()
        self.DWELLTIME_RATIO = 0.9  # fraction of XRF collection dwelltime to use to acquire spectra. Should be <1 to avoid missing the transition from point to point while XRF scan is ongoing

    ### scanning
    def __xrf_detector_is_acquiring(self) -> bool:
        """Check to see if the XRF detector is currently acquiring data

        Returns:
            bool: True = xrf detector is triggered, False = xrf detector is not acquiring data
        """
        det_trig = epics.caget(f"2idd:scan1.T{XRF_DETECTOR_TRIGGER}PV")
        return det_trig == 0

    def prime_for_stepscan(self, output_filepath: str) -> Thread:
        stepscan_dwelltime = epics.caget(
            "2iddXMAP:PresetReal"
        )  # step scan takes dwelltime in seconds
        num_x_points = epics.caget("2idd:scan1.NPTS")
        num_y_points = epics.caget("2idd:scan2.NPTS")
        self.spectrometer.dwelltime = (
            stepscan_dwelltime * 1000 * self.DWELLTIME_RATIO
        )  # spectrometer takes dwelltime in ms
        capture_thread = Thread(
            target=self._capture_alongside_stepscan, args=(num_x_points, num_y_points)
        )
        capture_thread.start()
        return capture_thread

    def _capture_alongside_stepscan(self, numx: int, numy: int, output_filepath: str):
        """
        captures a spectrum from the usb spectrometer alongside the step scan
        saves raw wavelength + counts read from spectrometer to h5 file
        """
        bg_wl, bg_cts, bg_tot_time = self.capture_raw()
        numwl = len(bg_wl)

        tqdm.write("XEOL capture thread started, waiting for stepscan to begin")
        while epics.caget("2idd:scan2.EXSC") == 0:
            time.sleep(5e-3)
            # print('waiting for trigger...')

        if epics.caget("2idd:scan2.EXSC") == 1:
            tqdm.write("XEOL collection started!")

            x_point = 0
            y_point = 0

            data = np.zeros([numx, numy, numwl])
            time_data = np.zeros([numx, numy])

            # demo
            for y_point in range(numy):
                # scanning a row
                for x_point in range(numx):
                    while (
                        x_point < numx
                    ):  # this ensures that the data is constructed per pixel/per line
                        wl, cts, tot_time = self.capture_raw()
                        time_data[x_point, y_point] = tot_time
                        data[x_point, y_point] = cts

                        while self.__xrf_detector_is_acquiring():
                            time.sleep(
                                1e-6
                            )  # wait for xrf detector to stop acquiring data, move on to next point

            data_dict = {
                "wavelength": wl,
                "dwelltime": time_data,
                "spectra": data,
                "background": bg_cts,
            }

            save_dict_to_hdf5(data_dict, output_filepath)
            tqdm.write("XEOL Scan Saved to: " + output_filepath)
