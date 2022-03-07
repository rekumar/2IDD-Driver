from pvComm import pvComm
from scan2idd import xrfSetup, scanStart, scanFinish

pvs = pvComm()
scandic = {'scanType':'Fly-XRF', 'smpName':'aa', 'x_scan':850.0,
           'y_scan':285.0, 'z_scan':0, 'dwell':250, 'width':100,
           'w_step':0.5, 'height':100, 'h_step':0.5 }
xrfSetup(pvs, scandic)
scanStart(pvs, scandic['scanType'], scandic['x_scan'])
run_str = 'run_fly' if scandic['scanType'] == 'Fly-XRF' else 'run_step'
while pvs.pvs[run_str].pv.value:
    print('Scanning running')
scanFinish(pvs)
