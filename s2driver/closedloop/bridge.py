import os
import time
import json

from websocket import Client
from analysis.loading import load_h5, load_xeol


class APSClient(Client):
    def __init__(self):
        self.scan_in_progress = False
        super().__init__()

    def _process_message(self, message: str):
        options = {
            "scan_complete": self._mark_scan_complete,
            "savedir": self._receive_savedir,
            # "get_experiment_directory": self.share_experiment_directory,
        }

        d = json.loads(message)
        func = options[d.pop("type")]
        func(d)

    def _mark_scan_complete(self, d):
        self.most_recent_completed_scan = d["scan_number"]
        self.scan_in_progress = False

    ### Methods that communicate with APSServer
    # receiving save directory to facilitate file loading
    def get_savedir(self):
        self.send(json.dumps({"type": "get_savepath"}))

    def _receive_savedir(self, d):
        self.xrfdir = os.path.join(d["rootdir"], d["subdir"])
        self.xeoldir = os.path.join(d["rootdir"], "XEOL")
        self.basename = d["basename"]

    def _wait_for_scan_complete(self):
        self.scan_in_progress = True
        while self.scan_in_progress:
            time.sleep(1)

    # scan methods
    def scan1d_x(self, startpos, endpos, numpts, dwelltime, block=True):
        self.send(
            json.dumps(
                {
                    "type": "scan1d_x",
                    "startpos": startpos,
                    "endpos": endpos,
                    "numpts": numpts,
                    "dwelltime": dwelltime,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def scan1d_y(self, startpos, endpos, numpts, dwelltime, block=True):
        self.send(
            json.dumps(
                {
                    "type": "scan1d_y",
                    "startpos": startpos,
                    "endpos": endpos,
                    "numpts": numpts,
                    "dwelltime": dwelltime,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def scan2d(self, xmin, xmax, numx, ymin, ymax, numy, dwelltime, block=True):
        self.send(
            json.dumps(
                {
                    "type": "scan2d",
                    "xmin": xmin,
                    "xmax": xmax,
                    "numx": numx,
                    "ymin": ymin,
                    "ymax": ymax,
                    "numy": numy,
                    "dwelltime": dwelltime,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def scan2d_xeol(self, xmin, xmax, numx, ymin, ymax, numy, dwelltime, block=True):
        self.send(
            json.dumps(
                {
                    "type": "scan2d_xeol",
                    "xmin": xmin,
                    "xmax": xmax,
                    "numx": numx,
                    "ymin": ymin,
                    "ymax": ymax,
                    "numy": numy,
                    "dwelltime": dwelltime,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def flyscan2d(self, xmin, xmax, numx, ymin, ymax, numy, dwelltime, block=True):
        self.send(
            json.dumps(
                {
                    "type": "flyscan2d",
                    "xmin": xmin,
                    "xmax": xmax,
                    "numx": numx,
                    "ymin": ymin,
                    "ymax": ymax,
                    "numy": numy,
                    "dwelltime": dwelltime,
                    "wait_for_h5": True,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def timeseries(self, numpts, dwelltime, block=True):
        self.send(
            json.dumps(
                {
                    "type": "timeseries",
                    "numpts": numpts,
                    "dwelltime": dwelltime,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    ### Methods to process data
    def load_scan(
        self,
        scan_number=None,
        clip_flyscan=False,
        xbic_on_dsic=False,
        quant_scaler="us_ic",
    ):
        if scan_number is None:
            scan_number = self.most_recent_completed_scan
        scanfid = os.path.join(self.xrfdir, f"{self.basename}_{scan_number:04d}.h5")
        return load_h5(
            fpath=scanfid,
            clip_flyscan=clip_flyscan,
            xbic_on_dsic=xbic_on_dsic,
            quant_scaler=quant_scaler,
        )

    def load_XEOL(self, scan_number=None):
        if scan_number is None:
            scan_number = self.most_recent_completed_scan
        scanfid = os.path.join(self.xeoldir, f"{self.basename}_{scan_number:04d}.h5")
        return load_xeol(fpath=scanfid)
