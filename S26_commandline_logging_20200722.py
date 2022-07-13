# Enables command line scripting for HXN microscope operation
# start this with /APSshare/anaconda/x86_64/bin/ipython -i S26_commandline.py

import sys
import epics
import epics.devices
import time
import datetime
import numpy as np
import os 
import math
import socket
import signal
from matplotlib import pyplot
from IPython import get_ipython
ipython=get_ipython()

sys.path.append("/home/sector26/pythonscripts/Tao/flyscan")

from flyxy_final import *


### START Logging functions (REK 20200722) ###
import json
import inspect

scanrecord = '26idbSOFT'
class Logger():
    """
    Object to handle logging of motor positions, filter statuses, and XRF ROI assignments per scan. 

    REK 20191206
    """
    def __init__(self, sample = '', note = ''):
        #self.rootDir = os.path.join(
        #   epics.caget(scanrecord+':saveData_fileSystem',as_string=True),  #file directory
        #   epics.caget(scanrecord+':saveData_subDir',as_string=True)       #subdir for our data
        #   )[:-4]
        self.rootDir =  epics.caget(scanrecord+':saveData_fileSystem',as_string=True) + epics.caget(scanrecord+':saveData_subDir',as_string=True)
        self.rootDir = self.rootDir[:-4]

        self.logDir = os.path.join(self.rootDir, 'Logging')
        if not os.path.isdir(self.logDir):
            os.mkdir(self.logDir)

        self.logFilepath = os.path.join(self.logDir, 'verboselog.json')
        if not os.path.exists(self.logFilepath):
            with open(self.logFilepath, 'w') as f:
                json.dump({'9999999': 0}, f)    #intialize as empty dictionary

        self.sample = sample    #current sample being measured
        self.note = note

        self.motorDict = {  #array of motor labels + epics addresses
                    "fomx": '26idcnpi:m10.VAL',
                    "fomy": '26idcnpi:m11.VAL',
                    "fomz": '26idcnpi:m12.VAL',
                    # "samx": '26idcnpi:m16.VAL',
                    "samy": '26idcnpi:m17.VAL',
                    # "samz": '26idcnpi:m18.VAL',
                    "samth": 'atto2:PIC867:1:m1.VAL',
                    "osax": '26idcnpi:m13.VAL',
                    "osay": '26idcnpi:m14.VAL',
                    "osaz": '26idcnpi:m15.VAL',
                    "condx": '26idcnpi:m5.VAL',
                    "attox": 'atto2:m4.VAL',
                    "attoz": 'atto2:m3.VAL',
                    "samchi": 'atto2:m1.VAL',
                    "samphi": 'atto2:m2.VAL',
                    "objx": '26idcnpi:m1.VAL',
                    "xrfx": '26idcDET:m7.VAL',
                    # "piezox": '26idcSOFT:sm1.VAL',
                    # "piezoy": '26idcSOFT:sm2.VAL',
                    "hybridx": '26idcnpi:X_HYBRID_SP.VAL',
                    "hybridy": '26idcnpi:Y_HYBRID_SP.VAL',
                    "twotheta": '26idcSOFT:sm3.VAL',
                    "gamma":    '26idcSOFT:sm4.VAL',
                    "filter1": "26idc:filter:Fi1:Set",  
                    "filter2": "26idc:filter:Fi2:Set",
                    "filter3": "26idc:filter:Fi3:Set",
                    "filter4": "26idc:filter:Fi4:Set",
                    "energy": "26idbDCM:sm8.RBV",   
                }

    def getXRFROI(self):
        """
        loads ROI assignments from MCA1, assumes we are using same ROI assignments for MCA 1-4
        """
        ROI = []
        for roinum in range(32):
            ROI.append({
                'Line': epics.caget('26idcXMAP:mca1.R{0}NM'.format(roinum)),
                'Low': epics.caget('26idcXMAP:mca1.R{0}LO'.format(roinum)),
                'High': epics.caget('26idcXMAP:mca1.R{0}HI'.format(roinum))
                })

        return ROI

    def updateLog(self, scanFunction, scanArgs):
        self.scanNumber = int(epics.caget(scanrecord+':saveData_scanNumber'))

        self.scanEntry = {
            'ROIs': self.getXRFROI(),
            'Sample': self.sample,
            'Note': self.note,
            'Date': str(datetime.datetime.now().date()),
            'Time': str(datetime.datetime.now().time()),
            'ScanFunction': scanFunction,
            'ScanArgs': scanArgs
        }
        
        for label, key in self.motorDict.items():
            self.scanEntry[label] = epics.caget(key)
        
        ### Add entry to log file
        with open(self.logFilepath, 'r') as f:
            fullLogbook = json.load(f)
        fullLogbook[int(self.scanNumber)] = self.scanEntry
        with open(self.logFilepath, 'w') as f:
            json.dump(fullLogbook, f)
    
    def get(self, scannumber, key):
        scannumber = str(scannumber)
        with open(self.logFilepath, 'r') as fid:
            f = json.load(f)
            if scannumber not in f.keys():
                print('Error: scan {0} not included in logbook.'.format(scannumber))
            elif key not in f[scannumber].keys():
                print('Error: invalid key {0}. Possible keys include:'.format(key))
                for k in f['scannumber'].keys():
                    print(k)
            else:
                print('Scan {0} {1}: {2}'.format(scannumber, key, f[scannumber][key]))

# initalize logging object
logger = Logger()

### END Logging functions (REK 20200722) ###

# Define motors
fomx = epics.Motor('26idcnpi:m10.')
fomy = epics.Motor('26idcnpi:m11.')
fomz = epics.Motor('26idcnpi:m12.')
#samx = epics.Motor('26idcnpi:m16.')
samy = epics.Motor('26idcnpi:m17.')
#samz = epics.Motor('26idcnpi:m18.')
samth = epics.Motor('atto2:PIC867:1:m1.')
osax = epics.Motor('26idcnpi:m13.')
osay = epics.Motor('26idcnpi:m14.')
osaz = epics.Motor('26idcnpi:m15.')
condx = epics.Motor('26idcnpi:m5.')
#attox = epics.Motor('atto2:m3.')
#attoz = epics.Motor('atto2:m4.')
#attoz = epics.Motor('26idcNES:sm27.')
attox = epics.Motor('atto2:m4.')
attoz = epics.Motor('atto2:m3.')
#samchi = epics.Motor('atto2:m1.')
#samphi = epics.Motor('atto2:m2.')
objx = epics.Motor('26idcnpi:m1.')
xrfx = epics.Motor('26idcDET:m7.')
#piezox = epics.Motor('26idcSOFT:sm1.')
#piezoy = epics.Motor('26idcSOFT:sm2.')
#lensx = epics.Motor('4idcThor:m2.')
#lensy = epics.Motor('4idcThor:m3.')
chopy = epics.Motor('26idc:m7.')
chopx = epics.Motor('26idc:m8.')

DCMenergy = epics.Motor("26idbDCM:sm8")

#hybridx = epics.Device('26idcDEV:X_HYBRID_SP.', attrs=('VAL','DESC'))
hybridx = epics.Device('26idcnpi:X_HYBRID_SP.', attrs=('VAL','DESC'))
#hybridx = epics.Device('26idcnpi:m34.', attrs=('VAL','DESC'))
hybridx.add_pv('26idcnpi:m34.RBV', attr='RBV')
#hybridy  = epics.Device('26idcDEV:Y_HYBRID_SP.', attrs=('VAL','DESC'))
hybridy  = epics.Device('26idcnpi:Y_HYBRID_SP.', attrs=('VAL','DESC'))
hybridy.add_pv('26idcnpi:m35.RBV', attr='RBV')
twotheta = epics.Motor('26idcSOFT:sm3.')
#twotheta = epics.Device('26idcDET:base:Theta.', attrs=('VAL','DESC'))
#twotheta.add_pv('26idcDET:base:Theta_d', attr='RBV')
#dcmy = epics.Device('26idb:DAC1_1.', attrs=('VAL','DESC'))
#dcmy.add_pv('26idcDET:base:Theta_d', attr='RBV')
not_epics_motors = [hybridx.NAME, hybridy.NAME, twotheta.NAME]

print("\n")

ipython.magic("%logstop")

if os.path.exists("/home/beams/USER26ID/oplog/oplog.txt"):
    os.rename("/home/beams/USER26ID/oplog/oplog.txt", "/home/beams/USER26ID/oplog/oplog_{0}.txt".format(datetime.datetime.today().strftime("%y%m%d")))

ipython.magic("%logstart -o -t /home/beams/USER26ID/oplog/oplog.txt append")


def sigint_handler(sig, frame):
    if (sc1.BUSY or sc2.BUSY):
        print("\n!!! use the abort button to abort the scans !!!")
    elif epics.caget("26idaWBS:sft01:ph01:ao06.VAL") == 1:
        flyxy_cleanup()
        sys.exit("fly scan interrupted, clean up complete.")
    else:
        sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

print(2)

def load_config():

    global optic_in_x, optic_in_y, optic_in_z, mpx_in_x, mpx_in_y, genie_in_x, genie_in_y, pind_in_x, pind_in_y

    optic_in_x, optic_in_y, optic_in_z, mpx_in_x, mpx_in_y, genie_in_x, genie_in_y, pind_in_x, pind_in_y = np.loadtxt("/home/beams/USER26ID/savedata/pythonscripts/holt/S26_config.txt")
    print("loading saved positions for fzp : {0:.3f} {1:.3f} {2:.3f}".format(optic_in_x, optic_in_y, optic_in_z))
    print("loading saved positions for mpx : {0:.3f} {1:.3f}".format(mpx_in_x, mpx_in_y))
    print("loading saved positions for gen : {0:.3f} {1:.3f}".format(genie_in_x, genie_in_y))
    print("loading saved positions for pnd : {0:.3f} {1:.3f}".format(pind_in_x, pind_in_y))
    
load_config()

def save_config():

    S26_config = [optic_in_x, optic_in_y, optic_in_z, mpx_in_x, mpx_in_y, genie_in_x, genie_in_y, pind_in_x, pind_in_y]
    f_conf = np.savetxt("/home/beams25/USER26ID/savedata/pythonscripts/holt/S26_config.txt", S26_config, fmt="%.3f",\
                        header="optic_in_x, optic_in_y, optic_in_z, mpx_in_x, mpx_in_y, genie_in_x, genie_in_y, pind_in_x, pind_in_y")
    



# Define movement functions
def mov(motor,position):
    if motor in [fomx, fomy, samy]:
        epics.caput('26idcnpi:m34.STOP',1)
        epics.caput('26idcnpi:m35.STOP',1)
        epics.caput('26idcSOFT:userCalc1.SCAN',0)
        epics.caput('26idcSOFT:userCalc3.SCAN',0)
    if motor.NAME in not_epics_motors:
        motor.VAL = position
        time.sleep(1)
        print(motor.DESC+"--->  "+str(motor.RBV))
    else:
        result = motor.move(position, wait=True)
        if result==0:
            time.sleep(0.5)
            print(motor.DESC+" ---> "+str(motor.RBV))
            fp = open(logbook,"a")
            fp.write(motor.DESC+" ---> "+str(motor.RBV)+"\n")
            fp.close()
            epics.caput('26idcSOFT:userCalc1.SCAN',6)
            epics.caput('26idcSOFT:userCalc3.SCAN',6)
        else:
            print("Motion failed")
        
    

