import os
import time
import json

from s2driver.closedloop.websocket import Client, Server
from s2driver.analysis.loading import load_h5, load_xeol
from s2driver.driving import *  # all driving commands, used by S2Server
from s2driver.logging import initialize_logbook

logger = initialize_logbook()


class S2Client(Client):
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
    def movr_x(self, pos, block=True):
        self.send(
            json.dumps(
                {
                    "type": "movr_x",
                    "pos": pos,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def movr_y(self, pos, block=True):
        self.send(
            json.dumps(
                {
                    "type": "movr_y",
                    "pos": pos,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def scan1d_x(self, startpos, endpos, numpts, dwelltime, absolute=False, block=True):
        self.send(
            json.dumps(
                {
                    "type": "scan1d_x",
                    "startpos": startpos,
                    "endpos": endpos,
                    "numpts": numpts,
                    "dwelltime": dwelltime,
                    "absolute": absolute,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def scan1d_x_xeol(
        self, startpos, endpos, numpts, dwelltime, absolute=False, block=True
    ):
        self.send(
            json.dumps(
                {
                    "type": "scan1d_x_xeol",
                    "startpos": startpos,
                    "endpos": endpos,
                    "numpts": numpts,
                    "dwelltime": dwelltime,
                    "absolute": absolute,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def scan1d_y(self, startpos, endpos, numpts, dwelltime, absolute=False, block=True):
        self.send(
            json.dumps(
                {
                    "type": "scan1d_y",
                    "startpos": startpos,
                    "endpos": endpos,
                    "numpts": numpts,
                    "dwelltime": dwelltime,
                    "absolute": absolute,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def scan1d_y_xeol(
        self, startpos, endpos, numpts, dwelltime, absolute=False, block=True
    ):
        self.send(
            json.dumps(
                {
                    "type": "scan1d_y_xeol",
                    "startpos": startpos,
                    "endpos": endpos,
                    "numpts": numpts,
                    "dwelltime": dwelltime,
                    "absolute": absolute,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def scan2d(
        self, xmin, xmax, numx, ymin, ymax, numy, dwelltime, absolute=False, block=True
    ):
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
                    "absolute": absolute,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def scan2d_xeol(
        self, xmin, xmax, numx, ymin, ymax, numy, dwelltime, absolute=False, block=True
    ):
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
                    "absolute": absolute,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def flyscan2d(
        self, xmin, xmax, numx, ymin, ymax, numy, dwelltime, absolute=False, block=True
    ):
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
                    "absolute": absolute,
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

    def timeseries_xeol(self, numpts, dwelltime, block=True):
        self.send(
            json.dumps(
                {
                    "type": "timeseries_xeol",
                    "numpts": numpts,
                    "dwelltime": dwelltime,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    def set_transmittance(self, transmittance: float, block=True):
        self.send(
            json.dumps(
                {
                    "type": "set_transmittance",
                    "transmittance": transmittance,
                }
            )
        )
        if block:
            self._wait_for_scan_complete()

    ### Methods to process data
    def load_h5(
        self,
        scan_number=None,
        clip_flyscan=True,
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


class S2Server(Server):
    def _process_message(self, message: str):
        options = {
            "request_savedir": self._send_savedir,
            "movr_x": self._movr_x,
            "movr_y": self._movr_y,
            "scan1d_x": self._scan1d_x,
            "scan1d_x_xeol": self._scan1d_x_xeol,
            "scan1d_y": self._scan1d_y,
            "scan1d_y_xeol": self._scan1d_y_xeol,
            "scan2d": self._scan2d,
            "scan2d_xeol": self._scan2d_xeol,
            "flyscan2d": self._flyscan2d,
            "timeseries": self._timeseries,
            "timeseries_xeol": self._timeseries_xeol,
            "set_transmittance": self._set_transmittance,
            # "get_experiment_directory": self.share_experiment_directory,
        }

        d = json.loads(message)
        func = options[d.pop("type")]
        logger.info(f"APSServer received instructions of type '{func}'")
        func(d)

    def _send_savedir(self, d):
        rootdir = PVS["filesys"].val
        subdir = PVS["subdir"].val
        basename = PVS["basename"].val
        self.send_message(
            json.dumps({"rootdir": rootdir, "subdir": subdir, "basename": basename})
        )

    def _mark_scan_complete(self):
        msg = {"type": "scan_complete", "scan_number": PVS["next_scan"].value - 1}
        self.send(json.dumps(msg))

    def _movr_x(self, d):
        movr(samx, d["pos"])
        self._mark_scan_complete()

    def _movr_y(self, d):
        movr(samy, d["pos"])
        self._mark_scan_complete()

    def _scan1d_x(self, d):
        scan1d(
            motor=samx,
            startpos=d["startpos"],
            endpos=d["endpos"],
            numpts=d["numpts"],
            dwelltime=d["dwelltime"],
            absolute=d["absolute"],
        )
        self._mark_scan_complete()

    def _scan1d_x_xeol(self, d):
        scan1d_xeol(
            motor=samx,
            startpos=d["startpos"],
            endpos=d["endpos"],
            numpts=d["numpts"],
            dwelltime=d["dwelltime"],
            absolute=d["absolute"],
        )
        self._mark_scan_complete()

    def _scan1d_y(self, d):
        scan1d(
            motor=samy,
            startpos=d["startpos"],
            endpos=d["endpos"],
            numpts=d["numpts"],
            dwelltime=d["dwelltime"],
            absolute=d["absolute"],
        )
        self._mark_scan_complete()

    def _scan1d_y_xeol(self, d):
        scan1d_xeol(
            motor=samy,
            startpos=d["startpos"],
            endpos=d["endpos"],
            numpts=d["numpts"],
            dwelltime=d["dwelltime"],
            absolute=d["absolute"],
        )
        self._mark_scan_complete()

    def _scan2d(self, d):
        scan2d(
            motor1=samx,
            startpos1=d["startpos1"],
            endpos1=d["endpos1"],
            numpts1=d["numpts1"],
            motor2=samy,
            startpos2=d["startpos2"],
            endpos2=d["endpos2"],
            numpts2=d["numpts2"],
            dwelltime=d["dwelltime"],
            absolute=d["absolute"],
        )
        self._mark_scan_complete()

    def _scan2d_xeol(self, d):
        scan2d_xeol(
            motor1=samx,
            startpos1=d["startpos1"],
            endpos1=d["endpos1"],
            numpts1=d["numpts1"],
            motor2=samy,
            startpos2=d["startpos2"],
            endpos2=d["endpos2"],
            numpts2=d["numpts2"],
            dwelltime=d["dwelltime"],
            absolute=d["absolute"],
        )
        self._mark_scan_complete()

    def _flyscan2d(self, d):
        flyscan2d(
            startpos1=d["startpos1"],
            endpos1=d["endpos1"],
            numpts1=d["numpts1"],
            startpos2=d["startpos2"],
            endpos2=d["endpos2"],
            numpts2=d["numpts2"],
            dwelltime=d["dwelltime"],
            absolute=d["absolute"],
        )
        self._mark_scan_complete()

    def _timeseries(self, d):
        timeseries(numpts=d["numpts"], dwelltime=d["dwelltime"])
        self._mark_scan_complete()

    def _timeseries_xeol(self, d):
        timeseries_xeol(numpts=d["numpts"], dwelltime=d["dwelltime"])
        self._mark_scan_complete()

    def _set_transmittance(self, d):
        set_transmittance(d["transmittance"])
        self._mark_scan_complete()
