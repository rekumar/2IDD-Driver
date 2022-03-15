import epics
import epics.devices
import time
import os
import functools
from tqdm import tqdm
from s2driver.logging import initialize_logbook, get_experiment_dir

# from s2driver.xeol.xeol import XEOLController
logger = initialize_logbook()

### PVs
PV_KEY = {
    # "x_center_Act": "2idd:m40.RBV",
    # "x_center_Rqs": "2idd:m40.VAL",
    # "y_center_Act": "2idd:m39.RBV",
    # "y_center_Rqs": "2idd:m39.VAL",
    # "z_value_Act": "2idd:m36.RBV",
    # "z_value_Rqs": "2idd:m36.VAL",
    # "x_width_fly": "2idd:FscanH.P1WD",
    # "y_width_fly": "2idd:Fscan1.P1WD",
    # "x_step_fly": "2idd:FscanH.P1SI",
    # "y_step_fly": "2idd:Fscan1.P1SI",
    "dwell_fly": "2idd:Flyscans:Setup:DwellTime.VAL",
    # "x_center_fly": "2idd:FscanH.P1CP",
    # "y_center_fly": "2idd:Fscan1.P1CP",
    # "x_center_mode_fly": "2idd:FscanH.P1AR",
    # "y_center_mode_fly": "2idd:Fscan1.P1AR",
    # "run_fly": "2idd:Fscan1.EXSC",
    # "wait_fly": "2idd:FscanH.WAIT",
    "cur_lines_fly": "2idd:Fscan1.CPT",
    "tot_lines_fly": "2idd:Fscan1.NPTS",
    "abort_fly": "2idd:FAbortScans.PROC",
    # "x_width_step": "2idd:scan1.P1WD",
    # "y_width_step": "2idd:scan2.P1WD",
    # "x_step_step": "2idd:scan1.P1SI",
    # "y_step_step": "2idd:scan2.P1SI",
    "dwell_step": "2iddXMAP:PresetReal",
    # "x_center_step": "2idd:scan1.P1CP",
    # "y_center_step": "2idd:scan2.P1CP",
    # "x_center_mode_step": "2idd:scan1.P1AR",
    # "y_center_mode_step": "2idd:scan2.P1AR",
    "cur_lines_step": "2idd:scan2.CPT",
    "tot_lines_step": "2idd:scan2.NPTS",
    # "run_step": "2idd:scan2.EXSC",
    # "wait_step": "2idd:scan1.WAIT",
    "abort_step": "2idd:AbortScans.PROC",
    "msg1d": "2idd:Fscan1.SMSG",
    "open_shutter": "2idd:s1:openShutter.PROC",
    "close_shutter": "2idd:s1:closeShutter.PROC",
    "fname_saveData": "2iddXMAP:netCDF1:FileName",
    "filesys": "2idd:saveData_fileSystem",
    "subdir": "2idd:saveData_subDir",
    "next_scan": "2idd:saveData_scanNumber",
    "basename": "2idd:saveData_baseName",
    "det_time": "2idd:3820:ElapsedReal",
}
PVS = {k: epics.PV(v) for k, v in PV_KEY.items()}

### Motors
samx = epics.Motor("2idd:m40")  # example: '26idcnpi:m10.'
samy = epics.Motor("2idd:m39")
samz = epics.Motor("2idd:m36")
# fomx = epics.Motor()
# fomy = epics.Motor()
# fomz = epics.Motor()
# osax = epics.Motor()
# osay = epics.Motor()
# osaz = epics.Motor()

MOVEMENT_THRESHOLD = {
    samx: 100,  # in um
    samy: 100,
    samz: 100,
    # samth: 5,
    # fomx: 50,
    # fomy: 50,
    # fomz: 50,
    # osax: 50,
    # osay: 50,
    # osaz: 50,
}  # movements that change motor positions by greater than this threshold amount will require user confirmation to proceed

### Scanners
sc1 = epics.devices.Scan("2idd:scan1")
sc2 = epics.devices.Scan("2idd:scan2")
flyh = epics.devices.Scan("2idd:FscanH")
fly1 = epics.devices.Scan("2idd:Fscan1")

