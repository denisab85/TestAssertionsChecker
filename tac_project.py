import imp
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import tempfile
import datetime

if sys.platform.startswith("win"):
    import _winreg

import swifttest

import tac_assertions
import tac_common

#
# Regexps
#
SWIFTTEST_PROJECT_FILE_RX = '.*\.swift_test$'
PORT_MAPPING_FILE_RX = '([Cc]lient|[Ss]erver)\s+[Pp]ort\s+(\d+)\.(client|server)_port'
VALID_IP_ADDRESS_RX = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
WINDOWS_GUID_RX = "\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}$"

#
# Constants
#

GLOBAL_PORTS_DIR = '/opt/swifttest/resources/dotnet/Ports/'
WAIT_INTERVAL = 1 # sec

#
# Port mapping
#

class PortMappingError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Port:
    def __init__(self, log, xml_element):
        # get logical port kind and number from xml
        logical_port_kind = xml_element.tag[:6]
        logical_port_number = xml_element.find(logical_port_kind + 'PortID').text
        if logical_port_kind ==  "Client":
            offset = 1000
        elif logical_port_kind == "Server":
            offset = 2000
        else:
            self.log.error("Unknown logical port kind: " + logical_port_kind)
        try:
            logical_port_number = int(logical_port_number) - offset
        except TypeError:
            PortMappingError('No valid logical port number found in XML.')
        self.lport = tac_common.LogicalPort(logical_port_number, logical_port_kind.lower())
        # get physical port number and appliance IP from xml
        physical_port_number = xml_element.find('Port').text
        appliance_ip = xml_element.find('Appliance').text
        try:
            if not re.match(VALID_IP_ADDRESS_RX, appliance_ip):
                raise PortMappingError('No valid physical port IP address found in XML for ' + logical_port_kind + ' Port ' + str(logical_port_number))
            physical_port_number = int(physical_port_number)
        except TypeError:
            raise PortMappingError('No valid physical port number or IP address found in XML for ' + logical_port_kind + ' Port ' + str(logical_port_number))
        self.pport = tac_common.PhysicalPort(physical_port_number, appliance_ip)


class PortMapping:
    def __init__(self, log):
        self.l2p = dict() # logical  -> physical
        self.p2l = dict() # physical -> logical
        self.log = log

    def load_global(self):
        pairs = []
        if os.path.exists(GLOBAL_PORTS_DIR):
            pairs = self.load_dir(GLOBAL_PORTS_DIR)

        if not len(pairs):
            raise PortMappingError('No global port configuration files found in \'%s\'' % GLOBAL_PORTS_DIR)

        for (lport, pport) in pairs:
            if lport in self.l2p:
                raise PortMappingError('%s mapped to more than one physical port' % str(lport))
            else:
                self.l2p[lport] = pport

            if pport in self.p2l:
                raise PortMappingError('%s mapped to more than one logical port' % str(pport))
            else:
                self.p2l[pport] = lport

    def load_dir(self, dir):
        """Return a list of not empty (lport, pport) pairs from port configuration files found in dir."""
        port_files = tac_common.get_files(dir, PORT_MAPPING_FILE_RX)
        pairs = [self.load_file(file) for file in port_files]
        return filter(None, pairs)

    def load_file(self, file):
        """Parse logical port configuration file and return pair (lport, pport)."""
        tree =  ET.parse(file)
        root = tree.getroot()

        # todo: [spashaev] check port type '<Data type="ClientPort" version="2">'

        physical_ports = root.findall('./Data/Port')
        if len(physical_ports) > 1:
            raise PortMappingError('More than one physical port specified in port file: %s' % file)

        if physical_ports[0].text is None:
            self.log.warning('Empty port in configuration file: %s' % file)
            return None

        try:
            physical_port_num = int(physical_ports[0].text)
            # todo: validate port number
        except ValueError:
            self.log.warning('Invalid port value: "%s" in file: %s' % (physical_ports[0].text, file))
            return None

        appliances = root.findall('./Data/Appliance')
        if len(appliances) > 1:
            raise PortMappingError('More than one appliance specified in port file: %s' % file)

        if appliances[0].text is None:
            self.log.warning('Empty appliance in configuration file: %s' % file)
            return None

        appliance_ip = appliances[0].text
        # todo: validate ip address

        pport = tac_common.PhysicalPort(physical_port_num, appliance_ip)

        match = re.match(PORT_MAPPING_FILE_RX, os.path.basename(file))
        if not match:
            raise PortMappingError('Bad port filename: %s' % file)

        logical_port_num = int(match.group(2))
        kind = match.group(3)

        lport = tac_common.LogicalPort(logical_port_num, kind)

        self.log.verbose('Loaded %s' % file)
        return (lport, pport)

    def load_from_automation_config(self, xml_path):
        """Parse automation config xml_path and update mapping."""
        self.p2l.clear()
        self.l2p.clear()
        tree = ET.parse(xml_path)
        root = tree.getroot()
        client_ports = root.findall('./ClientPortConfig')
        server_ports = root.findall('./ServerPortConfig')
        for cp in client_ports:
            cport = Port(self.log, cp)
            self.p2l[cport.pport] = cport.lport
            self.l2p[cport.lport] = cport.pport
        for sp in server_ports:
            sport = Port(self.log, sp)
            self.p2l[sport.pport] = sport.lport
            self.l2p[sport.lport] = sport.pport


