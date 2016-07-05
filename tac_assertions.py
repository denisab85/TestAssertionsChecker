import datetime
import os
import re
import collections

import swifttest

import tac_common
import tac_calculation

#
# Regexps
#
SUMMARY_FILE_RX = '([Cc]lient|[Ss]erver)\s+[Pp]ort\s+([0-9]+)\s*\(([0-9.]+) [Pp]ort ([0-9]+)\).sum(mary)?'
ASSERTION_FILE_RX = '.*\.assertions$'
RULE_RX = 'ANY|ANY_EXCEPT_LAST|LAST|SPAN\[\d+:\d+\]'
COUNTER_RX = "(((([cs])port)(\d+)?).)?([a-zA-Z0-9._]+)$"

#
# Constants
#
DEFAULT_ASSERTIONS_FILE = os.path.join(os.path.expanduser('~'), '.tac', 'default.assertions')
INTEGRITY_ASSERTIONS_FILE = os.path.join(os.path.expanduser('~'), '.tac', 'integrity.assertions')
CONSTANTS = {'const_name': 0}
OPERATORS = {'!', '*', '/', '%', '+', '-', '<', '<=', '>', '>=', '==', '!=', '&', '|', '(', ')', '@'}
MODIFIERS = {'sec':2, 'min':120}
Token = collections.namedtuple('Token', ['name', 'value', 'modifier'])


