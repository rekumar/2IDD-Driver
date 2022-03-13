from spectrometer import Stellarnet
import h5py
import numpy as np
import time
import epics
from threading import Thread
from queue import Queue
from tqdm import tqdm

XRF_DETECTOR_TRIGGER = (
    4  # index of scan trigger that is used to trigger the XRF detector
)


class XEOLDriver:
    def __init__(self):
        self.spectrometer = Stellarnet()
        self.DWELLTIME_RATIO = 0.9  # fraction of XRF collection dwelltime to use to acquire spectra. Should be <1 to avoid missing the transition from point to point while XRF scan is ongoing

    def __det_trig_check(self):
        det_trig = epics.caget(f"2idd:scan1.T{XRF_DETECTOR_TRIGGER}PV")
        return det_trig

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
        returns raw wavelength + counts read from spectrometer
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
            while y_point < numy:
                # scanning a row
                x_point = 0

                while (
                    x_point < numx
                ):  # this ensures that the data is constructed per pixel/per line

                    #         wl, cts, time = capture_raw() # no need to save the wl every time, it will be saved once and saved in differnt area
                    #         data[x_point, y_point, :] = cts # acquires a spectra, with settings defined elsewhere, will also output the measured time to run
                    #         time_data[x_point, y_point] = time #insert actual measured times here

                    # time_data[x_point, y_point] = np.round(np.random.rand(1)[0]*100,0) # random numbers instead of measured spec times
                    wl, cts, tot_time = self.capture_raw()

                    #                 time_data[x_point, y_point] = np.round(np.random.rand(1)[0]*100,0) # random numbers instead of measured spec times
                    time_data[x_point, y_point] = tot_time
                    data[x_point, y_point] = cts

                    det_trigger_check = 0
                    while det_trigger_check == 0:
                        det_trigger_check = self.__det_trig_check()

                    x_point += (
                        1  # move to next column, wait for next step to have started
                    )
                y_point += 1  # move to next row, also wait until next row is started

            data_dict = {
                "wavelength": wl,
                "dwelltime": time_data,
                "spectra": data,
                "background": bg_cts,
            }

            # scan_number = epics.caget("2idd:saveData_scanNumber")
            # scan_name = f"scan{scan_number-1}_XEOL.h5"
            # folderpath = "/mnt/micdata1/2idd/2021-3/Fenning/XEOL/"

            # filepath = str(folderpath + scan_name)
            self.save_dict_to_hdf5(data_dict, output_filepath)
            tqdm.write("XEOL Loop Completed!")
            tqdm.write("XEOL Scan Saved to: " + output_filepath)