#
# Error classes for LdxProject
#
class ProjectFileError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class ProjectRunError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


# ===============================================-------------------=============================================== #
# =============================================== CLASS  LdxProject =============================================== #
# ===============================================-------------------=============================================== #


class LdxProject(object):
    def __init__(self, project_dir, params, log):
        self.project_dir = project_dir
        self.params = params
        self.log = log
        self.project = None
        self.name = ''
        self.results_dir = ''
        self.mapping = None
        self.xml_path = os.path.join(self.project_dir, 'AutomationConfig', 'AutomationConfig.xml')
        self.LDXCMD_BIN = ""

        # If AutomationConfig does not exist or if the find_cfg argument is not set -
        if not self.converted() or not self.params.find_cfg:
            # then don't convert again, just make a new results folder
            # otherwise - convert the project and find the results directory that has been created during conversion
            self.convert()
            self.get_last_results_dir()

    def load(self):
        self.start_time = ("{}_{}_{} {}-{}-{} {}").format(
            time.strftime('%m').lstrip("0"),
            time.strftime('%d').lstrip("0"),
            time.strftime('%Y'),
            time.strftime('%I').lstrip("0"),
            time.strftime('%M'),
            time.strftime('%S'),
            time.strftime('%p'))
        if self.params.simulate:
            self.log.info('Simulation mode: using the latest results folder.')
            if not self.get_last_results_dir():
                return False
        else:
            if not self.params.simulate:
                self.make_results_dir()

        self.load_automation_config()
        self.name = self.project.name
        self.mapping = PortMapping(self.log)
        return True

    def converted(self):
        if not os.path.exists(self.xml_path):
            return False
        return True

    def duration(self):
        """Parse automation config file and get test duration time."""
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        load_profiles = root.findall('./ClientScenarioConfig/Loads')
        test_duration = 0
        for lp in load_profiles:
            loads = lp.findall('Load')
            load_profile_duration = 0
            for load in loads:
                load_profile_duration += int(load.find('Duration').text)
            if load_profile_duration > test_duration:
                test_duration = load_profile_duration
        return test_duration

    def find_ldxcmd(self):
        if sys.platform.startswith("win"):
            # Read from SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall
            # Setting security access mode. KEY_WOW64_64KEY is used for 64-bit TDE
            sam = _winreg.KEY_READ | _winreg.KEY_WOW64_64KEY
            reg_key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0,
                                      sam)
            latest_version = ""
            latest_build = 0
            path_to_latest_build = ""
            # iterate through all subkeys of \Uninstall
            for i in xrange(0, _winreg.QueryInfoKey(reg_key)[0]):
                try:
                    subkey = _winreg.EnumKey(reg_key, i)
                    if re.match(WINDOWS_GUID_RX, subkey):
                        tde_key = _winreg.OpenKey(reg_key, subkey)
                        display_name = str(_winreg.QueryValueEx(tde_key, "DisplayName")[0])
                        if display_name.startswith("Load DynamiX TDE"):
                            display_version = str(_winreg.QueryValueEx(tde_key, "DisplayVersion")[0])
                            match = re.match("(\d+).(\d+).(\d+)", display_version)
                            if match:
                                tde_build = int(match.group(3))
                                if tde_build > latest_build:
                                    path_to_build = str(_winreg.QueryValueEx(tde_key, "InstallLocation")[0])
                                    path_to_build = os.path.join(path_to_build, "LdxCmd.exe")
                                    if os.path.exists(path_to_build):
                                        latest_version = display_version
                                        latest_build = tde_build
                                        path_to_latest_build = path_to_build
                except EnvironmentError:
                    break
            if latest_build > 0:
                self.log.verbose("The latest LdxCmd version found: " + latest_version)
                self.LDXCMD_BIN = path_to_latest_build
            else:
                raise ProjectFileError('LdxCmd.exe not found.')
        else:
            self.LDXCMD_BIN = "/opt/swifttest/resources/dotnet/LdxCmd"
            if not os.path.exists(self.LDXCMD_BIN):
                raise ProjectFileError('LdxCmd executable not found: ' + self.LDXCMD_BIN)


    def convert(self):
        """Convert TDE project to AutomationConfig."""
        project_files = tac_common.get_files(self.project_dir, SWIFTTEST_PROJECT_FILE_RX)
        if len(project_files) > 1:
            raise ProjectFileError('More than one .swift_test file found in dir: %s' % self.project_dir)
        if len(project_files) == 0:
            raise ProjectFileError('No .swift_test file found in dir: %s' % self.project_dir)
        project_file = project_files[0]
        self.find_ldxcmd()
        self.log.verbose('Converting project to AutomationConfig: %s' % project_file)
        p = subprocess.Popen([self.LDXCMD_BIN,
                              '--generate', '--project:' + project_file,
                              '--upgrade',
                              '--Force'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, err = p.communicate()
        if p.returncode:
            self.log.error(output)
            raise ProjectFileError('An error occured during conversion.')
        else:
            self.log.verbose(output)
        self.log.verbose('.swift_test project to AutomationConfig converting finished.')
        if not self.converted():
            raise ProjectFileError('Failed to convert project to AutomationConfig.xml: %s' % self.project_dir)

    def load_automation_config(self):
        """Create swifttest.Project instance from AutomationConfig file."""
        self.log.verbose('Loading %s' % self.xml_path)
        if self.xml_path.endswith('.xml'):
            self.project = swifttest.Project(name='Project', config=self.xml_path)
        elif self.xml_path.endswith('.py'):
            module = imp.load_source('test_module', self.xml_path)
            self.project = module.myProject()
        else:
            raise ProjectRunError('Project file %s is neither XML configuration nor Python module.' % self.xml_path)
        if not self.project:
            raise ProjectRunError('Unable to load the project.')
        self.log.verbose('Loaded successfully.')

    def assign_ports(self):
        """Modify swifttest.Project instance according to port mapping. Maps
        defined project-wide or system-wide logical ports to physical."""
        # separate logical ports by kind
        client_ports = dict()
        server_ports = dict()
        for lport, pport in self.mapping.l2p.iteritems():
            if lport.kind == 'client':
                if not client_ports.get(lport):
                    client_ports[lport] = pport
                else:
                    raise PortMappingError('Duplicated logical port definition: %s' % str(lport))
            elif lport.kind == 'server':
                if not server_ports.get(lport):
                    server_ports[lport] = pport
                else:
                    raise PortMappingError('Duplicated logical port definition: %s' % str(lport))
            else:
                raise PortMappingError('Unknown logical port kind: %s' % str(lport))

        try:
            for port in self.project.project:
                if len(port.getappliance()) == 0:
                    pport = tac_common.PhysicalPort(port.getportnum(), port.getappliance())
                    raise PortMappingError('Bad port configuration: ' + str(pport))
                    # if port.getkind() == swifttest.Port.CLIENT:
                    #     lport, pport = client_ports.popitem()
                    #     port.setportnum(pport.number)
                    #     port.setappliance(pport.appliance_ip)

                    # elif port.getkind() == swifttest.Port.SERVER:
                    #     lport, pport = server_ports.popitem()
                    #     port.setportnum(pport.number)
                    #     port.setappliance(pport.appliance_ip)
                    # else:
                    #     raise PortMappingError('Unknown logical port kind in AutomationConfig: %s' + str(port))
        except KeyError:
            raise PortMappingError('Port mismatch. Project is using more logical ports than mapped')

    def run(self):
        """Run test project and return True if passed, false - otherwise"""
        self.log.info('Running "%s"' % self.name)
        test_duration = datetime.timedelta(seconds=self.duration() / 1000)
        test_finish_time = datetime.datetime.now() + test_duration
        self.log.info('Test duration: %s' % test_duration)
        self.log.info('Estim. finish: %s' % test_finish_time.strftime("%H:%M:%S %d.%m.%y"))
        try:
            # update port mapping from automation config
            if self.converted:
                self.mapping.load_from_automation_config(self.xml_path)
            else:
                # load port mapping from system-wide port configuration files in GLOBAL_PORTS_DIR
                self.mapping.load_global()
                self.assign_ports()
                # output of ports used in the project
            for p in self.project.portlist:
                self.log.verbose(self.get_logical_port(p) + " - " + self.get_physical_port(p))
        except ProjectFileError as e:
            self.log.error(str(e))
            return False
        except PortMappingError as e:
            self.log.error(str(e))
            return False
        except tac_assertions.AssertionsError as e:
            self.log.error(str(e))
            return False
        except Exception as e:
            self.log.error('Unexpected error while preparing "%s": %s' % (self.project_dir, str(e)))
            return False

        if self.params.simulate:
            self.log.info('Simulation mode: skipping project run.')
        else:
            if self.params.stop_ports:
                self.stop_ports()

            self.wait_for_state('idle', 10)
            if not self.project.prepare():
                logger = self.project.get_logger()
                messages = logger.each_error()
                error_message = messages.next()
                while error_message is not None:
                    print "%s\n" % error_message.text,
                    error_message = messages.next()
                raise ProjectRunError('Project preparing failed.')
            self.log.verbose('Project prepared.')

            if not self.project.run():
                raise ProjectRunError('Unable to run the test project.')
            self.wait_for_state('running', 30)
            self.log.verbose('Running the project...')

            self.wait_for_state('idle')
            self.stop_ports()
        return True

    def check(self):
        if self.params.simulate:
            self.log.info('Simulation mode: skipping results download and using the latest results directory.')
        else:
            if not self.check_logs():
                return False
            if not self.download_results():
                return False
        if not self.check_assertions():
            return False
        return True

    def check_assertions(self):
        try:
            assertions = tac_assertions.Assertions(self, self.log)
            assertions.load_summaries()
            passed = assertions.passed()
        except tac_assertions.AssertionsError as e:
            self.log.error(str(e))
            return False
        return passed

    def check_log(self, log):
        passed = True
        with open(log, 'r') as file:
            num = 0
            for line in file:
                num += 1
                if line.startswith('<3>') or line.startswith('<4>'):
                    self.log.error(os.path.basename(log) + ':' + str(num) + ':' + line[:-1])
                    passed = False
        return passed

    def check_logs(self):
        """Save logs for project in results_dir."""
        for port in self.project:
            pport = tac_common.PhysicalPort(port.getportnum(), port.getappliance())
            lport = self.mapping.p2l[pport]
            name = ''
            if lport.kind == 'client':
                name += 'Client Port '
            else:
                name += 'Server Port '
            name += str(lport.number) + '(' + pport.appliance_ip + ' port ' + str(pport.number) + ')'

            fpath = os.path.join(self.results_dir, name + '.log')
            if not swifttest.get_log(pport.appliance_ip, pport.number, fpath):
                self.log.error(
                    '%s download failed from %s:%s port' % (os.path.basename(fpath), pport.appliance_ip, pport.number))
                return False
            self.log.verbose('%s downloaded.' % os.path.basename(fpath))
            if not self.check_log(fpath):
                return False
        return True

    def download_results(self):
        """Save results for project in results_dir."""
        for port in self.project:
            pport = tac_common.PhysicalPort(port.getportnum(), port.getappliance())
            lport = self.mapping.p2l[pport]
            name = ''
            if lport.kind == 'client':
                name += 'Client Port '
            else:
                name += 'Server Port '
            name += str(lport.number) + '(' + pport.appliance_ip + ' port ' + str(pport.number) + ')'

            fpath = os.path.join(self.results_dir, name)
            summary = fpath + '.sum'
            if not swifttest.get_summary(pport.appliance_ip, pport.number, summary):
                self.log.error('%s download failed from %s:%s port' % (
                os.path.basename(summary), pport.appliance_ip, pport.number))
                return False
            self.log.verbose('%s downloaded.' % os.path.basename(summary))
            pcap = fpath + '.pcap'
            if swifttest.get_pcap(pport.appliance_ip, pport.number, pcap):
                self.log.verbose('%s downloaded.' % os.path.basename(pcap))
            try:
                tmp_dir = tempfile.mkdtemp()
                dv_logs = swifttest.get_verification_logs(pport.appliance_ip, pport.number, tmp_dir)
                if dv_logs:
                    dv_dir = fpath + ' Data Verification logs'
                    os.makedirs(dv_dir)
                    for log in dv_logs:
                        os.rename(log, os.path.join(dv_dir, os.path.basename(log)))
                        self.log.verbose('%s downloaded.' % os.path.basename(log))
                os.rmdir(tmp_dir)
            except Exception as e:
                self.log.warning('Cannot create result directory: ' + str(e))
        return True

    @staticmethod
    def get_logical_port(port):
        if port.kind == port.CLIENT:
            port_kind = 'Client port '
        elif port.kind == port.SERVER:
            port_kind = 'Server port '
        logical_port = port_kind + str(port.port._internal__id % 1000)
        return logical_port

    @staticmethod
    def get_physical_port(port):
        physical_port = str(port.appliance) + ":" + str(port.portnum)
        return physical_port

    def get_last_results_dir(self):
        """ Find last Results directory for the project."""
        last_result_dir = ""
        last_result_time = 0
        results_path = os.path.join(self.project_dir, 'Results')
        for name in os.listdir(results_path):
            if os.path.isdir(os.path.join(results_path, name)):
                try:
                    t = time.mktime(time.strptime(name, '%m_%d_%Y %H-%M-%S %p'))
                    if t > last_result_time:
                        results_dir = os.path.join(self.project_dir, 'Results', name)
                        if self.params.simulate:
                            if tac_common.get_files(results_dir, tac_assertions.SUMMARY_FILE_RX):
                                last_result_time = t
                                last_result_dir = results_dir
                        else:
                            last_result_time = t
                            last_result_dir = results_dir
                except ValueError:
                    continue
        if last_result_dir:
            self.results_dir = last_result_dir
            return True
        else:
            self.log.warning ('Cannot find result directory.')
            return False

    def make_results_dir(self):
        """Create results dir for current test run and return path to it."""
        self.results_dir = os.path.join(self.project_dir, 'Results', self.start_time)
        try:
            os.makedirs(self.results_dir)
        except Exception as e:
            raise ProjectRunError('Cannot create result directory: ' + str(e))

    def ports_in_state(self, state):
        """Return True if all ports of project in demanded state, False - otherwise."""
        for port in self.project:
            ip = port.getappliance()
            num = port.getportnum()
            try:
                pstate = swifttest.get_port_status(ip, num).get('state')
            except swifttest.SwiftTestException as e:
                sys.exit('Failed to get port status from appliance %s:%s (%s)' % (
                ip, num, str(e)))  # todo: pass exception to calling function instead
            if pstate != state:
                return False

        return True

    def wait_for_state(self, state, timeout=0):
        """Wait with timeout until all ports of project in demanded state."""
        waited = 0
        while not self.ports_in_state(state):
            time.sleep(WAIT_INTERVAL)
            waited += 1
            if timeout > 0 and waited > timeout:
                sys.exit('Ports are not in \'%s\' state for %d seconds' % (
                state, timeout))  # todo: pass exception to calling function instead

    def stop_ports(self):
        """Stop all ports in project."""
        for port in self.project:
            state = None
            ip = port.getappliance()
            num = port.getportnum()
            try:
                state = swifttest.get_port_status(ip, num).get('state')
            except swifttest.SwiftTestException as e:
                sys.exit('Failed to get port status from appliance %s:%s (%s)' % (
                ip, num, str(e)))  # todo: pass exception to calling function instead
            if state == 'idle':
                self.log.verbose('Port %s:%s is idle' % (ip, num))
            else:
                swifttest.stop_port(ip, num)
                swifttest.wait_until_port_idle(ip, num, WAIT_INTERVAL)
                self.log.verbose('Port %s:%s has stopped' % (ip, num))

## ============================================--------------------------============================================ ##
## ============================================ END OF CLASS  LdxProject ============================================ ##
## ============================================--------------------------============================================ ##
