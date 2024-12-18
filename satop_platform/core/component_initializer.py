from satop_platform.components.authorization.auth import PlatformAuthorization
from satop_platform.components.groundstation.connector import GroundstationConnector
from satop_platform.components.restapi.restapi import APIApplication
from satop_platform.components.syslog.syslog import Syslog

class SatOPComponents:
    api: APIApplication
    auth: PlatformAuthorization
    syslog: Syslog
    gs: GroundstationConnector

    def __init__(self, *args, **kwargs):
        self.auth = PlatformAuthorization()
        self.api = APIApplication(self, **kwargs.get('api', None))
        self.syslog = Syslog(self)
        self.gs = GroundstationConnector(self)