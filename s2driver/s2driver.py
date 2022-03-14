from s2driver.closedloop.bridge import S2Server
from s2driver.xeol.xeol import XEOLController
from s2driver.driving import *  # all driving commands
from s2driver.logging import get_logbook

logger = get_logbook()
server = S2Server()
xeol_controller = XEOLController()
