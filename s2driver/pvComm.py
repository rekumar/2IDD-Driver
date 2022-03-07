"""
Created on Wed Jul 28 14:32:26 2021

@author: graceluo

Function to setup scan, interact with PV mostly
"""

from pvObjects import getPVobj
from misc import getCurrentTime
import os, sys
import numpy as np


class pvComm():
    def __init__(self, userdir=None, log='log.txt'):
        self.pvs = getPVobj()
        if userdir is None:
            self.userdir = self.getDir()
        else:
            self.userdir = userdir
        self.logfilepath = os.path.join(self.userdir, log)
        self.logfid = open(self.logfilepath, 'a')

    def logger(self, msg):
        sys.stdout.write(msg)
        sys.stdout.flush()
        if self.logfid.closed:
            self.logfid = open(self.logfilepath, 'a')
        self.logfid.write(msg)
        self.logfid.flush()

    def getDir(self):
        fs = self.pvs['filesys'].pv.value
        fs = fs.replace('//micdata/data1', '/mnt/micdata1')
        return os.path.join(fs, self.pvs['subdir'].pv.value.replace('mda', ''))

    def scanPause(self, scanType):
        wt_str = 'wait_fly' if scanType=='Fly-XRF' else 'wait_step'
        self.pvs[wt_str].put_callback(1)

    def scanResume(self, scanType):
        wt_str = 'wait_fly' if scanType=='Fly-XRF' else 'wait_step'
        self.pvs[wt_str].put_callback(0)

    def scanAbort(self, scanType):
        abrt_str = 'abort_fly' if scanType=='Fly-XRF' else 'abort_step'
        self.pvs[abrt_str].put_callback(1)

    def closeShutter(self):
        self.logger('%s: Shutter Close\n' % (getCurrentTime()))
        self.pvs['close_shutter'].pv.put(1)

    def openShutter(self):
        self.logger('%s: Shutter Open\n' % (getCurrentTime()))
        self.pvs['open_shutter'].pv.put(1)
        
    def getCurrentLine(self, scanType):
        cur_str = 'cur_lines_fly' if scanType == 'Fly-XRF' else 'cur_lines_step'
        return self.pvs[cur_str].pv.value
    
    def getTotalLines(self, scanType):
        tot_str = 'tot_lines_fly' if scanType == 'Fly-XRF' else 'tot_lines_step'
        return self.pvs[tot_str].pv.value

    def setXYcenter(self, scanType, x_scan):
        self.logger('%s: Update the current position as the center of'
                    'the scan.\n' % (getCurrentTime()))
        if scanType == 'Fly-XRF':
            self.pvs['x_center_mode_fly'].pv.put(0)  # absolute center
            self.pvs['y_center_mode_fly'].pv.put(1)  # relative center
            self.pvs['x_center_fly'].pv.put(x_scan)
            self.pvs['y_center_fly'].pv.put(0)
            
        elif scanType == 'Step-XRF':
            self.pvs['x_center_mode_step'].pv.put(1)  # relative center
            self.pvs['y_center_mode_step'].pv.put(1)  # relative center
            self.pvs['x_center_step'].pv.put(0)
            self.pvs['y_center_step'].pv.put(0)

    def assignPosValToPVs(self, pvstr, pvval):
        for s_, v_ in zip(pvstr, pvval):
            self.pvs[s_].pv.put(v_)
            self.logger('%s: Change %s to %.3f\n' % (getCurrentTime(), s_, v_))

    def assignSinglePV(self, pvstr, pvval):
        self.pvs[pvstr].pv.put(pvval)
        self.logger('%s: Change %s to %.3f\n' %
                    (getCurrentTime(), pvstr, pvval))

    def writeScanInit(self, mode, smpinfo, scandic):
        next_sc = self.nextScanName()
        self.logger('%s Initiating scan %s %s\n' % ('#'*20, next_sc, '#'*20))
        self.logger('Sample info: %s\n' % smpinfo)
        self.logger('%s: Setting up scan using %s mode.\n' %
                    (getCurrentTime(), mode))
        self.logger('%s: %s' % (getCurrentTime(), scandic))
        self.logger('\n\n')

    def motorReady(self, l, mt):
        self.logger('%s: Checking whether motors are ready.\n' %
                    (getCurrentTime()))
        actpv = self.pvs['%s_Act' % l].pv
        rqspv = self.pvs['%s_Rqs' % l].pv
        self.pvs['%s_Act' % l].motorReady(rqspv, mt)

        if self.pvs['%s_Act' % l].motor_ready:
            self.logger('%s: %s motor is in position with value'
                        '%.2f\n' % (getCurrentTime(), l, actpv.value))
            return 1
        else:
            self.logger('%s: %s motor not in position, current: %.2f,'
                        ' request: %.2f\n' % (getCurrentTime(), l, actpv.value, rqspv.value))
            return 0

    def nextScanName(self):
        return '%s%s.mda' % (self.pvs['basename'].pv.value,
                             str(self.pvs['nextsc'].pv.value).zfill(4))

    def getXYZcenter(self):
        return [np.round(self.pvs[i].pv.value, 2) for i in ['x_center_Act',
                'y_center_Act', 'z_value_Act']]
