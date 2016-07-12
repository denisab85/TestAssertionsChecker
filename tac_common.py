import argparse
import collections
import logging
import os
import re
import sys
import json

#
# Constants
#
SWIFTTEST_PROJECT_FILE_EXT = ".swift_test"

#
# Common utils
#
LogicalPort = collections.namedtuple('LogicalPort', ['number', 'kind'])
PhysicalPort = collections.namedtuple('PhysicalPort', ['number', 'appliance_ip'])


def get_files(directory, pattern):
    """Return a list of file paths that match the given regex pattern inside the directory."""
    return [os.path.join(directory, f) for f in os.listdir(directory) if re.match(pattern, f) and not f.startswith('.')]


def is_project(path):
    for s in os.listdir(path):
        subitem = os.path.join(path, s)
        if os.path.isfile(subitem):
            ext = os.path.splitext(s)
            if ext[1] == SWIFTTEST_PROJECT_FILE_EXT:
                return True
    return False


def dig_tests(path, depth=256):
    """Look through the directory tree starting from 'path' to the given 'depth' and return a list of
    full paths to test projects found. [depth == 1: no search in subfolders; default: search to the depth of 256]"""
    if depth > 256:
        depth = 256
    elif depth < 0:
        depth = 0
    result = list()
    if is_project(path):
        result.append(path)
    else:
        if depth > 0:
            depth -= 1
            for si in os.listdir(path):
                sub_item = os.path.join(path, si)
                if os.path.isdir(sub_item):
                    result.extend(dig_tests(sub_item, depth))
    return result


class Arguments(object):
    verbose = False
    folders = []
    stop_ports = False
    find_cfg = False
    log_file = os.path.expanduser('~/.tac/tac.log')
    test_list = ""
    tests_by_type = dict()
    simulate = False
    depth = 256
    parser = argparse.ArgumentParser()

    def __init__(self):
        # get arguments
        # self.parser.add_argument('folders', nargs='*', type=str)
        self.parser.add_argument('-v', '--verbose', help='verbose mode', action='store_true')
        self.parser.add_argument('-s', '--stop_ports', help='stop ports before run', action='store_true')
        self.parser.add_argument('-f', '--find_cfg',
                            help='find AutomationConfig first, use convertion only if there is no config',
                            action='store_true')
        self.parser.add_argument('-l', '--log_file', help='custom path to log file')
        self.parser.add_argument('-t', '--test_list',
                            help='path to a file listing paths to tests',
                            type=argparse.FileType('r'))
        self.parser.add_argument('-m', '--simulate',
                            help='simulation mode (without connection to device)', action='store_true')
        self.parser.add_argument('-d', '--depth', help='depth of search for test projects in folders', type=int, default=256)
        self.parser.add_argument('-T', '--test_types',
                            help='types of tests',
                            nargs='+',
                            type = str)

        if len(sys.argv[1:]) == 0:
            self.parser.print_help()
            sys.exit(1)
        else:
            args = self.parser.parse_args()

        self.args = args
        self.parse_test_list()
        self.get_test_types()
        # self.expand_folders()
        self.stop_ports = bool(args.stop_ports)
        self.find_cfg = bool(args.find_cfg)
        if args.log_file:
            self.log_file = args.log_file
        self.test_list = args.test_list
        self.verbose = bool(args.verbose)
        self.simulate = bool(args.simulate)

    # def expand_folders(self):
    #     """Append test folders from 'folders' parameter or from file given as 'test_list' parameter"""
    #
    #     if self.args.folders:
    #         for path in self.args.folders:
    #             self.folders.extend(dig_tests(path, self.args.depth))

    def parse_test_list(self):
        """
        Parse JSON file from --test_list parameter and make a list of test paths for each test type
        """
        if self.args.test_list:
            with open(self.args.test_list.name) as json_file:
                data = json.load(json_file)
            for type in data:
                path_list = list()
                root_runs = 1
                path_runs = 1
                type_name = type['name']
                try:
                    type_runs = type['runs']
                except KeyError:
                    type_runs = 1
                print ("Parsing test type: {} [{}]".format(type_name, type.get('comment')))
                for test_root in type['roots']:
                    root_name = test_root["name"]
                    if os.path.exists(root_name):
                        try:
                            root_runs = test_root['runs']
                        except KeyError:
                            root_runs = 1
                        print ("\t{} [{}]".format(root_name, test_root.get('comment')))
                        for path in test_root['paths']:
                            path_name = path['name']
                            try:
                                path_runs = path['runs']
                            except KeyError:
                                path_runs = 1
                            if path_name == "*" :
                                path_list = []
                                for i in range(type_runs * root_runs * path_runs):
                                    path_list += dig_tests(root_name)
                            else:
                                full_path = os.path.join(root_name, path_name)
                                if os.path.exists(full_path):
                                    for i in range(type_runs*root_runs*path_runs):
                                        print ("\t\t" + path_name)
                                        path_list.append(full_path.encode('utf-8'))
                if self.tests_by_type.has_key(type_name):
                    self.tests_by_type[type_name] += path_list
                else:
                    self.tests_by_type.update({type_name: path_list})
                print ("{} test runs added.".format(len(path_list)))

    def get_test_types(self):
        """
        Return list of full paths to directories that contains specified types of tests.
        Ex.: functional tests only.
        """
        # Add test paths of specified types or all (if no type given)
        for test_type, path_list in self.tests_by_type.iteritems():
            if (self.args.test_types is None) or (test_type in self.args.test_types):
                self.folders.extend(path_list)


#
# Logging utils
#


class Bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OK = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ABORT = '\033[0;33m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class Logger(object):

    def __init__(self, log_file, verbose_mode):
        self.verbose_mode = verbose_mode
        log_dir = os.path.dirname(log_file)
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
        logging.basicConfig(filename=log_file, format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)

    def separator(self):
        self.info('-' * 90)

    def info(self, msg):
        print msg
        logging.info(msg)

    def verbose(self, msg):
        if self.verbose_mode:
            print msg
        logging.info(msg)

    def error(self, msg):
        print Bcolors.FAIL + msg + Bcolors.ENDC
        logging.error(msg)

    def warning(self, msg):
        if self.verbose_mode:
            print 'WARNING:', Bcolors.WARNING + msg + Bcolors.ENDC
        logging.warning(msg)