def movr(motor,tweakvalue):
    if motor in [fomx, fomy, samy]:
        epics.caput('26idcnpi:m34.STOP',1)
        epics.caput('26idcnpi:m35.STOP',1)
    if ( (motor in [hybridx, hybridy]) and ( (abs(hybridx.RBV-hybridx.VAL)>100) or (abs(hybridy.RBV-hybridy.VAL)>100) ) ):
        print("Please use lock_hybrid() to lock piezos at current position first...")
        return
    if motor.NAME in not_epics_motors:
        motor.VAL = motor.VAL+tweakvalue
        time.sleep(1)
        print(motor.DESC+"--->  "+str(motor.RBV))
    else:
        result = motor.move(tweakvalue, relative=True, wait=True)
        if result==0:
            time.sleep(0.5)
            print(motor.DESC+" ---> "+str(motor.RBV))
            fp = open(logbook,"a")
            fp.write(motor.DESC+" ---> "+str(motor.RBV)+"\n")
            fp.close()
        else:
            print("Motion failed")

def zp_in():
    print('Moving ZP to focal position...\n')
    epics.caput('26idcSOFT:userCalc1.SCAN',0);
    epics.caput('26idcSOFT:userCalc3.SCAN',0);
    epics.caput('26idbSOFT:userCalc3.SCAN',0);
    mov(fomx,optic_in_x)
    mov(fomy,optic_in_y)
    mov(fomz,optic_in_z)
    epics.caput('26idcSOFT:userCalc1.SCAN',5);
    epics.caput('26idcSOFT:userCalc3.SCAN',5);
    epics.caput('26idbSOFT:userCalc3.SCAN',5);

def zp_out():
    #global mpx_in_x, mpx_in_y
    tempx = epics.caget('26idc:sft01:ph02:ao09.VAL')
    tempy = epics.caget('26idc:robot:Y1.VAL')
    temp2th = epics.caget('26idcDET:base:Theta.VAL')
    if ( (abs(mpx_in_x-tempx)<0.1) and (abs(mpx_in_y-tempy)<0.1) and (abs(temp2th)<1.0) ):
        print("Please use genie_in() to move medipix out of beam first...")
        return
    print('Moving ZP out of beam...\n')
    epics.caput('26idcSOFT:userCalc1.SCAN',0);
    epics.caput('26idcSOFT:userCalc3.SCAN',0);
    epics.caput('26idbSOFT:userCalc3.SCAN',0);
    mov(fomx,optic_in_x+3500.0)
    mov(fomy,optic_in_y)
    mov(fomz,-4700.0)
    epics.caput('26idcSOFT:userCalc1.SCAN',5);
    epics.caput('26idcSOFT:userCalc3.SCAN',5);
    epics.caput('26idbSOFT:userCalc3.SCAN',5);


def slowlymove2theta(twotheta_target):

    twotheta0 = epics.caget("26idcDET:base:Theta.VAL")
    twotheta_step = (twotheta_target-twotheta0)/int(abs((twotheta_target-twotheta0)/5.))
    twotheta_targets = np.arange(twotheta0, twotheta_target+twotheta_step*.1, twotheta_step)
    print(twotheta_targets)
    for twotheta_tmp in twotheta_targets:
        print('moving twotheta to {0:.3f}'.format(twotheta_tmp))
        mov(twotheta, twotheta_tmp)
        time.sleep(30)
        while(not epics.caget("26idcDET:m1.DMOV")):
            time.sleep(5)
            print('waiting...')


def piezo_cen(projection = True, test = False):

    tempx_volt = epics.caget("26idcnpi:X_VOLTAGE_MONITOR.VAL")
    tempx_pervolt = epics.caget("26idcnpi:X_MICRONS_PER_VOLT")
    tempx = epics.caget("26idcnpi:X_HYBRID_SP.VAL")
    tempx_cen = tempx+(5-tempx_volt)*tempx_pervolt
    temp_attoz = epics.caget("atto2:m3.VAL")

    tempy_volt = epics.caget("26idcnpi:Y_VOLTAGE_MONITOR.VAL")
    tempy_pervolt = epics.caget("26idcnpi:Y_MICRONS_PER_VOLT")
    tempy = epics.caget("26idcnpi:Y_HYBRID_SP.VAL")
    tempy_cen = tempy+(5-tempy_volt)*tempy_pervolt
    temp_samy = epics.caget("26idcnpi:m17.VAL")

    if projection:
        tempth = epics.caget("atto2:PIC867:1:m1.VAL")
    else:
        tempth = 90
    target_attoz = temp_attoz + (tempx_cen - tempx) / math.sin(math.radians(tempth))
    target_samy = temp_samy + (tempy_cen - tempy)
    print("moving hybridx from {0:.3f} to {1:.3f}".format(tempx, tempx_cen))
    if not test:
        mov(hybridx,tempx_cen)
        time.sleep(1)
        mov(hybridy,tempy_cen)
        time.sleep(1)
    print("moving hybridy from {0:.3f} to {1:.3f}".format(tempy, tempy_cen))
    print("hybridx voltage is now {0:.1f}V (range 0-10V)".format(epics.caget("26idcnpi:X_VOLTAGE_MONITOR.VAL")))
    print("hybridy voltage is now {0:.1f}V (range 0-10V)".format(epics.caget("26idcnpi:Y_VOLTAGE_MONITOR.VAL")))

    print("disabling hybrid lock...")
    if not test:
        epics.caput('26idcnpi:m34.STOP',1)
        time.sleep(1)
        epics.caput('26idcnpi:m35.STOP',1)
        time.sleep(1)

    print("moving attoz from {0:.3f} to {1:.3f}".format(temp_attoz, target_attoz))
    print("moving samy from {0:.3f} to {1:.3f}".format(temp_samy, target_samy))
    if not test:
        mov(attoz, target_attoz)
        time.sleep(1)
        mov(samy, target_samy)
        time.sleep(1)
        lock_hybrid()
    print("enabling hybrid lock...")


def lock_hybrid():
    tempx = hybridx.RBV
    time.sleep(1)
    mov(hybridx,tempx)
    time.sleep(1)
    tempy = hybridy.RBV
    time.sleep(1)
    mov(hybridy,tempy)
    time.sleep(1)

def unlock_hybrid():
    tempx = hybridx.RBV
    tempy = hybridy.RBV
    print("before unlock: x = {0} and y = {1}".format(tempx, tempy))
    epics.caput('26idcnpi:m34.STOP',1)
    epics.caput('26idcnpi:m35.STOP',1)
    if ( (abs(fomx.RBV-optic_in_x)<100) and (abs(fomy.RBV-optic_in_y)<100) ):  
        mov(fomx,optic_in_x);
        mov(fomy,optic_in_y);
    time.sleep(1)
    tempx = hybridx.RBV
    tempy = hybridy.RBV
    print("after unlock: x = {0} and y = {1}".format(tempx, tempy))


def set_zp_in():
    global optic_in_x, optic_in_y, optic_in_z
    print("ZP X focal position set to: "+str(fomx.RBV))
    optic_in_x = fomx.RBV
    print("ZP Y focal position set to: "+str(fomy.RBV))
    optic_in_y = fomy.RBV
    print("ZP Z focal position set to: "+str(fomz.RBV))
    optic_in_z = fomz.RBV
    save_config()
    

def set_medipix_in():
    global mpx_in_x, mpx_in_y
    tempx = epics.caget('26idc:sft01:ph02:ao09.VAL')
    tempy = epics.caget('26idc:robot:Y1.VAL')
    print("Medipix X position set to: "+str(tempx))
    mpx_in_x = tempx
    print("Medipix Y position set to: "+str(tempy))
    mpx_in_y = tempy
    save_config()

def set_genie_in():
    global genie_in_x, genie_in_y
    tempx = epics.caget('26idc:sft01:ph02:ao09.VAL')
    tempy = epics.caget('26idc:robot:Y1.VAL')
    print("Genie X position set to: "+str(tempx))
    genie_in_x = tempx
    print("Genie Y position set to: "+str(tempy))
    genie_in_y = tempy
    save_config()

def beamstop_in():
    print('Moving downstream beamstop in...\n')
    mov(objx,-500)
    time.sleep(1)
    epics.caput('26idcnpi:m1.STOP',1)

def beamstop_out():
    print('Moving downstream beamstop out...\n')
    #mov(objx,-2495)
    mov(objx,-1750)
    time.sleep(1)
    epics.caput('26idcnpi:m1.STOP',1)

def prism_in():
    print('Moving prism for on-axis microscope in...\n')
    mov(condx,-35000)

def prism_out():
    print('Moving prism out...\n')
    mov(condx,-7056)
    #condy = -1302 10/15/2018

def xrf_in():
    print('Moving inboard XRF detector in...\n')
    mov(xrfx,-265) #CHECK COLLIMATOR FLUSH TO FRONT FACE

def xrf_out():
    print('Moving inboard XRF detector out...\n')
    mov(xrfx,-400)

def chopper_in():
    print('Moving chopper in...\n')
    mov(chopy,5.7) #chopper x 13.4 coarse alignment

def chopper_out():
    print('Moving chopper to beam pass through...\n')
    mov(chopy,4.7) #chopper x 13.4 coarse alignment

def pixirad_in():
    print('Moving pixirad detector on beam axis...\n')
    temp2th = epics.caget('26idcDET:base:Theta.VAL')
    tempgam = epics.caget('26idcDET:robot:Gamma.VAL')
    epics.caput('26idc:sft01:ph02:ao09.VAL',0.3)
    epics.caput('26idc:robot:Y1.VAL',92.0)
    time.sleep(1)
    epics.caput('26idcDET:base:Theta.VAL',temp2th)
    time.sleep(1)
    epics.caput('26idcDET:robot:Gamma.VAL',tempgam)

def medipix_in():
    #global mpx_in_x,mpx_in_y,optic_in_x
    temp2th = epics.caget('26idcDET:base:Theta.VAL')
    tempgam = epics.caget('26idcDET:robot:Gamma.VAL')
    if ( (abs(optic_in_x-fomx.RBV)>3000.0) and (abs(temp2th)<1.0) ):
        print("Please use zp_in() to block the direct beam first...")
        return
    print('Moving medipix 3 detector on beam axis...\n')
    epics.caput('26idc:sft01:ph02:ao09.VAL',mpx_in_x)
    epics.caput('26idc:robot:Y1.VAL',mpx_in_y)   
    time.sleep(1)
    epics.caput('26idcDET:base:Theta.VAL',temp2th)
    time.sleep(1)
    epics.caput('26idcDET:robot:Gamma.VAL',tempgam)

def genie_in():
    #global genie_in_x,genie_in_y
    print('Moving Genie detector on beam axis...\n')
    temp2th = epics.caget('26idcDET:base:Theta.VAL')
    tempgam = epics.caget('26idcDET:robot:Gamma.VAL')
    if ( (abs(temp2th)>0.05) or (abs(tempgam)>0.05) ):
        print("**Warning**  you are not imaging the direct beam - move two theta and gamma to zero to do this.")
    epics.caput('26idc:sft01:ph02:ao09.VAL',genie_in_x)
    epics.caput('26idc:robot:Y1.VAL',genie_in_y)
    while(1):
        tmp_genie_y = epics.caget('26idc:robot:Y1.VAL')
        if abs(tmp_genie_y-genie_in_y)<1:
            break
        time.sleep(1)
    epics.caput('26idcDET:base:Theta.VAL',temp2th)
    time.sleep(1)
    epics.caput('26idcDET:robot:Gamma.VAL',tempgam)

def pind_in():
    #global pind_in_x,pind_in_y
    print('Moving pin diode detector on beam axis...\n')
    temp2th = epics.caget('26idcDET:base:Theta.VAL')
    tempgam = epics.caget('26idcDET:robot:Gamma.VAL')
    epics.caput('26idc:sft01:ph02:ao09.VAL',pind_in_x)
    epics.caput('26idc:robot:Y1.VAL',pind_in_y)
    time.sleep(1)
    epics.caput('26idcDET:base:Theta.VAL',temp2th)
    time.sleep(1)
    epics.caput('26idcDET:robot:Gamma.VAL',tempgam)