CANCEL_PVS = {
    sc1: epics.PV("2idd:AbortScans.PROC"),
    sc2: epics.PV("2idd:AbortScans.PROC"),
    fly1: epics.PV("2idd:FAbortScans.PROC"),
}
# for attribute in ["T1PV", "T2PV", "T3PV", "T4PV", "NPTS"]: #TODO not sure what this is, got it from 26idc code -- maybe unnecessary at 2idd?
#     setattr(sc1, attribute, epics.caget(SCAN_RECORD + ":scan1." + attribute))
#     setattr(sc2, attribute, epics.caget(SCAN_RECORD + ":scan2." + attribute))

### XEOL
# xeol_controller = XEOLController()
xeol_controller = 0

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
            logger.debug("User aborted large movement request.")
            raise Exception(
                "Aborted move command - user indicated the target position was input incorrectly!"
            )


def mov(motor: epics.Motor, position: float):
    """Move a motor to a specific coordinate

    Args:
        motor (epics.Motor): motor to move
        position (float): position (um or degrees) to move motor to
    """
    position = round(position, 4)
    _check_for_huge_movement(motor=motor, target_position=position)
    # if motor in [fomx, fomy, samy]:  # TODO check if this is necessary here
    #     epics.caput("26idcnpi:m34.STOP", 1)
    #     epics.caput("26idcnpi:m35.STOP", 1)
    #     epics.caput("26idcSOFT:userCalc1.SCAN", 0)
    #     epics.caput("26idcSOFT:userCalc3.SCAN", 0)

    result = motor.move(position, wait=True)
    if result == 0:
        time.sleep(0.5)
        logger.info("Moved %s to %.4f", motor, position)
        # epics.caput("26idcSOFT:userCalc1.SCAN", 6)  # TODO not sure what this is doing?
        # epics.caput("26idcSOFT:userCalc3.SCAN", 6)
    else:
        logger.info("Failed attempt to move %s to %.4f", motor, position)


def movr(motor: epics.Motor, delta: float):
    """Move a motor by a relative amount

    Args:
        motor (epics.Motor): motor to move
        delta (float): distance (typically um) to move motor by
    """
    target_position = motor.VAL + delta
    mov(motor=motor, position=target_position)


def close_shutter():
    """Move shutter into the beampath"""
    epics.caput(f"2idd:s1:closeShutter.PROC", 1, wait=True)
    logger.debug("Shutter inserted into the beam path.")


def open_shutter():
    """Move shutter out of the beam path"""
    epics.caput(f"2idd:s1:openShutter.PROC", 1, wait=True)
    logger.debug("Shutter removed from the beam path.")


def insert_filter(index: int):
    """Move a filter into the beampath

    Args:
        index (int): index of the filter. Valid options assumed to be 1, 2, 3, and 4

    Raises:
        ValueError: Invalid filter index
    """
    if index not in [1, 2, 3, 4]:
        raise ValueError("Filter index must be 1, 2, 3, or 4!")
    epics.caput("2idd:s1:sendCommand", f"I{index}", wait=True)
    logger.debug("Filter %i moved in to beam path.", index)


def remove_filter(index: int):
    """Move a filter out of the beampath

    Args:
        index (int): index of the filter. Valid options assumed to be 1, 2, 3, and 4

    Raises:
        ValueError: Invalid filter index
    """
    if index not in [1, 2, 3, 4]:
        raise ValueError("Filter index must be 1, 2, 3, or 4!")
    epics.caput("2idd:s1:sendCommand", f"R{index}", wait=True)
    logger.debug("Filter %i moved out of beam path.", index)


def remove_all_filters():
    """Move all filters out of the beam path"""
    for i in [1, 2, 3, 4]:
        remove_filter(i)


def get_next_scan_number() -> int:
    return PVS["next_scan"].value


### Scanning Commands
def prescan(*args, **kwargs) -> bool:
    """Checks whether a scan is valid.

    Args:
        args: list of arguments to pass to the scan command

    Returns:
        bool: whether scan should proceed. False = scan is not started
    """
    scannum = get_next_scan_number()
    print("scannum is {0}".format(scannum))
    pathname = epics.caget("2idd:saveData_fullPathName", as_string=True)
    return True


def postscan(*args, **kwargs):
    return True


