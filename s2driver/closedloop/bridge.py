from collections import defaultdict
import numpy as np
import os
import time
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, NamedTuple, Union, Iterable, Set

from ax import *
from ax.core.base_trial import BaseTrial, TrialStatus
from websocket import Client
from analysis.loading import load_h5, load_xeol


class NumpyFloatValuesEncoder(json.JSONEncoder):
    """Converts np.float32 to float to allow dumping to json file"""

    def default(self, obj):
        if isinstance(obj, np.float32):
            return float(obj)
        return json.JSONEncoder.default(self, obj)


class APSClient(Client):
    def __init__(self):
        self.scan_in_progress = False
        return

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

    # scan methods
    def scan(self, xmin, xmax, numx, ymin, ymax, numy, dwelltime, block=True):
        self.send(
            json.dumps(
                {
                    "type": "scan",
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
        self.scan_in_progress = True
        while self.scan_in_progress:
            time.sleep(1)

    def flyscan(self, xmin, xmax, numx, ymin, ymax, numy, dwelltime):
        self.send(
            json.dumps(
                {
                    "type": "scan",
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
        self.scan_in_progress = True
        while self.scan_in_progress:
            time.sleep(1)

    def timeseries(self, numpts, dwelltime):
        self.send(
            json.dumps(
                {
                    "type": "timeseries",
                    "numpts": numpts,
                    "dwelltime": dwelltime,
                }
            )
        )
        self.scan_in_progress = True
        while self.scan_in_progress:
            time.sleep(1)

    ### Methods to process data
    def load_scan(
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
        scanfid = os.path.join(self.xeoldir, f"{self.basename}_{scan_number:d}.h5")
        return load_xeol(fpath=scanfid)