# Link to scan records, patched to avoid overwriting PVs
scanrecord = "26idbSOFT"
temp1 = epics.caget(scanrecord+':scan1.T1PV')
temp2 = epics.caget(scanrecord+':scan1.T2PV')
temp3 = epics.caget(scanrecord+':scan1.T3PV')
temp4 = epics.caget(scanrecord+':scan1.T4PV')
temp5 = epics.caget(scanrecord+':scan1.NPTS')
sc1 = epics.devices.Scan(scanrecord+":scan1")
time.sleep(1)
sc1.T1PV=temp1
sc1.T2PV=temp2
sc1.T3PV=temp3
sc1.T4PV=temp4
sc1.NPTS=temp5
time.sleep(1)
temp1 = epics.caget(scanrecord+':scan2.T1PV')
temp2 = epics.caget(scanrecord+':scan2.T2PV')
temp3 = epics.caget(scanrecord+':scan2.T3PV')
temp4 = epics.caget(scanrecord+':scan2.T4PV')
temp5 = epics.caget(scanrecord+':scan2.NPTS')
time.sleep(1)
sc2 = epics.devices.Scan(scanrecord+":scan2")
sc2.T1PV=temp1
sc2.T2PV=temp2
sc2.T3PV=temp3
sc2.T4PV=temp4
sc2.NPTS=temp5
logbook = epics.caget(scanrecord+':saveData_fileSystem',as_string=True)+'/'+epics.caget(scanrecord+':saveData_subDir',as_string=True)+'/logbook.txt'

dets_list = []
# Turn on/off detectors and set exposure times
def detectors(det_list):
    numdets = np.size(det_list)
    if(numdets<1 or numdets>4):
        print("Unexpected number of detectors")
    else:
        sc1.T1PV = ''
        sc1.T2PV = ''
        sc1.T3PV = ''
        sc1.T4PV = ''
        for ii in range(numdets):
            if det_list[ii]=='scaler':
                exec('sc1.T'+str(ii+1)+'PV = \'26idc:3820:scaler1.CNT\'')
            if det_list[ii]=='xrf':
                exec('sc1.T'+str(ii+1)+'PV = \'26idcXMAP:EraseStart\'')
            if det_list[ii]=='xrf_hscan':
                exec('sc1.T'+str(ii+1)+'PV = \'26idbSOFT:scanH.EXSC\'')
            if det_list[ii]=='andor':
                exec('sc1.T'+str(ii+1)+'PV = \'26idcNEO:cam1:Acquire\'')
            if det_list[ii]=='ccd':
                exec('sc1.T'+str(ii+1)+'PV = \'26idcCCD:cam1:Acquire\'')
            if det_list[ii]=='pixirad':
                exec('sc1.T'+str(ii+1)+'PV = \'dp_pixirad_xrd75:cam1:Acquire\'')
            #if det_list[ii]=='pilatus':
#                exec('sc1.T'+str(ii+1)+'PV = \'S18_pilatus:cam1:Acquire\'')
            #if det_list[ii]=='pilatus':
            #    exec('sc1.T'+str(ii+1)+'PV = \'dp_pilatusASD:cam1:Acquire\'')
            if det_list[ii]=='pilatus':
                exec('sc1.T'+str(ii+1)+'PV = \'dp_pilatus4:cam1:Acquire\'')
            #if det_list[ii]=='pilatus':
            #    exec('sc1.T'+str(ii+1)+'PV = \'S33-pilatus1:cam1:Acquire\'')
            if det_list[ii]=='medipix':
                exec('sc1.T'+str(ii+1)+'PV = \'QMPX3:cam1:Acquire\'')
                #exec('sc1.T'+str(ii+1)+'PV = \'dp_pixirad_msd1:cam1:MultiAcquire\'')
            if det_list[ii]=='vortex':
                exec('sc1.T'+str(ii+1)+'PV = \'dp_vortex_xrd77:mca1EraseStart\'')
	dets_list = det_list		

def count_time(dettime):
    det_trigs = [sc1.T1PV, sc1.T2PV, sc1.T3PV, sc1.T4PV]
    if '26idc:3820:scaler1.CNT' in det_trigs:
        epics.caput("26idc:3820:scaler1.TP",dettime)
    #if ('26idcXMAP:EraseStart' in det_trigs) or ('26idbSOFT:scanH.EXSC' in det_trigs):
    epics.caput("26idcXMAP:PresetReal",dettime)
    if '26idcNEO:cam1:Acquire' in det_trigs:
        epics.caput("26idcNEO:cam1:Acquire",0)
        time.sleep(0.5)
        epics.caput("26idcNEO:cam1:AcquireTime",dettime)
        epics.caput("26idcNEO:cam1:ImageMode","Fixed")
    if '26idcCCD:cam1:Acquire' in det_trigs:
        epics.caput("26idcCCD:cam1:Acquire",0)
        time.sleep(0.5)
        epics.caput("26idcCCD:cam1:AcquireTime",dettime)
        epics.caput("26idcCCD:cam1:ImageMode","Fixed")
        time.sleep(0.5)
        epics.caput("26idcCCD:cam1:Initialize",1)
    if 'dp_pixirad_xrd75:cam1:Acquire' in det_trigs:
        epics.caput("dp_pixirad_xrd75:cam1:AcquireTime",dettime)
    #if 'dp_pilatusASD:cam1:Acquire' in det_trigs:
    #    epics.caput("dp_pilatusASD:cam1:AcquireTime",dettime)
    if 'dp_pilatus4:cam1:Acquire' in det_trigs:
        epics.caput("dp_pilatus4:cam1:AcquireTime",dettime)
    if 'QMPX3:cam1:Acquire' in det_trigs:
        epics.caput("QMPX3:cam1:AcquirePeriod",dettime*1000)
        #epics.caput("QMPX3:cam1:AcquirePeriod",500)
        #epics.caput("QMPX3:cam1:NumImages",np.round(dettime/0.5))
#    if 'S33-pilatus1:cam1:Acquire' in det_trigs:
#        epics.caput("S33-pilatus1:cam1:AcquireTime",dettime)
#    if 'S18_pilatus:cam1:Acquire' in det_trigs:
#        epics.caput("S18_pilatus:cam1:AcquireTime",dettime)
    # if 'dp_pixirad_msd1:MultiAcquire' in det_trigs:
   #     epics.caput("dp_pixirad_msd1:cam1:AcquireTime",dettime)
   # if 'dp_pixirad_msd1:cam1:Acquire' in det_trigs:
   #     epics.caput("dp_pixirad_msd1:cam1:AcquireTime",dettime)
    if 'dp_vortex_xrd77:mca1EraseStart' in det_trigs:
        epics.caput("dp_vortex_xrd77:mca1.PRTM",dettime)

def prescan(scanArgs):
    scannum = epics.caget(scanrecord+':saveData_scanNumber',as_string=True)
    print("scannum is {0}".format(scannum))
    pathname = epics.caget(scanrecord+':saveData_fullPathName',as_string=True)
    detmode = epics.caget("QMPX3:cam1:ImageMode");
    savemode = epics.caget("QMPX3:TIFF1:EnableCallbacks")
    if( detmode == 2 ):
        print("Warning - Medipix is in continuous acquisition mode - changing this to single")
        epics.caput("QMPX3:cam1:ImageMode",0)
        time.sleep(1)
    if( savemode == 0):
        print("Warning - Medipix is not saving images - enabling tiff output")
        epics.caput("QMPX3:TIFF1:EnableCallbacks",1)
        time.sleep(1)
    if( epics.caget('PA:26ID:SCS_BLOCKING_BEAM.VAL') ):
        print("Warning - C station shutter is closed - opening shutter")
        epics.caput("PC:26ID:SCS_OPEN_REQUEST.VAL",1)
        time.sleep(2)
    epics.caput("QMPX3:TIFF1:FilePath",pathname[:-4]+'Images/'+scannum+'/')
    time.sleep(1)
    epics.caput("QMPX3:TIFF1:FileName",'scan_'+scannum+'_img')
    time.sleep(1)
    for i in range(1,5):
        det_name = epics.caget("26idbSOFT:scan1.T{0}PV".format(i))
        if 'pilatus' in det_name:
            epics.caput("dp_pilatus4:cam1:FilePath",'/home/det/s26data/'+pathname[15:-4]+'Images/'+str(scannum)+'/')
            time.sleep(1)
            epics.caput("dp_pilatus4:cam1:FileName",'scan_'+scannum+'_pil')
            time.sleep(1)
    epics.caput("26idc:filter:Fi1:Set",0)
    time.sleep(1)

    ### LOGGING CODE ADDED BY REK
    try:
        curframe = inspect.currentframe()   #REK 20191206
        callframe = inspect.getouterframes(curframe, 2) #REK 20191206
    except:
        pass

    try:
        scanFunction = callframe[1][3]  #name of function 1 levels above prescan - should be the scan function that called this REK 20191206
    except:
        scanFunction = 'error_finding_scanfunction' #callframe[1][3] was breaking during thetascan - if the problem crops up, comment three lines above and uncomment this one
    if u'fp' in scanArgs.keys():    #default logbook handle gets passed as scan argument sometimes, we dont care about that. REK 20191211
        del(scanArgs[u'fp'])

    for k,_ in scanArgs.items():
        scanArgs[k] = str(scanArgs[k])

    logger.updateLog(scanFunction = scanFunction, scanArgs = scanArgs)  #write to verbose logbook - REK 20191206
    ### END LOGGING CODE ####

    return 0

def postscan():
    pathname = epics.caget(scanrecord+':saveData_fullPathName',as_string=True)
    epics.caput("QMPX3:TIFF1:FilePath",pathname[:-4]+'Images/')
    time.sleep(1)
    epics.caput("QMPX3:TIFF1:FileName",'image')
    time.sleep(1)
    for i in range(1,5):
        det_name = epics.caget("26idbSOFT:scan1.T{0}PV".format(i))
        if 'pilatus' in det_name:
            epics.caput("dp_pilatus4:cam1:FilePath",'/home/det/s26data/'+pathname[15:-4]+'Images/')
            time.sleep(1)
            epics.caput("dp_pilatus4:cam1:FileName",'pilatus')
            time.sleep(1)
    epics.caput("26idc:filter:Fi1:Set",1)
    time.sleep(1)

 
# Define scanning functions

def scan(is2d=0):
	stopnow = prescan(scanArgs = locals())
	if (stopnow):
		return
	if (is2d==1):
		sc2.execute=1
	else:
		sc1.execute=1
	print("Scanning...")
	time.sleep(1)
	while(sc1.BUSY or sc2.BUSY):
		time.sleep(1)
	postscan()
    

def scan1d(motor,startpos,endpos,numpts,dettime, absolute=False):
    if motor in [fomx, fomy, samy]:
        epics.caput('26idcnpi:m34.STOP',1)
        epics.caput('26idcnpi:m35.STOP',1)
    if ( (motor in [hybridx, hybridy]) and ( (abs(hybridx.RBV-hybridx.VAL)>100) or (abs(hybridy.RBV-hybridy.VAL)>100) ) ):
        print("Please use lock_hybrid() to lock piezos at current position first...")
        return
    sc1.P1PV = motor.NAME+'.VAL'
    if absolute:
        sc1.P1AR=0
    else:
        sc1.P1AR=1
    sc1.P1SP = startpos
    sc1.P1EP = endpos
    sc1.NPTS = numpts
    count_time(dettime)
    fp = open(logbook,"a")
    fp.write(' ----- \n')
    fp.write('SCAN #: '+epics.caget(scanrecord+':saveData_scanNumber',as_string=True)+' ---- '+str(datetime.datetime.now())+'\n')
    if absolute:
        fp.write('Scanning '+motor.DESC+' from '+str(startpos)+' ---> '+str(endpos)+' in '+str(numpts)+' points at '+str(dettime)+' seconds acquisition\n')
    else:
        fp.write('Scanning '+motor.DESC+' from '+str(startpos+motor.VAL)+' ---> '+str(endpos+motor.VAL))
        fp.write(' in '+str(numpts)+' points at '+str(dettime)+' seconds acquisition\n')
    fp.write(' ----- \n')
    fp.close()
    time.sleep(1)
    stopnow = prescan(scanArgs = locals());
    if (stopnow):
        return
    sc1.execute=1
    print("Scanning...")
    time.sleep(1)
    while(sc1.BUSY == 1):
        time.sleep(1)
    postscan()

def scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime, absolute=False):
    if (motor1 in [fomx, fomy, samy]) or (motor2 in [fomx, fomy, samy]):
        epics.caput('26idcnpi:m34.STOP',1)
        epics.caput('26idcnpi:m35.STOP',1)
    if ( ( (motor1 in [hybridx, hybridy]) or (motor2 in [hybridx,hybridy]) ) and ( (abs(hybridx.RBV-hybridx.VAL)>100) or (abs(hybridy.RBV-hybridy.VAL)>100) ) ):
        print("Please use lock_hybrid() to lock piezos at current position first...")
        return
    sc2.P1PV = motor1.NAME+'.VAL'
    sc1.P1PV = motor2.NAME+'.VAL'
    if absolute:
        sc1.P1AR=0
        sc2.P1AR=0
    else:
        sc1.P1AR=1
        sc2.P1AR=1
    sc2.P1SP = startpos1
    sc1.P1SP = startpos2
    sc2.P1EP = endpos1
    sc1.P1EP = endpos2
    sc2.NPTS = numpts1
    sc1.NPTS = numpts2
    count_time(dettime)
    fp = open(logbook,"a")
    fp.write(' ----- \n')
    fp.write('SCAN #: '+epics.caget(scanrecord+':saveData_scanNumber',as_string=True)+' ---- '+str(datetime.datetime.now())+'\n')
    if absolute:
        fp.write('2D Scan:\n')
        fp.write('Inner loop: '+motor2.DESC+' from '+str(startpos2)+' ---> '+str(endpos2))
        fp.write(' in '+str(numpts2)+' points at '+str(dettime)+' seconds acquisition\n')
        fp.write('Outer loop: '+motor1.DESC+' from '+str(startpos1)+' ---> '+str(endpos1))
        fp.write(' in '+str(numpts1)+' points at '+str(dettime)+' seconds acquisition\n')   
    else:
        fp.write('2D Scan:\n')
        fp.write('Outer loop: '+motor1.DESC+' from '+str(startpos1+motor1.VAL)+' ---> '+str(endpos1+motor1.VAL))
        fp.write(' in '+str(numpts1)+' points at '+str(dettime)+' seconds acquisition\n')
        fp.write('Inner loop: '+motor2.DESC+' from '+str(startpos2+motor2.VAL)+' ---> '+str(endpos2+motor2.VAL))
        fp.write(' in '+str(numpts2)+' points at '+str(dettime)+' seconds acquisition\n')
    fp.write(' ----- \n')
    fp.close()
    time.sleep(1)
    stopnow = prescan(scanArgs = locals());
    if (stopnow):
        return
    sc2.execute=1
    print("Scanning...")
    time.sleep(1)
    while(sc2.BUSY == 1):
        time.sleep(1)
    postscan()

def focalseries(z_range,numptsz,y_range,numptsy,dettime,motor1=fomz,motor2=hybridy):
    sc1.P1PV = motor2.NAME+'.VAL'
    sc2.P1PV = motor1.NAME+'.VAL'
    sc1.P1SP = -y_range/2.0
    sc2.P1SP = -z_range/2.0
    sc1.P1EP = y_range/2.0
    sc2.P1EP = z_range/2.0
    sc1.NPTS = numptsy
    sc2.NPTS = numptsz
    sc1.P1AR = 1
    sc2.P1AR = 1
    sc2.P2AR = 1
    sc2.P3AR = 1
    sc2.P2PV = hybridy.NAME+'.VAL'
    sc2.P2SP = 1.177*z_range/400   #change y offset here
    sc2.P2EP = -1.177*z_range/400
    sc2.P3PV = hybridx.NAME+'.VAL'
    sc2.P3SP = 0.3125*z_range/400   #change x offset here
    sc2.P3EP = -0.3125*z_range/400
    count_time(dettime)
    time.sleep(1)
    if ( (abs(hybridx.RBV-hybridx.VAL)>50) or (abs(hybridy.RBV-hybridy.VAL)>50) ):
        print("Please use lock_hybrid() to lock piezos at current position first...")
        sc2.P2PV = ''
        sc2.P3PV = ''
        return
    stopnow = prescan(scanArgs = locals());
    if (stopnow):
        return
    sc2.execute=1
    print("Scanning...")
    time.sleep(1)
    while(sc2.BUSY == 1):
        time.sleep(1)
    postscan()
    time.sleep(2)
    sc2.P2PV = ''
    sc2.P3PV = ''

def defocus(z_move):
    movr(fomz,z_move)
    movr(hybridy,-1.177*2*z_move/400) #SOH: added factor of 2 that is needed to get correct runout
    movr(hybridx,-0.31*2*z_move/400)

def timeseries(numpts,dettime=1.0):
    tempsettle1 = sc1.PDLY
    tempsettle2 = sc1.DDLY
    tempdrive = sc1.P1PV
    tempstart = sc1.P1SP
    tempend = sc1.P1EP
    sc1.PDLY = 0.0
    sc1.DDLY = 0.0
    sc1.P1PV = "26idcNES:sft01:ph01:ao03.VAL"
    sc1.P1AR = 1
    sc1.P1SP = 0.0
    sc1.P1EP = numpts*dettime
    sc1.NPTS = numpts+1
    count_time(dettime)
    fp = open(logbook,"a")
    fp.write(' ----- \n')
    fp.write('SCAN #: '+epics.caget(scanrecord+':saveData_scanNumber',as_string=True)+' ---- '+str(datetime.datetime.now())+'\n')
    fp.write('Timeseries: '+str(numpts)+' points at '+str(dettime)+' seconds acquisition\n')
    fp.write(' ----- \n')
    fp.close()
    time.sleep(1)
    stopnow = prescan(scanArgs = locals());
    if (stopnow):
        return
    sc1.execute=1
    print("Scanning...")
    time.sleep(2)
    while(sc1.BUSY == 1):
        time.sleep(1)
    postscan()
    sc1.PDLY = tempsettle1
    sc1.DDLY = tempsettle2
    sc1.P1PV = tempdrive
    sc1.P1SP = tempstart
    sc1.P1EP = tempend

 
def spiral(stepsize,numpts,dettime):
    epics.caput('26idpvc:userCalc5.OUTN','')
    epics.caput('26idpvc:userCalc6.OUTN','')
    epics.caput('26idpvc:userCalc5.CALC$','B+'+str(stepsize/2)+'*SQRT(A)*COS(4*SQRT(A))')
    epics.caput('26idpvc:userCalc6.CALC$','B+'+str(stepsize/2)+'*SQRT(A)*SIN(4*SQRT(A))')
    epics.caput('26idpvc:sft01:ph01:ao04.VAL',hybridx.RBV)
    epics.caput('26idpvc:sft01:ph01:ao05.VAL',hybridy.RBV)
    epics.caput('26idpvc:sft01:ph01:ao01.VAL',0.0)
    time.sleep(1)
#    epics.caput('26idpvc:userCalc5.OUTN','26idcDEV:X_HYBRID_SP.VAL')
#    epics.caput('26idpvc:userCalc6.OUTN','26idcDEV:Y_HYBRID_SP.VAL')
    epics.caput('26idpvc:userCalc5.OUTN','26idcnpi:X_HYBRID_SP.VAL')
    epics.caput('26idpvc:userCalc6.OUTN','26idcnpi:Y_HYBRID_SP.VAL')
    temppos = sc1.P1PV
    tempcen = sc1.P1CP
    tempwidth = sc1.P1WD
    time.sleep(1)
    sc1.P1PV = '26idpvc:sft01:ph01:ao01.VAL'
    sc1.P1AR=1
    sc1.P1SP = 0.0
    sc1.P1EP = numpts-1
    sc1.NPTS = numpts
    count_time(dettime)
    fp = open(logbook,"a")
    fp.write(' ----- \n')
    fp.write('SCAN #: '+epics.caget(scanrecord+':saveData_scanNumber',as_string=True)+' ---- '+str(datetime.datetime.now())+'\n')
    fp.write('Scanning spiral from x:'+str(hybridx.VAL)+' y:'+str(hybridy.VAL)+' with step size of: '+str(stepsize)+' nm')
    fp.write(' in '+str(numpts)+' points at '+str(dettime)+' seconds acquisition\n')
    fp.write(' ----- \n')
    fp.close()
    time.sleep(1)
    stopnow = prescan(scanArgs = locals());
    if (stopnow):
        return
    sc1.execute=1
    print("Scanning...")
    time.sleep(1)
    while(sc1.BUSY == 1):
        time.sleep(1)
    postscan()
    time.sleep(1)
    sc1.P1PV = temppos
    sc1.P1CP = tempcen
    sc1.P1WD = tempwidth
    epics.caput('26idpvc:userCalc5.OUTN','')
    epics.caput('26idpvc:userCalc6.OUTN','')

def spiralsquare(spiral_step, spiral_ctime):

    print("if you abort this scan, please make sure the scanmode is switched back and sc1.P2PV cleared !")
    # add this to my cleanup macro so that it is done automatically in the future

    if abs(hybridx.RBV-hybridx.VAL)>100 or abs(hybridy.RBV-hybridy.VAL)>100:
        print("Please use lock_hybrid() to lock piezos at current position first...")
        return

    sc1.P1PV = "26idcnpi:X_HYBRID_SP.VAL"
    sc1.P2PV = "26idcnpi:Y_HYBRID_SP.VAL"

    sc1.P1AR = 0  # absolute, not sure it is useful, but be safe
    sc1.P2AR = 0  # absolute, not sure it is useful, but be safe

    spiral_x0 = hybridx.RBV
    spiral_y0 = hybridy.RBV 

    spiral_traj = np.load("optimized_route.npz")

    spiral_npts = int(spiral_traj['x'].shape[0])

    spiral_x = spiral_traj['x']*spiral_step+spiral_x0
    spiral_y = spiral_traj['y']*spiral_step+spiral_y0
    count_time(spiral_ctime)
    
    sc1.NPTS = spiral_npts

    sc1.P1PA = spiral_x
    sc1.P2PA = spiral_y
    print("switching to look up mode")
    sc1.P1SM = 1
    sc1.P2SM = 1
    time.sleep(1)

    stopnow = prescan(scanArgs = locals());
    if (stopnow):
        return
    sc1.execute=1
    print("Scanning...")
    time.sleep(1)
    while(sc1.BUSY == 1):
        time.sleep(1)
    postscan()

    print("switching to linear mode")
    sc1.P1SM = 0
    sc1.P2SM = 0
    sc1.P2PV = ""