def scan_moderator(func):
    """Decorator to apply prescan and postscan routines around scan functions"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if prescan(*args, **kwargs):
            open_shutter()  # remove the shutter
            result = func(*args, **kwargs)
            close_shutter()  # replace the shutter
            return postscan(result, *args, **kwargs)
        else:
            logger.debug("Failed prescan check")

            raise Exception("Failed prescan check, scan will not be executed!")

    return wrapper


def _set_dwell_time(dwelltime: float):
    """Sets detectors to count for a given detector time

    Args:
        dwelltime (float): detector counting time, in milliseconds
    """
    dwelltime = round(dwelltime)  # nearest ms
    epics.caput(
        "2idd:Flyscans:Setup:DwellTime.VAL", dwelltime, wait=True
    )  # flyscan takes dwelltime in milliseconds
    epics.caput(
        "2iddXMAP:PresetReal", dwelltime / 1e3, wait=True
    )  # step scan takes dwelltime in seconds
    logger.debug("Set detector dwell time to %.2f ms", dwelltime)


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
    # if motor in [
    #     fomx,
    #     fomy,
    #     samy,
    # ]:  # TODO not sure which of these needs to be stopped for 2idd
    #     epics.caput("26idcnpi:m34.STOP", 1)
    #     epics.caput("26idcnpi:m35.STOP", 1)

    scanner.P1PV = motor.NAME + ".VAL"
    if absolute:
        scanner.P1AR = 0
        _check_for_huge_movement(motor, startpos)
    else:
        scanner.P1AR = 1
        _check_for_huge_movement(motor, startpos + motor.VAL)
    scanner.P1SP = startpos
    scanner.P1EP = endpos
    scanner.NPTS = numpts
    logger.debug(
        "Set scanner %s to scan %s from %.2f to %.2f, absolute is %i",
        scanner,
        motor,
        startpos,
        endpos,
        absolute,
    )


def _execute_scan(scanner: epics.devices.Scan, scantype: str):
    """Executes a scan. Blocks and prints a progress bar for the scan. Will unblock when scan is complete.

    Args:
        scanner (epics.devices.Scan): scanner object to track progress of
    """
    npts = scanner.NPTS
    scannum = get_next_scan_number()
    try:
        scanner.execute = 1  # start the scan
        logger.info("Started %s %i", scantype, scannum)
        with tqdm(total=npts, desc=f"Scan {scannum}") as pbar:
            while scanner.BUSY == 0:
                time.sleep(0.1)  # wait for scan to begin
            current_point = 0
            while scanner.BUSY == 1:
                if scanner.CPT != current_point:
                    current_point = scanner.CPT
                    pbar.n = current_point  # update progress bar to current number of points completed
                    pbar.display()
                time.sleep(1)
            pbar.n = npts  # complete the progress bar
            pbar.display()
    except KeyboardInterrupt:
        cancel = CANCEL_PVS.get(scanner, None)
        if cancel is not None:
            cancel.put(1)
        logger.info(f"Scan {scannum} canceled using ctrl-c!")


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

    _execute_scan(sc1, scantype="scan1d")


@scan_moderator
def scan1d_xeol(
    motor: epics.Motor,
    startpos: float,
    endpos: float,
    numpts: int,
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
        absolute (bool, optional): whether startpos and endpos are relative to the current motor position (False) or absolute motor coordinates (True). Defaults to False (relative).
    """

    if not xeol_controller.IS_PRESENT:
        raise Exception(
            "XEOL Controller is not present, probably the spectrometer was not connected when s2driver was initialized. Can't run an XEOL measurement!"
        )
    _set_scanner(
        scanner=sc1,
        motor=motor,
        startpos=startpos,
        endpos=endpos,
        numpts=numpts,
        absolute=absolute,
    )
    _set_dwell_time(dwelltime)

    xeol_output_filepath = os.path.join(
        get_experiment_dir(),
        "XEOL",
        f'{PVS["basename"].val}_{PVS["scan_number"].val:04d}_XEOL.h5',
    )
    xeol_thread = xeol_controller.prime_for_stepscan(
        scantype="scan1d", output_filepath=xeol_output_filepath
    )
    _execute_scan(sc1, scantype="scan1d_xeol")
    xeol_thread.join()  # will join when xeol data has been saved to file


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
        absolute (bool, optional): whether startpos and endpos are relative to the current motor position (False) or absolute motor coordinates (True). Defaults to False (relative).
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

    _execute_scan(sc2, scantype="scan2d")


