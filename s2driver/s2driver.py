from multiprocessing.sharedctypes import Value
import epics
import epics.devices
import time
import os
import functools

### Motors
samx = epics.Motor("FILL_IN_PV")  # example: '26idcnpi:m10.'
samy = epics.Motor()
samz = epics.Motor()
samth = epics.Motor()
fomx = epics.Motor()
fomy = epics.Motor()
fomz = epics.Motor()
osax = epics.Motor()
osay = epics.Motor()
osaz = epics.Motor()

MOVEMENT_THRESHOLD = {
    samx: 100,
    samy: 100,
    samz: 100,
    samth: 5,
    fomx: 50,
    fomy: 50,
    fomz: 50,
    osax: 50,
    osay: 50,
    osaz: 50,
}  # movements that change motor positions by greater than this threshold amount will require user confirmation to proceed
### Scan Records
# Link to scan records, patched to avoid overwriting PVs (note from Tao at 26-id-c)

SCAN_RECORD = "26idbSOFT"  # TODO fix. I think this is the prefix for all the file saving PV, scan PV, etc.

sc1 = epics.devices.Scan(SCAN_RECORD + ":scan1")
time.sleep(1)
sc2 = epics.devices.Scan(SCAN_RECORD + ":scan1")
time.sleep(1)
for attribute in ["T1PV", "T2PV", "T3PV", "T4PV", "NPTS"]:
    setattr(sc1, attribute, epics.caget(SCAN_RECORD + ":scan1." + attribute))
    setattr(sc2, attribute, epics.caget(SCAN_RECORD + ":scan2." + attribute))

LOGBOOK = os.path.join(
    epics.caget(SCAN_RECORD + ":saveData_fileSystem", as_string=True),
    epics.caget(SCAN_RECORD + ":saveData_subDir", as_string=True),
    "logbook.txt",
)  # Currently not being used, but we could imagine saving a log of commands in the user folder this way


### Single-Action Commands


def _check_for_huge_movement(motor: epics.Motor, target_position: float):
    """Checks if the movement step requested by the user is suspiciously large

    Args:
        motor (epics.Motor): motor to be moved
        target_position (float): target position of the motor

    Raises:
        Exception: The motor step was put in incorrectly, and the movement was aborted.
    """
    current_position = motor.VAL  # current setpoint
    delta = abs(target_position - current_position)
    if delta > MOVEMENT_THRESHOLD[motor]:
        response = input(
            f"You asked to move {motor} by {delta:.2f} (from {current_position} to {target_position} - is that correct? (y/n)"
        )
        if response != "y":
            raise Exception(
                "Aborted move command - user indicated the target position was input incorrectly!"
            )


def mov(motor: epics.Motor, position: float):
    """Move a motor to a specific coordinate

    Args:
        motor (epics.Motor): motor to move
        position (float): position (typically um) to move motor to
    """
    _check_for_huge_movement(motor=motor, target_position=position, absolute=True)
    if motor in [fomx, fomy, samy]:  # TODO check if this is necessary here
        epics.caput("26idcnpi:m34.STOP", 1)
        epics.caput("26idcnpi:m35.STOP", 1)
        epics.caput("26idcSOFT:userCalc1.SCAN", 0)
        epics.caput("26idcSOFT:userCalc3.SCAN", 0)

    result = motor.move(position, wait=True)
    if result == 0:
        time.sleep(0.5)
        print(motor.DESC + " ---> " + str(motor.RBV))
        epics.caput("26idcSOFT:userCalc1.SCAN", 6)  # TODO not sure what this is doing?
        epics.caput("26idcSOFT:userCalc3.SCAN", 6)
    else:
        print("Motion failed")


def movr(motor: epics.Motor, delta: float):
    """Move a motor by a relative amount

    Args:
        motor (epics.Motor): motor to move
        delta (float): distance (typically um) to move motor by
    """
    target_position = motor.VAL + delta
    mov(motor=motor, position=target_position)


def filter_in(index: int):
    """Move a filter into the beampath

    Args:
        index (int): index of the filter. Valid options assumed to be 1, 2, 3, and 4

    Raises:
        ValueError: Invalid filter index
    """
    if index not in [1, 2, 3, 4]:
        raise ValueError("Filter index must be 1, 2, 3, or 4!")
    epics.caput(
        f"26idc:filter:Fi{int(index)}:Set", 1
    )  # TODO double check that 1/0 is correct here
    time.sleep(1)