def spiralscan(spiral_step, spiral_npts, spiral_ctime):

    print("if you abort this scan, please make sure the scanmode is switched back and sc1.P2PV cleared !")
    # add this to my cleanup macro so that it is done automatically in the future

    if abs(hybridx.RBV-hybridx.VAL)>100 or abs(hybridy.RBV-hybridy.VAL)>100:
        print("Please use lock_hybrid() to lock piezos at current position first...")
        return

    sc1.P1PV = "26idcnpi:X_HYBRID_SP.VAL"
    sc1.P2PV = "26idcnpi:Y_HYBRID_SP.VAL"

    sc1.P1AR = 0  # absolute, not sure it is useful, but be safe
    sc1.P2AR = 0  # absolute, not sure it is useful, but be safe

    spiral_x0 = hybridx.RBV
    spiral_y0 = hybridy.RBV 
    spiral_x = np.zeros(spiral_npts)+spiral_x0
    spiral_y = np.zeros(spiral_npts)+spiral_y0
    count_time(spiral_ctime)
    sc1.NPTS = spiral_npts

    for i in range(1, spiral_npts):
        spiral_x[i] += np.sqrt(i)*np.cos(4*np.sqrt(i))*spiral_step
        spiral_y[i] += np.sqrt(i)*np.sin(4*np.sqrt(i))*spiral_step

    sc1.P1PA = spiral_x
    sc1.P2PA = spiral_y
    print("switching to look up mode")
    sc1.P1SM = 1
    sc1.P2SM = 1
    time.sleep(1)

    stopnow = prescan(scanArgs = locals());
    if (stopnow):
        return
    sc1.execute=1
    print("Scanning...")
    time.sleep(1)
    while(sc1.BUSY == 1):
        time.sleep(1)
    postscan()

    print("switching to linear mode")
    sc1.P1SM = 0
    sc1.P2SM = 0
    sc1.P2PV = ""


def jitterspiralscan(spiral_step, spiral_npts, spiral_ctime, jitter_std, jitter_type = 1):

    print("if you abort this scan, please make sure the scanmode is switched back and sc1.P2PV cleared !")
    # add this to my cleanup macro so that it is done automatically in the future

    if abs(hybridx.RBV-hybridx.VAL)>100 or abs(hybridy.RBV-hybridy.VAL)>100:
        print("Please use lock_hybrid() to lock piezos at current position first...")
        return

    sc1.P1PV = "26idcnpi:X_HYBRID_SP.VAL"
    sc1.P2PV = "26idcnpi:Y_HYBRID_SP.VAL"

    sc1.P1AR = 0  # absolute, not sure it is useful, but be safe
    sc1.P2AR = 0  # absolute, not sure it is useful, but be safe

    spiral_x0 = hybridx.RBV
    spiral_y0 = hybridy.RBV 
    spiral_x = np.zeros(spiral_npts)+spiral_x0
    spiral_y = np.zeros(spiral_npts)+spiral_y0
    count_time(spiral_ctime)
    sc1.NPTS = spiral_npts

    for i in range(1, spiral_npts):
        spiral_x[i] += np.sqrt(i)*np.cos(4*np.sqrt(i))*spiral_step
        spiral_y[i] += np.sqrt(i)*np.sin(4*np.sqrt(i))*spiral_step

    scannum = epics.caget(scanrecord+':saveData_scanNumber',as_string=True)

    spiral_xxx = np.zeros(spiral_npts)
    spiral_yyy = np.zeros(spiral_npts)
    spiral_xxx[0] = spiral_x[0]
    spiral_yyy[0] = spiral_y[0]
    for i in range(1, spiral_npts):
        spiral_xxx[i] = spiral_x[i-1] + np.random.normal(1, jitter_std) * (spiral_x[i] - spiral_x[i-1])
        spiral_yyy[i] = spiral_y[i-1] + np.random.normal(1, jitter_std) * (spiral_y[i] - spiral_y[i-1])

    spiral_xx = np.zeros(spiral_npts)
    spiral_yy = np.zeros(spiral_npts)
    spiral_xx[0] = spiral_x[0]
    spiral_yy[0] = spiral_y[0]
    for i in range(1, spiral_npts):
        spiral_xx[i] = spiral_xx[i-1] + np.random.normal(1, jitter_std) * (spiral_x[i] - spiral_x[i-1])
        spiral_yy[i] = spiral_yy[i-1] + np.random.normal(1, jitter_std) * (spiral_y[i] - spiral_y[i-1])

    if jitter_type == 1: # short range order
        sc1.P1PA = spiral_xx
        sc1.P2PA = spiral_yy
        np.save("/home/sector26/2020R2/20200610/Analysis/positions/pos{0:05d}.npy".format(int(scannum)), np.array((spiral_xx, spiral_yy)))
    else: # long range order
        sc1.P1PA = spiral_xxx
        sc1.P2PA = spiral_yyy
        np.save("/home/sector26/2020R2/20200610/Analysis/positions/pos{0:05d}.npy".format(int(scannum)), np.array((spiral_xxx, spiral_yyy)))

    print("switching to look up mode")
    sc1.P1SM = 1
    sc1.P2SM = 1
    time.sleep(1)

    stopnow = prescan(scanArgs = locals());
    if (stopnow):
        return
    sc1.execute=1
    print("Scanning...")
    time.sleep(1)
    while(sc1.BUSY == 1):
        time.sleep(1)
    postscan()

    print("switching to linear mode")
    sc1.P1SM = 0
    sc1.P2SM = 0
    sc1.P2PV = ""



def jitterscan(jitter_step, jitter_std, jitter_npts, jitter_ctime):

    print("if you abort this scan, please make sure the scanmode is switched back and sc1.P2PV cleared !")
    # add this to my cleanup macro so that it is done automatically in the future

    if abs(hybridx.RBV-hybridx.VAL)>100 or abs(hybridy.RBV-hybridy.VAL)>100:
        print("Please use lock_hybrid() to lock piezos at current position first...")
        return

    sc1.P1PV = "26idcnpi:X_HYBRID_SP.VAL"
    sc1.P2PV = "26idcnpi:Y_HYBRID_SP.VAL"

    sc1.P1AR = 0  # absolute, not sure it is useful, but be safe
    sc1.P2AR = 0  # absolute, not sure it is useful, but be safe

    jitter_x0 = hybridx.RBV
    jitter_y0 = hybridy.RBV 
    jitter_x = np.arange(jitter_npts)*jitter_step
    jitter_y = np.arange(jitter_npts)*jitter_step
    jitter_x -= jitter_x.mean()
    jitter_y -= jitter_y.mean()
    jitter_x, jitter_y = np.meshgrid(jitter_x, jitter_y)
    jitter_x = jitter_x.flatten()
    jitter_y = jitter_y.flatten()
    jitter_x = np.random.normal(jitter_x, jitter_std * jitter_step)+jitter_x0
    jitter_y = np.random.normal(jitter_y, jitter_std * jitter_step)+jitter_y0
    count_time(jitter_ctime)
    sc1.NPTS = jitter_npts * jitter_npts

    sc1.P1PA = jitter_x
    sc1.P2PA = jitter_y
    print("switching to look up mode")
    sc1.P1SM = 1
    sc1.P2SM = 1
    time.sleep(1)

    stopnow = prescan(scanArgs = locals());
    if (stopnow):
        return
    sc1.execute=1
    print("Scanning...")
    time.sleep(1)
    while(sc1.BUSY == 1):
        time.sleep(1)
    postscan()

    print("switching to linear mode")
    sc1.P1SM = 0
    sc1.P2SM = 0
    sc1.P2PV = ""

def princeton1():

    for iy in range(3):
        unlock_hybrid()
        time.sleep(1)
        movr(samy, 20)
        lock_hybrid()
        print(222)
        time.sleep(5)
        

        scan2d(hybridy, 10, -10, 51, hybridx, -4, 4, 51, 1)
        movr(attoz, 20)
        print(111)
        time.sleep(5)
        scan2d(hybridy, 10, -10, 51, hybridx, -4, 4, 51, 1)
        movr(attoz, 20)
        print(111)
        time.sleep(5)
        scan2d(hybridy, 10, -10, 51, hybridx, -4, 4, 51, 1)
        movr(attoz, -40)
        print(333)
        time.sleep(5)

            


def ptychoseires2():

    spiralsquare(.1, .5)
    spiralsquare(.05, .5)
    for i in range(3):
        movr(attoz, 5)
        print(111)
        time.sleep(10)
        spiralsquare(.1, .5)
        spiralsquare(.05, .5)

    unlock_hybrid()
    time.sleep(1)
    movr(samy, -5)
    lock_hybrid()
    time.sleep(1)

    spiralsquare(.1, .5)
    spiralsquare(.05, .5)
    for i in range(3):
        movr(attoz, -5)
        print(111)
        time.sleep(10)
        spiralsquare(.1, .5)
        spiralsquare(.05, .5)
    
    unlock_hybrid()
    time.sleep(1)
    movr(samy, -5)
    lock_hybrid()
    time.sleep(1)

    spiralsquare(.1, .5)
    spiralsquare(.05, .5)
    for i in range(3):
        movr(attoz, 5)
        print(111)
        time.sleep(10)
        spiralsquare(.1, .5)
        spiralsquare(.05, .5)

    unlock_hybrid()
    time.sleep(1)
    movr(samy, -5)
    lock_hybrid()
    time.sleep(1)

    spiralsquare(.1, .5)
    spiralsquare(.05, .5)
    for i in range(3):
        movr(attoz, -5)
        print(111)
        time.sleep(10)
        spiralsquare(.1, .5)
        spiralsquare(.05, .5)

        


def ptychoseries():

    unlock_hybrid()
    time.sleep(1)
    movr(attoz, 6)
    time.sleep(1)
    movr(attoz, 6)
    time.sleep(1)
    movr(attoz, 6)
    time.sleep(1)
    lock_hybrid()
    print("111")
    time.sleep(10)

    spiralscan(0.1, 31*31, .5)
    spiralscan(0.05, 31*31, .5)
    spiralscan(0.025, 31*31, .5)

    unlock_hybrid()
    time.sleep(1)
    movr(samy, 6)
    time.sleep(1)
    lock_hybrid()
    print("111")
    time.sleep(10)

    spiralscan(0.1, 31*31, .5)
    spiralscan(0.05, 31*31, .5)
    spiralscan(0.025, 31*31, .5)

    unlock_hybrid()
    time.sleep(1)
    movr(attoz, -6)
    time.sleep(1)
    movr(attoz, -6)
    time.sleep(1)
    movr(attoz, -6)
    time.sleep(1)
    lock_hybrid()
    print("111")
    time.sleep(10)

    spiralscan(0.1, 31*31, .5)
    spiralscan(0.05, 31*31, .5)
    spiralscan(0.025, 31*31, .5)
   
    unlock_hybrid()
    time.sleep(1)
    movr(samy, 6)
    time.sleep(1)
    lock_hybrid()
    print("111")
    time.sleep(10)

    spiralscan(0.1, 31*31, .5)
    spiralscan(0.05, 31*31, .5)
    spiralscan(0.025, 31*31, .5)

    unlock_hybrid()
    time.sleep(1)
    movr(attoz, 6)
    time.sleep(1)
    lock_hybrid()
    print("111")
    time.sleep(10)

    spiralscan(0.1, 31*31, .5)
    spiralscan(0.05, 31*31, .5)
    spiralscan(0.025, 31*31, .5)

    unlock_hybrid()
    time.sleep(1)
    movr(attoz, 6)
    time.sleep(1)
    lock_hybrid()
    print("111")
    time.sleep(10)

    spiralscan(0.1, 31*31, .5)
    spiralscan(0.05, 31*31, .5)
    spiralscan(0.025, 31*31, .5)

    unlock_hybrid()
    time.sleep(1)
    movr(attoz, 6)
    time.sleep(1)
    lock_hybrid()
    print("111")
    time.sleep(10)

    spiralscan(0.1, 31*31, .5)
    spiralscan(0.05, 31*31, .5)
    spiralscan(0.025, 31*31, .5)
    

    #def thetascan(thetapts,detchan,xscan,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime):