@scan_moderator
def scan2d_xeol(
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
        absolute (bool, optional): whether startpos and endpos are relative to the current motor position (False) or absolute motor coordinates (True). Defaults to False (relative).
    """

    if not xeol_controller.IS_PRESENT:
        raise Exception(
            "XEOL Controller is not present, probably the spectrometer was not connected when s2driver was initialized. Can't run an XEOL measurement!"
        )
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

    xeol_output_filepath = os.path.join(
        get_experiment_dir(),
        "XEOL",
        f'{PVS["basename"].val}_{PVS["scan_number"].val:04d}_XEOL.h5',
    )
    xeol_thread = xeol_controller.prime_for_stepscan(
        scantype="scan2d", output_filepath=xeol_output_filepath
    )
    _execute_scan(sc2, scantype="scan2d_xeol")
    xeol_thread.join()  # will join when xeol data has been saved to file


@scan_moderator
def flyscan2d(
    startpos1: float,
    endpos1: float,
    numpts1: int,
    startpos2: float,
    endpos2: float,
    numpts2: int,
    dwelltime: float,
    absolute: bool = False,
    wait_for_h5: bool = False,
):
    """Executes a flyscan using samx and samy. At 2idd, flyscanning requires that the x scanner is in absolute coordinates and that the y scanner is in relative coordinates.

    Args:
        startpos1 (float): starting coordinate for samx, um
        endpos1 (float): ending coordinate for samx, um
        numpts1 (int): number of steps to break the x scan into
        startpos2 (float): starting coordinate for samy, um
        endpos2 (float): ending coordinate for samy, um
        numpts2 (int): number of steps to break the y scan into
        dwelltime (float): dwelltime (ms) per point
        absolute (bool, optional): whether startpos and endpos are relative to the current motor position (False) or absolute motor coordinates (True). In either case the coordinates will be converted to absolute x, relative y for flyscanner. Defaults to False (relative).
    """
    if absolute:
        y0 = (startpos2 + endpos2) / 2
        mov(samy, y0)  # move such that we are centered on scan in y dimension.
        startpos2 -= samy.VAL
        endpos2 -= samy.VAL
    else:
        startpos1 += samx.VAL
        endpos1 += samx.VAL

    _check_for_huge_movement(samx, startpos1)
    flyh.P1SP = startpos1
    flyh.P1EP = endpos1
    flyh.NPTS = numpts1
    logger.debug(
        "Set flyscanner %s to scan horizontally from %.2f to %.2f",
        flyh,
        startpos1,
        endpos1,
    )

    _set_scanner(
        scanner=fly1,
        motor=samy,
        startpos=startpos2,
        endpos=endpos2,
        numpts=numpts2,
        absolute=False,
    )  # flyy must be relative
    _set_dwell_time(dwelltime)

    h5_output_filepath = os.path.join(
        get_experiment_dir(),
        "img.dat",
        f'{PVS["basename"].value}_{PVS["next_scan"].value:04d}.h5',
    )
    _execute_scan(fly1, scantype="flyscan2d")

    if wait_for_h5:
        while not os.path.exists(h5_output_filepath):
            time.sleep(0.1)  # wait for the file to appear (ie write has begun)
        time.sleep(3)  # wait for file to be completely written to disk


@scan_moderator
def timeseries(numpts: int, dwelltime: float):
    """Record data with constant beam exposure at a single point. This is currently done by a scan1d over samx with a relative move of 0 lol.

    Args:
        numpts (int): number of scans to record
        dwelltime (float): duration (ms) to expose each scan
    """
    _set_scanner(
        scanner=sc1,
        motor=samx,
        startpos=0,
        endpos=0,
        numpts=numpts,
        absolute=False,
    )
    _set_dwell_time(dwelltime)

    _execute_scan(sc1, scantype="timeseries")


@scan_moderator
def timeseries_xeol(numpts: int, dwelltime: float):
    """Record data with constant beam exposure at a single point. This is currently done by a scan1d over samx with a relative move of 0 lol.

    Args:
        numpts (int): number of scans to record
        dwelltime (float): duration (ms) to expose each scan
    """
    _set_scanner(
        scanner=sc1,
        motor=samx,
        startpos=0,
        endpos=0,
        numpts=numpts,
        absolute=False,
    )
    _set_dwell_time(dwelltime)

    xeol_output_filepath = os.path.join(
        get_experiment_dir(),
        "XEOL",
        f'{PVS["basename"].val}_{PVS["scan_number"].val:04d}_XEOL.h5',
    )
    xeol_thread = xeol_controller.prime_for_stepscan(
        scantype="timeseries", output_filepath=xeol_output_filepath
    )
    _execute_scan(sc1, scantype="timeseries_xeol")
    xeol_thread.join()  # will join when xeol data has been saved to file
