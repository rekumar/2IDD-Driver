from turtle import back
from s2driver.xeol.spectrometer import Stellarnet
import numpy as np
import time
import epics
from threading import Thread
from tqdm import tqdm
from s2driver.analysis.helpers import save_dict_to_hdf5
import epics.devices

sc1 = epics.devices.Scan("2idd:scan1")
sc2 = epics.devices.Scan("2idd:scan2")

XRF_DETECTOR_TRIGGER = (
    4  # index of scan trigger that is used to trigger the XRF detector
)

XEOL_IMPLEMENTATED_SCANTYPES = ["scan1d", "scan2d", "timeseries"]
class XEOLController:
    def __init__(self):
        try:
            self.spectrometer = Stellarnet()
            self.IS_PRESENT = True
        except:
            self.IS_PRESENT = False
        self.DWELLTIME_RATIO = 0.9  # fraction of XRF collection dwelltime to use to acquire spectra. Should be <1 to avoid missing the transition from point to point while XRF scan is ongoing

        self.XEOL_IMPLEMENTED_SCANTYPES = {
            "scan1d": self._capture_alongside_scan1d,
            "timeseries": self._capture_alongside_scan1d,
            "scan2d": self._capture_alongside_scan2d,
        }
    ### scanning
    def __xrf_detector_is_acquiring(self) -> bool:
        """Check to see if the XRF detector is currently acquiring data

        Returns:
            bool: True = xrf detector is triggered, False = xrf detector is not acquiring data
        """
        det_trig = epics.caget(f"2idd:scan1.T{XRF_DETECTOR_TRIGGER}CD")
        return det_trig == 0

    def prime_for_scan(self, scantype:str, output_filepath: str) -> Thread:
        if scantype not in self.XEOL_IMPLEMENTED_SCANTYPES:
            raise ValueError(f"Invalid scan type - XEOL is only implemented for {XEOL_IMPLEMENTATED_SCANTYPES.keys()}")
        capture_function = self.XEOL_IMPLEMENTED_SCANTYPES[scantype] #get the capture thread appropriate to this scan type

        stepscan_dwelltime = epics.caget(
            "2iddXMAP:PresetReal"
        )*1e3  # step scan takes dwelltime in seconds, we want ms
        self.spectrometer.dwelltime = (
            stepscan_dwelltime * self.DWELLTIME_RATIO
        )  # spectrometer takes dwelltime in ms

        self.spectrometer.numscans = 5  # average 5 scans together for background
        bg_wl, bg_cts, bg_tot_time = self.spectrometer.capture_raw()
        self.spectrometer.numscans = 1  # back to 1 scan per capture
        
        capture_thread = Thread(
            target=capture_function,
            args=(output_filepath, bg_cts),
        )
        capture_thread.start()
        return capture_thread

    def _capture_alongside_scan2d(self, output_filepath: str, background_counts: np.ndarray):
        """
        captures a spectrum from the usb spectrometer alongside the step scan
        saves raw wavelength + counts read from spectrometer to h5 file
        """
        numx = sc1.NPTS
        numy = sc2.NPTS
        numwl = len(background_counts)
        tqdm.write("XEOL capture thread started, waiting for 2d stepscan to begin")
        while sc2.BUSY == 0:
            time.sleep(5e-3)
            # print('waiting for trigger...')
        tqdm.write("XEOL collection started!")

        data = np.zeros([numy, numx, numwl])
        time_data = np.zeros([numy, numx])
        x_coords = np.zeros([numy, numx])
        y_coords = np.zeros([numy, numx])

        for y_point in range(numy):
            for x_point in range(numx):
                wl, cts, tot_time = self.spectrometer.capture_raw()
                time_data[y_point, x_point] = tot_time
                data[y_point, x_point] = cts
                x_coords[y_point, x_point] = epics.caget(sc1.P1PV)
                y_coords[y_point, x_point] = epics.caget(sc2.P1PV)

                while self.__xrf_detector_is_acquiring():
                    time.sleep(
                        1e-6
                    )  # wait for xrf detector to stop acquiring data, move on to next point

        data_dict = {
            "wavelength": wl,
            "dwelltime": time_data,
            "spectra": data,
            "background": background_counts,
            "x": x_coords,
            "y": y_coords,
        }

        save_dict_to_hdf5(data_dict, output_filepath)
        tqdm.write("XEOL Scan Saved to: " + output_filepath)

    def _capture_alongside_scan1d(self, output_filepath: str, background_counts: np.ndarray):
        """
        captures a spectrum from the usb spectrometer alongside the step scan
        saves raw wavelength + counts read from spectrometer to h5 file
        """
        numpts = sc1.NPTS
        numwl = len(background_counts)
        tqdm.write("XEOL capture thread started, waiting for stepscan to begin")
        while sc1.BUSY == 0:
            time.sleep(5e-3)
            # print('waiting for trigger...')

        tqdm.write("XEOL collection started!")

        data = np.zeros([numpts, numwl])
        time_data = np.zeros(numpts)
        coords = np.zeros(numpts)

        for point in range(numpts):
            wl, cts, tot_time = self.spectrometer.capture_raw()
            time_data[point] = tot_time
            data[point] = cts
            coords[point] = epics.caget(sc1.P1PV)

            while self.__xrf_detector_is_acquiring():
                time.sleep(
                    1e-6
                )  # wait for xrf detector to stop acquiring data, move on to next point

        data_dict = {
            "wavelength": wl,
            "dwelltime": time_data,
            "spectra": data,
            "background": background_counts,
            "x": coords,
        }

        save_dict_to_hdf5(data_dict, output_filepath)
        tqdm.write("XEOL Scan Saved to: " + output_filepath)

    