def thetascan(thetapts,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime):
    #scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime)
    mov(samth, thetapts[0]-0.5)
    numthpts = np.size(thetapts)
    time.sleep(1)
    #epics.caput("26idbSOFT:scan1.REFD",26); #Set horizontal reference XRF detector channel
    for ii in range(numthpts):
        mov(samth,thetapts[ii])
        print ("theta",thetapts[ii])
        #sc1.PASM = 3  #Sets lineup scan to post-scan move to peak
        #_hx0 = epics.caget("26idcnpi:X_HYBRID_SP.VAL")
        #scan1d(hybridx,10.6-3,10.6+11,141,1)  # ADJUST X LINE UP SCAN HERE
        #time.sleep(1)
        #sc1.PASM = 7  #Sets lineup scan to post-scan move to com
        #scan1d(hybridx,-3,3,121,1)  # ADJUST X LINE UP SCAN HERE
        #sc1.PASM = 2
        #movr(hybridx,-10.6)
        #time.sleep(1)
        #print("hybridx peak moved from ", _hx0, " to ", epics.caget("26idcnpi:X_HYBRID_SP.VAL"))
        scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime)  #MESH SCAN
        print("time to stop")
        time.sleep(10)
        print("too late man")


def mmscan(thetapts):
    for itheta in thetapts:
        mov(samth,itheta)
        print ("theta",itheta)
        sc1.PASM = 3  #Sets lineup scan to Center of Mass
        _hx0 = epics.caget("26idcnpi:X_HYBRID_SP.VAL")
        scan1d(hybridx,-2,2, 101, 0.5)  # ADJUST X LINE UP SCAN HERE
        print("hybridx peak moved from ", _hx0, " to ", epics.caget("26idcnpi:X_HYBRID_SP.VAL"))
        _hy0 = epics.caget("26idcnpi:Y_HYBRID_SP.VAL")
        scan1d(hybridy,-2,2, 101, 0.5)  # ADJUST Y LINE UP SCAN HERE
        print("hybridy peak moved from ", _hy0, " to ", epics.caget("26idcnpi:Y_HYBRID_SP.VAL"))
    sc1.PASM = 2  #Sets post-scan move back to prior position'''
  

"""
def theta_scan():
    thetascan([40.4,40.6,40.8],hybridy,-3.5,0.9,177,hybridx,-0.15,0.15,16,1)  
    mov(samth,40.39)
    sc1.PASM = 3  #Sets lineup scan to Center of Mass
    print("scanning hybridx to recenter")
    _hx0 = epics.caget("26idcnpi:X_HYBRID_SP.VAL")
    xscan=4; #X scan range
    scan1d(hybridx,-xscan/2,xscan/2, 121, 0.2)  # ADJUST X LINE UP SCAN HERE
    time.sleep(1)
    print("hybridx peak moved from ", _hx0, " to ", epics.caget("26idcnpi:X_HYBRID_SP.VAL"))      
    thetascan([41.8,42,42.2,42.4,42.6],hybridy,-3.5,0.9,177,hybridx,-0.15,0.15,16,1)  
"""

def tao1():

    for ttt in range(30):
        #movr(hybridy, 0.5)
        hy0 = hybridy.RBV
        sc1.PASM = 5 # pos edge
        scan1d(hybridy, -0.4, 0.4, 41, .5)
        print("drift in Y : {0:.3f}".format(hybridy.RBV-hy0))
        #movr(hybridy, -0.5)
        #movr(hybridx, 0.5)
        #hx0 = hybridx.RBV
        #scan1d(hybridx, -0.3, 0.3, 61, .5)
        #print("drift in X : {0:.3f}".format(hybridx.RBV-hx0))
        #movr(hybridx, -0.5)
        #print('600 sec to interrupt')
        time.sleep(600)
        #print('too late')
        

def cai1():

    old_nrj = epics.caget("26idbDCM:sm8.RBV")
    print("current energy is ", old_nrj)
    epics.caput("26idbDCM:sm8.VAL", 11838, wait=1)
    time.sleep(2)
    epics.caput("26idbDCM:sm8.VAL", 11838, wait=1)
    time.sleep(2)
    print("moved energy to ", epics.caget("26idbDCM:sm8.RBV"))
    nrj_diff = 11838 - old_nrj
    focus_diff = nrj_diff/11888*23012
    print('moving fcous by ', -1*int(focus_diff))
    defocus(-1*int(focus_diff))

    scan1d(DCMenergy, 1, 101, 101, 85);
    
    defocus(int(focus_diff))

    epics.caput("26idbDCM:sm8.VAL", old_nrj, wait=1)
    time.sleep(2)
    epics.caput("26idbDCM:sm8.VAL", old_nrj, wait=1)
    time.sleep(2)
    print("moved energy to ", epics.caget("26idbDCM:sm8.RBV"))

    
def rocking(theta_start,theta_end,npts,xstart,xend,nxpts,dettime):
    
	dstep=(theta_start-theta_end)/float(npts)
	currth=epics.caget("atto2:PIC867:1:m1.RBV")
   
	jj=theta_start 
	for ii in range(npts+1):
		mov(samth,currth+jj)
		sc1.PASM = 7  #Sets lineup scan to post-scan move to peak - REFERENCE DETECTOR MUST BE CORRECTLY SET
		time.sleep(1)
		scan1d(hybridx,xstart,xend,nxpts, 0.5)  # ADJUST X LINE UP SCAN HERE
		#scan1d(hybridy, -3,3,51, 0.3) #scan the y positoin
		sc1.PASM = 2  #Sets post-scan move back to prior position
		time.sleep(1)
		scan1d(hybridx,xstart,xend,nxpts+1,dettime)  #Smaller 1D scan with long exposures
		jj+=dstep

#Change in eV
def change_energy(E0,Z0,delta_E):
    stDCM = epics.caget("26idbDCM:sm8.RBV")
    stUDS = epics.caget("26idbDCM:sm2.RBV")
    stUUS = epics.caget("26idbDCM:sm3.RBV")
    defocus(delta_E*Z0/E0)
    epics.caput("26idbDCM:sm8.VAL",stDCM+delta_E)
    time.sleep(1)
    epics.caput("26idbDCM:sm2.VAL",stUDS+delta_E/1000.0)
    time.sleep(1)
    epics.caput("26idbDCM:sm3.VAL",stUUS+delta_E/1000.0)
    time.sleep(1)



#def energyscan(E0,Z0,EVrange,numpts,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime):
#E0, Estep in eV
# Z0 is focal length at E0 from ZP calculator (in MICRONS)
def energyscan1d(E0,Z0,EVrange,numpts,motor1,startpos1,endpos1,numpts1,dettime, move_undulator=1): #input Z0 in MICRONS
    stDCM = epics.caget("26idbDCM:sm8.RBV")
    stUDS = epics.caget("26idbDCM:sm2.RBV")
    stUUS = epics.caget("26idbDCM:sm3.RBV")
    stHybY = epics.caget("26idcnpi:Y_HYBRID_SP.VAL")
    Estep = np.float(EVrange)/(numpts-1)
    HybYstep=0.4/30.0*0 #About 13 nm per eV around 9 keV. Toggle 0 as req 
    defocus((EVrange/2.0)*Z0/E0)
    epics.caput("26idbDCM:sm8.VAL",stDCM-EVrange/2.0)
    time.sleep(1)
    if move_undulator == 1:
        epics.caput("26idbDCM:sm2.VAL",stUDS-EVrange/2000.0)
        time.sleep(1)
        epics.caput("26idbDCM:sm3.VAL",stUUS-EVrange/2000.0)
        time.sleep(1)
    epics.caput("26idcnpi:Y_HYBRID_SP.VAL", stHybY-EVrange/2.0*HybYstep)
    time.sleep(1)
    print("Scanning at:%.1f eV" %(epics.caget("26idbDCM:sm8.RBV")))
    scan1d(motor1,startpos1,endpos1,numpts1,dettime)  #LINE SCAN
    for ii in range(1,numpts):
         defocus(-Estep*Z0/E0)
         time.sleep(1)
         epics.caput("26idbDCM:sm8.VAL",stDCM-EVrange/2.0+Estep*ii)
         time.sleep(1)
         if move_undulator == 1:
             epics.caput("26idbDCM:sm2.VAL",stUDS-EVrange/2000.0+Estep*ii/1000)
             time.sleep(1)
             epics.caput("26idbDCM:sm3.VAL",stUUS-EVrange/2000.0+Estep*ii/1000)
             time.sleep(1)
         epics.caput("26idcnpi:Y_HYBRID_SP.VAL", stHybY-EVrange/2.0*HybYstep+ii*HybYstep*Estep)
         time.sleep(1) 
         scan1d(motor1,startpos1,endpos1,numpts1,dettime)  #LINE SCAN
    epics.caput("26idbDCM:sm8.VAL",stDCM)
    time.sleep(1)
    if move_undulator == 1:
        epics.caput("26idbDCM:sm2.VAL",stUDS)
        time.sleep(1)
        epics.caput("26idbDCM:sm3.VAL",stUUS)
        time.sleep(1)
    defocus((EVrange/2.0)*Z0/E0)
    time.sleep(1)
    epics.caput("26idcnpi:Y_HYBRID_SP.VAL",stHybY)

#Z0 in MICRONS        
#E0, Estep in eV
# Z0 is focal length at E0 from ZP calculator (in MICRONS)
def energyscan2d(E0,Z0,EVrange,numpts,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime, move_undulator=1):
    stDCM = epics.caget("26idbDCM:sm8.RBV")
    stUDS = epics.caget("26idbDCM:sm2.RBV")
    stUUS = epics.caget("26idbDCM:sm3.RBV")
    stHybY = epics.caget("26idcnpi:Y_HYBRID_SP.VAL")
    Estep = np.float(EVrange)/(numpts-1)
    HybYstep=0.4/30.0*0 #About 13 nm per eV around 9 keV. Toggle 0 as req 
    defocus((EVrange/2.0)*Z0/E0)
    epics.caput("26idbDCM:sm8.VAL",stDCM-EVrange/2.0)
    time.sleep(1)
    if move_undulator == 1:
        epics.caput("26idbDCM:sm2.VAL",stUDS-EVrange/2000.0)
        time.sleep(1)
        epics.caput("26idbDCM:sm3.VAL",stUUS-EVrange/2000.0)
        time.sleep(1)
    epics.caput("26idcnpi:Y_HYBRID_SP.VAL", stHybY-EVrange/2.0*HybYstep)
    time.sleep(1)
    print("Scanning at:%.1f eV" %(epics.caget("26idbDCM:sm8.RBV")))
    scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime)  #MESH SCAN
    for ii in range(1,numpts):
         defocus(-Estep*Z0/E0)
         time.sleep(1)
         epics.caput("26idbDCM:sm8.VAL",stDCM-EVrange/2.0+Estep*ii)
         time.sleep(1)
         if move_undulator == 1:
             epics.caput("26idbDCM:sm2.VAL",stUDS-EVrange/2000.0+Estep*ii/1000)
             time.sleep(1)
             epics.caput("26idbDCM:sm3.VAL",stUUS-EVrange/2000.0+Estep*ii/1000)
             time.sleep(1)
         epics.caput("26idcnpi:Y_HYBRID_SP.VAL", stHybY-EVrange/2.0*HybYstep+ii*HybYstep*Estep)
         time.sleep(1) 
         print("Scanning at:%.1f eV" %(epics.caget("26idbDCM:sm8.RBV")))
         scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime)  #MESH SCAN
    epics.caput("26idbDCM:sm8.VAL",stDCM)
    time.sleep(1)
    if move_undulator == 1:
        epics.caput("26idbDCM:sm2.VAL",stUDS)
        time.sleep(1)
        epics.caput("26idbDCM:sm3.VAL",stUUS)
        time.sleep(1)
    defocus((EVrange/2.0)*Z0/E0)
    time.sleep(1)
    epics.caput("26idcnpi:Y_HYBRID_SP.VAL",stHybY)

       