def filter_out(index: int):
    """Move a filter into the beampath

    Args:
        index (int): index of the filter. Valid options assumed to be 1, 2, 3, and 4

    Raises:
        ValueError: Invalid filter index
    """
    if index not in [1, 2, 3, 4]:
        raise ValueError("Filter index must be 1, 2, 3, or 4!")
    epics.caput(
        f"26idc:filter:Fi{int(index)}:Set", 0
    )  # TODO double check that 1/0 is correct here
    time.sleep(1)


### Scanning Commands
def prescan(result, *args, **kwargs) -> bool:
    """Checks whether a scan is valid.

    Args:
        args: list of arguments to pass to the scan command

    Returns:
        bool: whether scan should proceed. False = scan is not started
    """
    scannum = epics.caget(SCAN_RECORD + ":saveData_scanNumber", as_string=True)
    print("scannum is {0}".format(scannum))
    pathname = epics.caget(SCAN_RECORD + ":saveData_fullPathName", as_string=True)
    time.sleep(1)
    return True


def postscan(*args, **kwargs):
    return True


def scan_moderator(func):
    """Decorator to apply prescan and postscan routines around scan functions"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if prescan(*args, **kwargs):
            filter_out(1)  # remove the shutter
            result = func(*args, **kwargs)
            filter_in(1)  # replace the shutter
            return postscan(result, *args, **kwargs)
        else:
            raise Exception("Failed prescan check, scan will not be executed!")

    return wrapper


def _set_dwell_time(dwelltime: float):
    """Sets detectors to count for a given detector time

    Args:
        dwelltime (float): detector counting time, in milliseconds
    """
    # TODO this is all from 26idc, i expect at 2idd you only need to set the XRF and maybe ptycho camera dwell times.
    det_trigs = [sc1.T1PV, sc1.T2PV, sc1.T3PV, sc1.T4PV]
    if "26idc:3820:scaler1.CNT" in det_trigs:
        epics.caput("26idc:3820:scaler1.TP", dwelltime)
    # if ('26idcXMAP:EraseStart' in det_trigs) or ('26idbSOFT:scanH.EXSC' in det_trigs):
    epics.caput("26idcXMAP:PresetReal", dwelltime)
    if "26idcNEO:cam1:Acquire" in det_trigs:
        epics.caput("26idcNEO:cam1:Acquire", 0)
        time.sleep(0.5)
        epics.caput("26idcNEO:cam1:AcquireTime", dwelltime)
        epics.caput("26idcNEO:cam1:ImageMode", "Fixed")
    if "26idcCCD:cam1:Acquire" in det_trigs:
        epics.caput("26idcCCD:cam1:Acquire", 0)
        time.sleep(0.5)
        epics.caput("26idcCCD:cam1:AcquireTime", dwelltime)
        epics.caput("26idcCCD:cam1:ImageMode", "Fixed")
        time.sleep(0.5)
        epics.caput("26idcCCD:cam1:Initialize", 1)
    if "dp_pixirad_xrd75:cam1:Acquire" in det_trigs:
        epics.caput("dp_pixirad_xrd75:cam1:AcquireTime", dwelltime)
    # if 'dp_pilatusASD:cam1:Acquire' in det_trigs:
    #    epics.caput("dp_pilatusASD:cam1:AcquireTime",dwelltime)
    if "dp_pilatus4:cam1:Acquire" in det_trigs:
        epics.caput("dp_pilatus4:cam1:AcquireTime", dwelltime)
    if "QMPX3:cam1:Acquire" in det_trigs:
        epics.caput("QMPX3:cam1:AcquirePeriod", dwelltime * 1000)
        # epics.caput("QMPX3:cam1:AcquirePeriod",500)
        # epics.caput("QMPX3:cam1:NumImages",np.round(dwelltime/0.5))
    #    if 'S33-pilatus1:cam1:Acquire' in det_trigs:
    #        epics.caput("S33-pilatus1:cam1:AcquireTime",dwelltime)
    #    if 'S18_pilatus:cam1:Acquire' in det_trigs:
    #        epics.caput("S18_pilatus:cam1:AcquireTime",dwelltime)
    # if 'dp_pixirad_msd1:MultiAcquire' in det_trigs:
    #     epics.caput("dp_pixirad_msd1:cam1:AcquireTime",dwelltime)
    # if 'dp_pixirad_msd1:cam1:Acquire' in det_trigs:
    #     epics.caput("dp_pixirad_msd1:cam1:AcquireTime",dwelltime)
    if "dp_vortex_xrd77:mca1EraseStart" in det_trigs:
        epics.caput("dp_vortex_xrd77:mca1.PRTM", dwelltime)

    time.sleep(1)


def _set_scanner(
    scanner: epics.devices.Scan,
    motor: epics.Motor,
    startpos: float,
    endpos: float,
    numpts: int,
    absolute: bool = False,
):
    """Prepares a scanner to execute a scan

    Args:
        scanner (epics.devices.Scan): scanner object to set up
        motor (epics.Motor): motor to scan
        startpos (float): starting position, in um
        endpos (float): ending position, in um
        numpts (int): number of scan points, inclusive of startpos/endpos
        absolute (bool, optional): whether startpos and endpos are relative to the current motor position (True) or absolute motor coordinates (False). Defaults to False.
    """
    if motor in [
        fomx,
        fomy,
        samy,
    ]:  # TODO not sure which of these needs to be stopped for 2idd
        epics.caput("26idcnpi:m34.STOP", 1)
        epics.caput("26idcnpi:m35.STOP", 1)

    scanner.P1PV = motor.NAME + ".VAL"
    if absolute:
        scanner.P1AR = 0
    else:
        scanner.P1AR = 1
    scanner.P1SP = startpos
    scanner.P1EP = endpos
    scanner.NPTS = numpts


@scan_moderator
def scan1d(
    motor: epics.Motor,
    startpos: float,
    endpos: float,
    numpts: int,
    dwelltime: float,
    absolute: bool = False,
):
    """Scans across a single motor

    Args:
        motor (epics.Motor): motor to scan
        startpos (float): starting position, in um
        endpos (float): ending position, in um
        numpts (int): number of scan points, inclusive of startpos/endpos
        dwelltime (float): counting time at each point of the scan, in ms
        absolute (bool, optional): whether startpos and endpos are relative to the current motor position (True) or absolute motor coordinates (False). Defaults to False.
    """
    _set_scanner(
        scanner=sc1,
        motor=motor,
        startpos=startpos,
        endpos=endpos,
        numpts=numpts,
        absolute=absolute,
    )
    _set_dwell_time(dwelltime)
    sc1.execute = 1

    print("Scanning...")
    time.sleep(1)
    while sc1.BUSY == 1:
        time.sleep(1)


@scan_moderator
def scan2d(
    motor1: epics.Motor,
    startpos1: float,
    endpos1: float,
    numpts1: int,
    motor2: epics.Motor,
    startpos2: float,
    endpos2: float,
    numpts2: int,
    dwelltime: float,
    absolute: bool = False,
):
    """Scans across two motors

    Args:
        motor1 (epics.Motor): motor to scan
        startpos1 (float): starting position, in um
        endpos1 (float): ending position, in um
        numpts1 (int): number of scan points, inclusive of startpos/endpos
        motor2 (epics.Motor): motor to scan
        startpos2 (float): starting position, in um
        endpos2 (float): ending position, in um
        numpts2 (int): number of scan points, inclusive of startpos/endpos
        dwelltime (float): counting time at each point of the scan, in ms
        absolute (bool, optional): whether startpos and endpos are relative to the current motor position (True) or absolute motor coordinates (False). Defaults to False.
    """
    _set_scanner(
        scanner=sc1,
        motor=motor1,
        startpos=startpos1,
        endpos=endpos1,
        numpts=numpts1,
        absolute=absolute,
    )
    _set_scanner(
        scanner=sc2,
        motor=motor2,
        startpos=startpos2,
        endpos=endpos2,
        numpts=numpts2,
        absolute=absolute,
    )
    _set_dwell_time(dwelltime)
    sc2.execute = 1
    print("Scanning...")
    time.sleep(1)
    while sc2.BUSY == 1:
        time.sleep(1)


@scan_moderator
def timeseries(numpts: int, dwelltime: float):
    """Record data with constant beam exposure at a single point

    Args:
        numpts (int): number of scans to record
        dwelltime (float): duration (ms) to expose each scan
    """
    # store the current scanner parameters
    tempsettle1 = sc1.PDLY
    tempsettle2 = sc1.DDLY
    tempdrive = sc1.P1PV
    tempstart = sc1.P1SP
    tempend = sc1.P1EP

    sc1.PDLY = 0.0
    sc1.DDLY = 0.0
    sc1.P1PV = "26idcNES:sft01:ph01:ao03.VAL"  # TODO I think this is a timer PV? idk
    sc1.P1AR = 1
    sc1.P1SP = 0.0
    sc1.P1EP = numpts * dwelltime
    sc1.NPTS = numpts + 1
    _set_dwell_time(dwelltime=dwelltime)
    sc1.execute = 1
    print("Scanning...")
    time.sleep(2)
    while sc1.BUSY == 1:
        time.sleep(1)

    # restore scanner parameters
    sc1.PDLY = tempsettle1
    sc1.DDLY = tempsettle2
    sc1.P1PV = tempdrive
    sc1.P1SP = tempstart
    sc1.P1EP = tempend