#
#  Assertion files
#
class AssertionsError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Assertion:
    def __init__(self, expr, source_file, num, log):
        self.source_file = source_file
        self.active = True
        self.ignored = False
        self.log = log
        self.vars = dict()
        self.expr = expr
        self.tokens = []
        self.tokenize()
        self.calc = tac_calculation.Calculator(self.tokens)  # for native Python
        # self.calc = tac_calculation_c.Calculator()    # for c++ over Python wrapper

        self.make_vars()

    # def __eq__(self, other):
    #     return isinstance(other, self.__class__) and self.__dict__ == other.__dict__
    #
    # def __ne__(self, other):
    #     return not self.__eq__(other)

    def __str__(self):
        return '{' + os.path.abspath(self.source_file) + ', ' + self.assertion_line(0) + '}'

    def __hash__(self):
        return hash(os.path.abspath(self.source_file) + self.assertion_line(0))

    @staticmethod
    def split_expr(expr):
        for const in CONSTANTS.keys():
            expr = expr.replace(const, ' ' + const + ' ')
        for lit in MODIFIERS.keys():
            expr = expr.replace('@' + lit, ' @' + lit + ' ')
        for op in OPERATORS:
            expr = expr.replace(op, ' ' + op + ' ')
        expr = expr.replace('> =', '>=')
        expr = expr.replace('< =', '<=')
        expr = expr.replace('= =', '==')
        return (' '.join(expr.split())).split()

    def tokenize(self):
        nport = 0
        port_types = set()
        split_expr = self.split_expr(self.expr)
        for word in split_expr:
            # check for constant
            if word in CONSTANTS.keys():
                self.tokens.append(Token('num', CONSTANTS[word]))
                continue
            # check for modifiers like 'sec' or 'min'
            elif len(self.tokens) and self.tokens[-1].name == '@':
                self.tokens.pop()
                if word in MODIFIERS.keys():
                    last_token = self.tokens.pop()
                    modified_token = Token(last_token[0], last_token[1], word)
                    self.tokens.append(modified_token)
                else:
                    raise AssertionsError('Incorrect modifier \'{}\': {}'.format(word, self.expr))
                continue
            # check for operator
            elif word in OPERATORS:
                self.tokens.append(Token(word, word, None))
                continue
            # check for rule prefixis like 'ANY', 'LAST', 'SPAN', etc.
            match = re.match(RULE_RX, word)
            if match:
                rule = match.group(0)
                match = re.match('SPAN\[(\d+):(\d+)\]', rule)
                if match:
                    start = int(match.group(1))
                    end = int(match.group(2))
                    if end >= start:
                        self.tokens.append(Token('rule', rule, None))
                    else:
                        raise AssertionsError('Incorrect time span values: {}'.format(self.expr))
                else:
                    self.tokens.append(Token('rule', rule, None))
                continue
            # check for a number
            match = re.match('\d+[.]\d+|\d+', word)
            if match:
                self.tokens.append(Token('num', float(word), None))
                continue
            # check for port prefix
            match = re.match(COUNTER_RX, word)
            if match:
                port = match.group(2)
                if not port:
                    nport += 1
                else:
                    port_types.add(port)
                self.tokens.append(Token('var', word, None))
                continue
            else:
                err_msg = 'Syntax error, unknown token \'{}\' in expression: {}'.format (word, self.expr)
                raise AssertionsError(err_msg)
        # check tokens
        if len(self.tokens) == 0:
            raise AssertionsError('Bad syntax in expression: ' + self.expr)

        # first token should be the type of rule
        if self.tokens[0].name != 'rule' or not re.match (RULE_RX, self.tokens[0].value):
            raise AssertionsError('Bad rule prefix in expression: ' + self.expr)


        # if sevral ports are used in expression
        self.multiport = bool(len(port_types) > 1)
        # if self.multiport and nport:

        # the first token is the rule prefix
        self.rule_prefix = self.tokens[0].value

        # save all but the first token for calculations
        self.tokens = self.tokens[1:]

    def make_vars(self):
        # names : variable_name -> (LogicalPort, stat_name)
        token_num = -1
        for token in self.tokens:
            token_num += 1
            if token.name == 'var':
                match = re.match(COUNTER_RX, token.value)
                if match:
                    port = match.group(3)
                    port_num = match.group(5)
                    stat_name = match.group(6)

                    # if name is wildcarded (without [cs]port[0-9]+ prefix) set port to None
                    if port_num is None and port is None:
                        variable = (None, stat_name, token.modifier)
                    else:
                        if port == 'cport':
                            port = 'client'
                        elif port == 'sport':
                            port = 'server'
                        else:
                            raise AssertionsError('Bad logical port prefix in variable name: %s' % token.value)
                        if port_num:
                            variable = (tac_common.LogicalPort(int(port_num), port), stat_name, token.modifier)
                        else:
                            variable = (tac_common.LogicalPort(None, port), stat_name, token.modifier)
                    self.vars[token.value] = variable
                else:
                    raise AssertionsError('Bad variable name: %s' % token.value)

                    # todo: [spashaev] add check about last rule type
    @staticmethod
    def get_value(summaries, tick, pport, stat_name, modifier):
        sample = summaries[tick]
        try:
            value = sample[pport].get(stat_name, 0.0)
        except KeyError:
            raise AssertionsError(("Value '{0}' not found for {1}. Check port configuration.").format(stat_name, pport))
        if modifier:
            mod_value = MODIFIERS.get(modifier)
            if tick < mod_value:
                value = value / (tick + 1) * mod_value
            else:
                relevant_sample = summaries[tick - mod_value]
                value = value - relevant_sample[pport].get(stat_name, 0.0)
        return value

    def get_values(self, project, summaries, tick):
        """Expand this Assertion wildcarded variables into list of dicts with values from the sample."""
        self.values = {}
        variables_to_expand_port = []
        variables_to_expand_port_number = []
        variables_variant = {}
        for name, (lport, stat_name, modifier) in self.vars.iteritems():
            if lport is None:
                variables_to_expand_port.append((name, modifier))
            elif lport.number is None:
                variables_to_expand_port_number.append((name, modifier))
            else:
                pport = project.mapping.l2p.get(lport, None)
                # if logical port doesn't correspond to any physical port of the project - ignore this assertion
                if pport is None:
                    self.ignored = True # make assertion ignored
                    self.log.info('"' + project.project.name() + '" ' + os.path.basename(self.source_file) + ' ' + self.assertion_with_port(0, str(lport)) + ' ignored')
                    return
                else:
                    value = self.get_value(summaries, tick, pport, stat_name, modifier)
                    variables_variant[name] = value
                    self.values[lport] = variables_variant
        if variables_to_expand_port or variables_to_expand_port_number:
            for port in project.project:
                pport = tac_common.PhysicalPort(port.getportnum(), port.getappliance())
                lport = project.mapping.p2l.get(pport, None)
                if lport is None:
                    self.log.warning("No logical port found for %s" % pport)
                # derive variables set and extend it with values from
                # current physical port
                changed = False
                # for variables in which port is not specified, get values from any port in sample
                for name, modifier in variables_to_expand_port:
                    stat_name = self.vars[name][1]
                    value = self.get_value(summaries, tick, pport, stat_name, modifier)
                    variables_variant[name] = value
                    changed = True
                # for variables in which port kind is specified, get values from sample only for this port kind
                for name, modifier in variables_to_expand_port_number:
                    var_lport = self.vars[name][0]
                    stat_name = self.vars[name][1]
                    if var_lport.kind == lport.kind:
                        value = self.get_value(summaries, tick, pport, stat_name, modifier)
                        variables_variant[name] = value
                        changed = True
                if changed:
                    self.values[lport] = variables_variant

    def check(self, project, summaries):
        # If the rule is related to multiple samples - then loop through all samples one by one
        #print ("checking rule: " + self.expr)
        passed = True
        if self.rule_prefix in ('ANY', 'ANY_EXCEPT_LAST') or self.rule_prefix.startswith('SPAN['):
            fin = len(summaries)
            if self.rule_prefix == 'ANY_EXCEPT_LAST':
                fin -= 1
            tick = 0
            while passed and tick < fin:
                sec = (tick + 1) / 2
                self.get_values(project, summaries, tick)

                result = self.calc.calculate(self.values, self.multiport)
                res = bool(int(result[0]))
                msg = result[1]
                if self.rule_prefix in ('ANY', 'ANY_EXCEPT_LAST'):
                    passed = bool(res)
                elif self.rule_prefix.startswith('SPAN['):
                    match = re.match('SPAN\[(\d+):(\d+)\]', self.rule_prefix)
                    if match:
                        start = int(match.group(1))
                        end = int(match.group(2))
                        if start <= sec <= end:
                            passed = bool(res)
                        else:
                            passed = True
                tick += 1

        # If the rule is related to the last sample
        if self.rule_prefix in ('LAST', 'ANY_EXCEPT_LAST'):
            # get the last sample values stored in the [0] item of summaries
            sec = len(summaries) / 2
            self.get_values(project, summaries, 0)
            res = self.calc.calculate(self.values, self.multiport)
            # res = result[0]
            msg = 'result[1]'
            if self.rule_prefix == 'LAST':
                passed = bool(res)
            elif self.rule_prefix == 'ANY_EXCEPT_LAST':
                passed = not bool(res)

        time_stamp = str(datetime.timedelta(seconds=sec))
        if not passed:
            self.log.info\
                (time_stamp + ' Assertion failed (\'' + self.expr + '\' in ' + os.path.basename(self.source_file) + '): ' + msg)
        # if the assertion has failed - mark it as inactive, and it will not be used in future checks
        self.active = passed

    def assertion_line(self, tick):
        s = str(datetime.timedelta(seconds=tick/2)) + ' ' + self.rule_prefix + ' '
        for token in self.tokens:
            s += str(token.value) + ' '
        return s

    def assertion_with_port(self, tick, port):
        s = self.assertion_line(tick) + 'with non-configured ' + str(port)
        return s