def theta2thetascan(thstartpos,thendpos,numpts,dettime):
    sc1.P2PV = '26idcDET:base:Theta.VAL'
    sc1.P2SP = 2*thstartpos
    sc1.P2EP = 2*thendpos
    sc1.P2AR=1
    time.sleep(1)
    scan1d(samth,thstartpos,thendpos,numpts,dettime)
    sc1.P2PV = ''
    


def panelscan(ypositions,xpositions,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime):
    numypts = np.size(ypositions)
    for ii in range(numypts):
        mov(hybridy,ypositions[ii])
        mov(hybridx,xpositions[ii])
        time.sleep(1)
        #----Uncomment below for lineup scan ----
        #sc1.PASM = 3  #Sets lineup scan to post-scan move to peak - REFERENCE DETECTOR MUST BE CORRECTLY SET
        #time.sleep(1)
        #scan1d(hybridy,-1,1,51,3)  #LINE UP SCAN
        #sc1.PASM = 2  #Sets post-scan move back to prior position
        #time.sleep(1)
        #-----Uncomment above for lineup scan ----
        scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime)  #MESH SCAN

def tempscan(temppts,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime):
    numtemppts = np.size(temppts)
    for ii in range(numtemppts):
        print('Changing temperature to '+str(temppts[ii])+'...')
        epics.caput('26idcSOFT:LS336:tc1:OUT1:SP',temppts[ii])
        if ii>1:
            movr(samy,-0.1666*(temppts[ii]-temppts[ii-1]))
        time.sleep(900)
        scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime)  #MESH SCAN

def pvscan(pvname,pvpts,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime):
    numpvpts = np.size(pvpts);
    for ii in range(numpvpts):
        print('Changing '+pvname+' to '+str(pvpts[ii])+'...')
        time.sleep(1)
        epics.caput(pvname,pvpts[ii])
        time.sleep(1)
        #if ii>1:
        #    movr(hybridy,-0.1666*(temppts[ii]-temppts[ii-1]))
        #time.sleep(900)
        scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime)
    epics.caput(pvname,0.0)
    time.sleep(1)
"""
def set_beam_energy(EkeV):
    und_us = [8.0299, 9.0497, 10.1098, 11.1395, 12.089]
    und_ds = [8.0701, 9.1298, 10.1398, 11.2202, 12.080]
    chi2 = [-0.1533, -0.2046, -0.2701, -0.3362, -0.4017]
    th2 = [5.27, 5.57, 5.67, 5.77, 5.77]
    if (EkeV<8.0) or (EkeV>12.0):
        print("Routine is only good between 8 and 12 keV- exiting")
        return
    i3 = float(EkeV-8)
    i1 = int(math.ceil(i3))
    i2 = int(math.floor(i3))
    if i1==i2:
        und_us_interp = und_us[i1]
        und_ds_interp = und_ds[i1]
        chi2_interp = chi2[i1]
        th2_interp = th2[i1]
    else:
        und_us_interp = (i1 - i3)*und_us[i2] + (i3 - i2)*und_us[i1]
        und_ds_interp = (i1 - i3)*und_ds[i2] + (i3 - i2)*und_ds[i1]
        chi2_interp = (i1 - i3)*chi2[i2] + (i3 - i2)*chi2[i1]
        th2_interp = (i1 - i3)*th2[i2] + (i3 - i2)*th2[i1]
    dcm_interp = EkeV*1000
    print('Moving to-  und_US:'+str(und_us_interp)+' und_DS:'+str(und_ds_interp)+' Chi2:'+str(chi2_interp)+' Th2:'+str(th2_interp)+' DCM:'+str(dcm_interp))
    epics.caput("26idbDCM:sm2.VAL",und_ds_interp)
    time.sleep(1)
    epics.caput("26idbDCM:sm3.VAL",und_us_interp)
    time.sleep(1)
    epics.caput("26idbDCM:sm5.VAL",chi2_interp)
    time.sleep(1)
    epics.caput("26idb:DAC1_1.VAL",th2_interp)
    time.sleep(1)
    epics.caput("26idbDCM:sm8.VAL",dcm_interp)
    time.sleep(1)
"""


def set_phase(phase):
    ph1 = [0,7,15,19,28,34,40,48,55,60,67,74,81,87,99,117,127,133,145,159,168,182,198,210,220,227,237,245,255,272,283,295,308,320,330,340,358]
    amp1 = [1.1,1.15,1.27,1.33,1.37,1.3,1.28,1.29,1.29,1.32,1.32,1.30,1.2,1.11,.98,.96,.93,.87,.82,.81,.84,.85,.88,.88,.88,.85,.86,.91,.91,.87,.85,.83,.83,.9,.93,.96,1.02]
    i1 = int(math.ceil(float(phase)/10))
    i2 = int(math.floor(float(phase)/10))
    if i1==i2:
        ph2=ph1[i1]
        amp2=amp1[i1]
    else:
        ph2 = (i1-float(phase)/10)*(ph1[i2])+(float(phase)/10-i2)*(ph1[i1])
        amp2 = (i1-float(phase)/10)*(amp1[i2])+(float(phase)/10-i2)*(amp1[i1])
    epics.caput('26idbDCM:sft01:ph01:ao05.VAL',amp2)
    epics.caput('26idbDCM:sft01:ph01:ao06.VAL',ph2)
    epics.caput('26idbDCM:sft01:ph01:ao08.VAL',float(phase))

def ramp_phase(phase):
    ph1=epics.caget('26idbDCM:sft01:ph01:ao08.VAL')
    while(ph1<>phase):
        step1 = (phase>ph1)*1.0-(phase<ph1)*1.0
        set_phase(float(ph1)+step1)
        #print([ph1,phase,step1,float(ph1)+step1])
        time.sleep(0.5)
        ph1=epics.caget('26idbDCM:sft01:ph01:ao08.VAL')
    print('Done')

def watch_phase():
    ph1 = np.round(epics.caget('26idbDCM:sft01:ph01:ao07.VAL'))
    while(1):
        time.sleep(1)
        ph2 = np.round(epics.caget('26idbDCM:sft01:ph01:ao07.VAL'))
        if(ph1<>ph2):
            ramp_phase(ph2)
            ph1=ph2



#def scan3d(outermotor,outerstart,outerstop,outernumpts,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,exp_time):
#    movr(outermotor,outerstart)
#    time.sleep(1)
#    for ii in range(outernumpts):
#        movr(outermotor,ii*((outerstop-outerstart)/outernumpts))
#        time.sleep(1)
#        scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,exp_time)
#        time.sleep(1)
#    mov(outermotor,(outerstart+outerstop)/2)

def scanfocusmaps(defocus_list, motor1, startpos1, endpos1, numpts1, motor2, startpos2, endopos2, numpts2, dettime):

    for ii in range(np.size(defocus_list)):
        defocus(defocus_list[ii]);
        scan2d( motor1, startpos1, endpos1, numpts1, motor2, startpos2, endopos2, numpts2, dettime )


    
def dotwoscans():
    scan2d( hybridy, -.5, .5, 51, hybridx, -.5, .5, 51, 0.5 );
    scan2d( hybridy, -1, 1, 51, hybridx, -1, 1, 51, 0.5 );
    scan2d( hybridy, -2, 2, 51, hybridx, -2, 2, 51, 0.5 );
    defocus(-30);
    scan2d( hybridy, -.5, .5, 51, hybridx, -.5, .5, 51, 0.5 );
    scan2d( hybridy, -1, 1, 51, hybridx, -1, 1, 51, 0.5 );
    scan2d( hybridy, -2, 2, 51, hybridx, -2, 2, 51, 0.5 );




  
def lastnightscan():
	scan2d(hybridy,-0.2,0.2,21,hybridx,-1.8,1.8,181,1)
	scan2d(hybridy,-0.4,0.4,21,hybridx,-3.6,3.6,181,1)
	scan2d(hybridy,-0.6,0.6,21,hybridx,-5.4,5.4,181,1)
	scan2d(hybridy,-0.8,0.8,21,hybridx,-7.2,7.2,181,1)
	scan2d(hybridy,-1.0,1.0,21,hybridx,-9.0,9.0,181,1)
	
def scantimeseries(motor, stepsize, numpts):
    for ii in range(numpts):
        timeseries(1000, 1)
        movr(motor, stepsize)


def thetavsEscan(Evminrel,Evmaxrel,numpts,dtime):
    stDCM = epics.caget("26idbDCM:sm8.RBV")
    stUDS = epics.caget("26idbDCM:sm2.RBV")
    stUUS = epics.caget("26idbDCM:sm3.RBV")
    ststh = epics.caget("atto2:PIC867:1:m1.RBV")
    Estep = np.float(Evmaxrel-Evminrel)/(numpts-1)
    epics.caput("26idbDCM:sm8.VAL",stDCM+Evminrel)
    time.sleep(1)
    epics.caput("26idbDCM:sm2.VAL",stUDS+Evminrel/1000.0)
    time.sleep(1)
    epics.caput("26idbDCM:sm3.VAL",stUUS+Evminrel/1000.0)
    time.sleep(1)
    for ii in range(1,numpts+1):
        scan1d(samth,-.5,.5,26,dtime)
        time.sleep(1)
        epics.caput("26idbDCM:sm8.VAL",stDCM+Evminrel+Estep*ii)
        time.sleep(1)
        epics.caput("26idbDCM:sm2.VAL",stUDS+(Evminrel+Estep*ii)/1000)
        time.sleep(1)
        epics.caput("26idbDCM:sm3.VAL",stUUS+(Evminrel+Estep*ii)/1000)
        time.sleep(1)
    epics.caput("26idbDCM:sm8.VAL",stDCM)
    time.sleep(1)
    epics.caput("26idbDCM:sm2.VAL",stUDS)
    time.sleep(1)
    epics.caput("26idbDCM:sm3.VAL",stUUS)
    time.sleep(1)

def mvrE(EVrel):
    stDCM = epics.caget("26idbDCM:sm8.RBV")
    stUDS = epics.caget("26idbDCM:sm2.RBV")
    stUUS = epics.caget("26idbDCM:sm3.RBV")
    epics.caput("26idbDCM:sm8.VAL",stDCM+EVrel)
    time.sleep(1)
    epics.caput("26idbDCM:sm2.VAL",stUDS+EVrel/1000.0)
    time.sleep(1)
    epics.caput("26idbDCM:sm3.VAL",stUUS+EVrel/1000.0)
    time.sleep(1)

def EfixQ(E,Enum,dettime):
	mvrE(E/2)
	for ii in range(1,Enum+1):
		count_time(dettime)


def xscan_20181210():
    movr(hybridx, -3.5)
    movr(hybridy, 2)
    scan1d(hybridx, 0, 12, 61, 60)
    mvrE(4)
    movr(samth,-0.0164)
    scan1d(hybridx, 0, 12, 61, 60)
    mvrE(-4)
    movr(samth,0.0164)


def finalscan():
	scan2d(hybridy, -7.5, 7.5, 61, hybridx, -22.5, 7.5, 121, 0.5);
	movr(hybridy,-10)
	scan2d(hybridy, -7.5, 7.5, 61, hybridx, -7.5, 7.5, 61, 0.5);
	movr(hybridy,-10)
	scan2d(hybridy, -7.5, 7.5, 61, hybridx, -7.5, 7.5, 61, 0.5);
	movr(hybridy,-10)
	scan2d(hybridy, -7.5, 7.5, 61, hybridx, -7.5, 7.5, 61, 0.5);


