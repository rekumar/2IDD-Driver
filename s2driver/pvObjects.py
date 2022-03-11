"""
Created on Wed Oct 27 10:28:14 2021

@author: graceluo + fsm

Create and get PVobjects for 2IDD 

"""

import epics, sys
import numpy as np
from misc import getCurrentTime


class pvObject(object):
    def __init__(self, pv_str, pv_key):
        self.pv = epics.PV(pv_str)
        self.pvname = pv_key
        self.putvalue = self.pv.value
        self.put_complete = 0
        self.motor_ready = 1

    def onPutComplete(self, pvname=None, **kws):
        sys.stdout.write(
            "%s: Finish updating PV %s with value of %s\n"
            % (getCurrentTime(), self.pvname, str(self.putvalue))
        )
        self.put_complete = 1

    def put_callback(self, v=None):
        self.put_complete = 0
        if v is not None:
            self.putvalue = v
            self.pv.put(self.putvalue, callback=self.onPutComplete)

    def motorReady(self, rqspv, tolerance=4e-2):
        rqsvalue = np.round(rqspv.value, 2)
        if abs((np.round(self.pv.value, 2) - rqsvalue)) < tolerance:
            self.motor_ready = 1
        else:
            rqspv.put(rqsvalue)
            self.motor_ready = 0


def definePVs():
    pvs = {
        "x_center_Act": "2idd:m40.RBV",
        "x_center_Rqs": "2idd:m40.VAL",
        "y_center_Act": "2idd:m39.RBV",
        "y_center_Rqs": "2idd:m39.VAL",
        "z_value_Act": "2idd:m36.RBV",
        "z_value_Rqs": "2idd:m36.VAL",
        "x_width_fly": "2idd:FscanH.P1WD",
        "y_width_fly": "2idd:Fscan1.P1WD",
        "x_step_fly": "2idd:FscanH.P1SI",
        "y_step_fly": "2idd:Fscan1.P1SI",
        "dwell_fly": "2idd:Flyscans:Setup:DwellTime.VAL",
        "x_center_fly": "2idd:FscanH.P1CP",
        "y_center_fly": "2idd:Fscan1.P1CP",
        "x_center_mode_fly": "2idd:FscanH.P1AR",
        "y_center_mode_fly": "2idd:Fscan1.P1AR",
        "run_fly": "2idd:Fscan1.EXSC",
        "wait_fly": "2idd:FscanH.WAIT",
        "cur_lines_fly": "2idd:Fscan1.CPT",
        "tot_lines_fly": "2idd:Fscan1.NPTS",
        "abort_fly": "2idd:FAbortScans.PROC",
        "x_width_step": "2idd:scan1.P1WD",
        "y_width_step": "2idd:scan2.P1WD",
        "x_step_step": "2idd:scan1.P1SI",
        "y_step_step": "2idd:scan2.P1SI",
        "dwell_step": "2iddXMAP:PresetReal",
        "x_center_step": "2idd:scan1.P1CP",
        "y_center_step": "2idd:scan2.P1CP",
        "x_center_mode_step": "2idd:scan1.P1AR",
        "y_center_mode_step": "2idd:scan2.P1AR",
        "cur_lines_step": "2idd:scan2.CPT",
        "tot_lines_step": "2idd:scan2.NPTS",
        "run_step": "2idd:scan2.EXSC",
        "wait_step": "2idd:scan1.WAIT",
        "abort_step": "2idd:AbortScans.PROC",
        "msg1d": "2idd:Fscan1.SMSG",
        "open_shutter": "2idd:s1:openShutter.PROC",
        "close_shutter": "2idd:s1:closeShutter.PROC",
        "fname_saveData": "2iddXMAP:netCDF1:FileName",
        "filesys": "2idd:saveData_fileSystem",
        "subdir": "2idd:saveData_subDir",
        "nextsc": "2idd:saveData_scanNumber",
        "basename": "2idd:saveData_baseName",
        "det_time": "2idd:3820:ElapsedReal",
    }
    return pvs


def getPVobj():
    pvObjs = {}
    pvs = definePVs()
    for k, v in pvs.items():
        pv_obj = pvObject(v, k)
        pvObjs.update({k: pv_obj})
    return pvObjs