class Assertions:
    def __init__(self, project, log):
        self.project = project
        self.log = log
        self.assertions = []
        self.load_assertions()
        self.summary_files = list()
        self.counters = set()
        self.summaries = list()

    def load_assertions(self):
        """Return list of Assertion records for project_dir."""
        # load project-wide assertions
        files = tac_common.get_files(self.project.project_dir, ASSERTION_FILE_RX)

        # use default assertions if there are no project-wide
        if len(files) == 0:
            if os.path.exists(DEFAULT_ASSERTIONS_FILE):
                files.append(DEFAULT_ASSERTIONS_FILE)

        # prepend integrity assertions assertion_file
        if os.path.exists(INTEGRITY_ASSERTIONS_FILE):
            files.insert(0, INTEGRITY_ASSERTIONS_FILE)

        if len(files) == 0:
            err_msg = 'No assertion files found in either of the following paths:\n'
            err_msg += '\t%s\n\t%s\n\t%s' % (
                os.path.join(self.project.project_dir, '*.assertions'), DEFAULT_ASSERTIONS_FILE,
                INTEGRITY_ASSERTIONS_FILE)
            raise AssertionsError(err_msg)
        self.log.verbose("Loading assertions...")
        self.log.verbose (files)
        for file_path in files:
            try:
                with open(file_path, 'r') as assertion_file:
                    num = 0
                    for expr in assertion_file:
                        num += 1
                        # ignore empty lines and comments
                        if expr in ['\n', '\r\n'] or not expr.strip() or expr[0] == '#':
                            continue
                           # remove trailing \n
                        expr = expr.rstrip('\n')
                        a = Assertion(expr, os.path.basename(file_path), num, self.log)
                        self.assertions.append(a)
                    self.log.verbose('Assertions loaded: ' + file_path)
            except Exception as e:
                self.log.error("Failed to load assertions file: " + file_path)
                raise AssertionsError(str(e))

    def get_counters(self):
        """ Check all statistic keys in assertions for validity, make a list of valid counters, make invalid assertions ignored. """
        # If no summary files found - raise exception
        if len(self.summary_files) == 0:
            raise AssertionsError('Summary files not found.')
        ignored_counters = set()
        ignore_assertions_count = 0
        summary = swifttest.Summary(self.summary_files[0])
        # test each summary counter for validity
        for a in self.assertions:
            a_ignored = False
            for name, (lport, stat_name, modifier) in a.vars.iteritems():
                test_cnt = set()
                match = re.match(COUNTER_RX, name)
                if match:
                    name = match.group(6)
                test_cnt.add(name)
                # test this counter
                # if counter is invalid - ignore the whole assertion expression
                if not swifttest.Stats.counter_exists(name):
                    a.ignored = True
                    a_ignored = True
                    ignored_counters.add(stat_name)
            if a_ignored:
                ignore_assertions_count += 1
        # output of ignored counters
        if len(ignored_counters):
            if ignore_assertions_count > 1:
                iac = "s"
            else:
                iac = ""
            if len(ignored_counters) > 1:
                msg = (" assertions with the following invalid counter{0} are ignored:").format(iac)
            else:
                msg = (" assertion with the following invalid counter{0} is ignored:").format(iac)
            self.log.error(
                str(ignore_assertions_count) + msg)
            i = 0
            for ic in ignored_counters:
                i += 1
                self.log.info("\t" + ic)
                if i > 10:
                    self.log.error("<...> Total " + str(len(ignored_counters)) + " items.")
                    break

    def load_summaries(self):
        """Make a map (physical_port -> summary generator) for stats."""
        # Make a unique list of statistics counters used in list of assertions
        self.summary_files = tac_common.get_files(self.project.results_dir, SUMMARY_FILE_RX)
        self.get_counters()

        self.log.info('Loading summary files...')

        # Make a list of dictionary generators from summary files using swifttest API
        # Include only needed counters
        generator = {}
        end = {}
        for sf in self.summary_files:
            self.log.verbose(sf)
            # Open summary file.
            summary = swifttest.Summary(sf)
            match = re.match(SUMMARY_FILE_RX, os.path.basename(sf))
            appliance_ip = match.group(3)
            port_number = int(match.group(4))
            pport = tac_common.PhysicalPort(port_number, appliance_ip)
            generator[pport] = summary.each_counters(self.counters)
        # Get all counter values from all generators that have not ended yet and put them into self.summaries dict
        while True:
            sample = {}
            for pport in generator:
                try:
                    sample[pport] = next(generator[pport])
                except StopIteration:
                    if not pport in end.keys():
                        end[pport] = self.summaries[-1][pport]
                    sample[pport] = {}
            if len(end) == len(generator):
                break
            self.summaries.append(sample)
        self.summaries.insert(0, end)

    def passed(self):
        """Print assertions summary report and return True if passed, false - otherwise."""
        self.log.verbose("Checking assertions...")
        n = 0
        for a in self.assertions:
            if a.active and not a.ignored:
                a.check(self.project, self.summaries)
        assertion_files = set()
        result = True
        for a in self.assertions:
            assertion_files.add(a.source_file)

        for f in assertion_files:
            passed = 0
            failed = 0
            ignored = 0
            for a in self.assertions:
                if f == a.source_file:
                    if a.ignored:
                        ignored += 1
                    elif a.active:
                        passed += 1
                    else:
                        failed += 1
            self.log.info("Statisctics for " + tac_common.Bcolors.BOLD + os.path.basename(f) + tac_common.Bcolors.ENDC + ":")
            total = passed + failed + ignored
            self.log.info('\tTotal:   ' + str(total))
            self.log.info('\tPassed:  ' + tac_common.Bcolors.OK + str(passed) + tac_common.Bcolors.ENDC)
            self.log.info('\tFailed:  ' + tac_common.Bcolors.FAIL + str(failed) + tac_common.Bcolors.ENDC)
            self.log.info('\tIgnored: ' + str(ignored))
            if failed > 0:
                result = False
        return result