def geniescan1d(motor, start, end, numpts1, dettime):

    epics.caput("S26idcGen1:cam1:ImageMode", 0)
    epics.caput("S26idcGen1:cam1:AcquireTime", dettime)
    _m_pos0 = motor.RBV
    _m_pos = np.linspace(start, end, numpts1) + _m_pos0
    _tmp_data = np.zeros(numpts1)
    for i in range(numpts1):
        motor.VAL = _m_pos[i]
        time.sleep(.5)
        epics.caput("S26idcGen1:cam1:Acquire", 1)
        time.sleep(dettime+.5)
        _tmp_data[i] = epics.caget("S26idcGen1:image1:ArrayData", as_numpy=1, count=1360*1024).sum()
    motor.VAL = _m_pos0
    pyplot.plot(_m_pos, _tmp_data)
    pyplot.show()
    print("peak at {0}".format(_m_pos[_tmp_data.argmax()]))

'''
def flyxy(xstart, xend, nx, ystart, yend, ny, flytime):

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_fly:
        socket_fly.connect(("localhost", 9988))
        socket_fly.sendall("{0} {1} {2} {3} {4} {5} {6}".format(xstart, xend, nx, ystart, yend, ny, flytime))
        socket_fly.listen(1)
        conn, addr = socket_fly.accept()
        reply = conn.recv(1024)
    print reply
'''        
    
        
'''
def thetascantime(thetapts,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime):
    
    for ii in range(0,2):
        mov(samth,18.0)
        mov(samth,18.4)
        thetascan(thetapts,motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime)

def scan2dtime(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime):
    
    for ii in range(0,5):

        movr(hybridy, -2.5)
        sc1.PASM = 7  #Sets lineup scan to post-scan move to peak - REFERENCE DETECTOR MUST BE CORRECTLY SET
        time.sleep(1)
        scan1d(hybridx,-8,8,101, 0.3)  # ADJUST X LINE UP SCAN HERE
        scan1d(hybridy, -5,5,51, 0.3) #scan the y positoin
        sc1.PASM = 2  #Sets post-scan move back to prior position
        time.sleep(1)
    
        movr( hybridy, 2.5)
        movr( hybridx, 1.67 )

        scan2d(motor1,startpos1,endpos1,numpts1,motor2,startpos2,endpos2,numpts2,dettime)


def gotoROI():
    sc1.PASM = 7  #Sets lineup scan to post-scan move to peak - REFERENCE DETECTOR MUST BE CORRECTLY SET
    time.sleep(1)
    scan1d(hybridx,-8,8,101, 0.3)  # ADJUST X LINE UP SCAN HERE
    scan1d(hybridy, -5,5,51, 0.3) #scan the y positoin
    sc1.PASM = 2  #Sets post-scan move back to prior position
    time.sleep(1)
    movr( hybridy, 2.5) #middle of the A
    movr( hybridx, 1.67) #middle of the A
'''   

#def chasetemp():

#    sc1.PASM = 7 
#    c=epics.caget('26idbDCM:sft01:ph01:ao12.VAL') #done flag 
#    
#    while c<0.5:
#
#        time.sleep(1)
#        scan1d(hybridx,-5,5,41, 0.3)  # ADJUST X LINE UP SCAN HERE
#        time.sleep(1)
#        scan1d(hybridy, -5,5,41, 0.3) #scan the y positoin
#        print("hybridx = %f, hybridy = %f"%( epics.caget( '26idcnpi:X_HYBRID_SP.VAL' ), epics.caget( '26idcnpi:Y_HYBRID_SP.VAL' ) ) )
#        print( datetime.datetime.now() )
#        c=epics.caget('26idbDCM:sft01:ph01:ao12.VAL') #done flag 
#         
#    sc1.PASM = 2


def ttscan(theta):
    mov(samth,theta)
    time.sleep(1)
    epics.caput("26idbSOFT:scan1.REFD",30)
    sc1.PASM = 3  #Sets lineup scan to post-scan move to peak
    scan1d(hybridx,-1,1,41,3)
    scan1d(hybridy,-1,1,41,3)
    sc1.PASM = 2  #Sets post-scan move back to prior position
    scan2d(hybridy,-.8,.8,81,hybridx,-.8,.8,81,3)


def tttscan():
    mov(samth, 26.000)
    time.sleep(5)
    mov(samth, 26.175)
    epics.caput("26idbSOFT:scan1.REFD",8)
    sc1.PASM = 3  #Sets lineup scan to post-scan move to peak
    scan1d(hybridy,-1,1,41,1)
    sc1.PASM = 2  #Sets post-scan move back to prior position
    scan2d(hybridy,-.7,.7,71,hybridx,-.5,.5,51,3)
    mov(samth, 26.240)
    time.sleep(1)
    scan2d(hybridy,-.7,.7,71,hybridx,-.5,.5,51,3)

    mov(hybridy, 1439.25)
    time.sleep(5)
    mov(samth, 26.000)
    time.sleep(5)
    mov(samth, 26.175)
    epics.caput("26idbSOFT:scan1.REFD",8)
    sc1.PASM = 3  #Sets lineup scan to post-scan move to peak
    scan1d(hybridy,-1,1,41,1)
    sc1.PASM = 2  #Sets post-scan move back to prior position
    scan2d(hybridy,-.7,.7,71,hybridx,-.5,.5,51,3)
    mov(samth, 26.240)
    time.sleep(1)
    scan2d(hybridy,-.7,.7,71,hybridx,-.5,.5,51,3)

def prescandark():
    scannum = epics.caget(scanrecord+':saveData_scanNumber',as_string=True)
    print("scannum is {0}".format(scannum))
    pathname = epics.caget(scanrecord+':saveData_fullPathName',as_string=True)
    detmode = epics.caget("QMPX3:cam1:ImageMode");
    savemode = epics.caget("QMPX3:TIFF1:EnableCallbacks")
    if( detmode == 2 ):
        print("Warning - Medipix is in continuous acquisition mode - changing this to single")
        epics.caput("QMPX3:cam1:ImageMode",0)
        time.sleep(1)
    if( savemode == 0 ):
        print("Warning - Medipix is not saving images - enabling tiff output")
        epics.caput("QMPX3:TIFF1:EnableCallbacks",1)
        time.sleep(1)
    if( epics.caget('PA:26ID:SCS_BLOCKING_BEAM.VAL') ):
        print("Warning - C station shutter is closed - opening shutter")
        epics.caput("PC:26ID:SCS_OPEN_REQUEST.VAL",1)
        time.sleep(2)
    epics.caput("QMPX3:TIFF1:FilePath",pathname[:-4]+'Images/'+scannum+'/')
    time.sleep(1)
    epics.caput("QMPX3:TIFF1:FileName",'scan_'+scannum+'_img')
    time.sleep(1)
    epics.caput("dp_pilatus4:cam1:FilePath",'/home/det/s26data/2020R1/20200131/Images/'+scannum+'/') #'/home/det'+pathname[5:-4]+'Images/'+scannum+'/')
    time.sleep(1)
    epics.caput("dp_pilatus4:cam1:FileName",'scan_'+scannum+'_img_Pilatus')
    time.sleep(1)
    epics.caput("26idc:softGlue:BUFFER-3_IN_Signal",'1')
    time.sleep(1)
    #epics.caput("S18_pilatus:cam1:FilePath",'/mnt/Sector_26'+pathname[5:-4]+'Images/'+scannum+'/')
    #time.sleep(1)
    #epics.caput("S18_pilatus:cam1:FileName",'scan_'+scannum+'_img_Pilatus')
    #time.sleep(1)
    #epics.caput("dp_pilatus4:cam1:FilePath",'/home/det/Sector_26_new/2019R2/20190806/'+'Images/'+scannum+'/')
    #time.sleep(1)
    #epics.caput("dp_pilatus4:cam1:FileName",'scan_'+scannum+'_img_Pilatus')
    #time.sleep(1)
    #epics.caput("26idc:filter:Fi1:Set",0)
    #time.sleep(1)
    return 0

def postscandark():
    epics.caput("26idc:softGlue:BUFFER-3_IN_Signal",'0')
    time.sleep(1)
    pathname = epics.caget(scanrecord+':saveData_fullPathName',as_string=True)
    epics.caput("QMPX3:TIFF1:FilePath",pathname[:-4]+'Images/')
    time.sleep(1)
    epics.caput("QMPX3:TIFF1:FileName",'image')
    time.sleep(1)
    epics.caput("dp_pilatus4:cam1:FilePath",'/home/det/s26data/2020R1/20200131/Images/') #'/home/det'+pathname[5:-4]+'Images/'+scannum+'/')
    time.sleep(1)
    epics.caput("dp_pilatus4:cam1:FileName",'image_Pilatus')
    time.sleep(1)
    #epics.caput("S18_pilatus:cam1:FilePath",'/mnt/Sector_26'+pathname[5:-4]+'Images/')
    #time.sleep(1)
    #epics.caput("S18_pilatus:cam1:FileName",'image_Pilatus')
    #time.sleep(1)
    #epics.caput("dp_pilatus4:cam1:FilePath",'/home/det/Sector_26_new/2019R2/20190806/'+'Images/')
    #time.sleep(1)
    #epics.caput("dp_pilatus4:cam1:FileName",'image_Pilatus')
    #time.sleep(1)
    #epics.caput("26idc:filter:Fi1:Set",1)
    #time.sleep(1)


def timeseriesdark(numpts,dettime=1.0):
    tempsettle1 = sc1.PDLY
    tempsettle2 = sc1.DDLY
    tempdrive = sc1.P1PV
    tempstart = sc1.P1SP
    tempend = sc1.P1EP
    sc1.PDLY = 0.0
    sc1.DDLY = 0.0
    sc1.P1PV = "26idcNES:sft01:ph01:ao03.VAL"
    sc1.P1AR = 1
    sc1.P1SP = 0.0
    sc1.P1EP = numpts*dettime
    sc1.NPTS = numpts+1
    count_time(dettime)
    fp = open(logbook,"a")
    fp.write(' ----- \n')
    fp.write('SCAN #: '+epics.caget(scanrecord+':saveData_scanNumber',as_string=True)+' ---- '+str(datetime.datetime.now())+'\n')
    fp.write('Timeseries: '+str(numpts)+' points at '+str(dettime)+' seconds acquisition\n')
    fp.write(' ----- \n')
    fp.close()
    time.sleep(1)
    stopnow = prescandark();
    if (stopnow):
        return
    sc1.execute=1
    print("Scanning...")
    time.sleep(2)
    while(sc1.BUSY == 1):
        time.sleep(1)
    postscandark()
    sc1.PDLY = tempsettle1
    sc1.DDLY = tempsettle2
    sc1.P1PV = tempdrive
    sc1.P1SP = tempstart
    sc1.P1EP = tempend




def yuzi1():

    for itheta in np.arange(21.26,24.5,0.3):
        mov(samth, itheta)
        sc1.PASM = 7
        scan1d(attox, -50, 20, 71, 1)
        scan1d(hybridx, -3, 3, 61, 1)
        scan1d(hybridy, -7, 7, 71, 1)
        sc1.PASM = 2
        movr(attox, -15)
        scan2d(hybridy, -8, 8, 81, hybridx, -3, 3, 81, 1)
        movr(attox, 15)
        print("time to stop")
        time.sleep(10)
        print("too late man")






"""
# Define zone plate in-focus position
#10 keV below
optic_in_x = -1083.2
optic_in_y = -966.1
optic_in_z = -942.3		

# Define medipix3 in-beam position
mpx_in_x = -.15
mpx_in_y = 93.7

# Define genie camera in-beam position
genie_in_x = 6.3
genie_in_y = 133.0

# Define pin diode in-beam position
pind_in_x = -36.5
pind_in_y = 123.0


"""

