#!/usr/bin/env python

import argparse
import collections
import itertools
import os
import swifttest

# Encoding back-to-back positive tests generator. This script saves to
# OUTPUT_DIR generated AutomationConfigs of positive encodings tests
# with specific assertions, which can be easily checked by tac.py, all
# tests should be passed.

#
# Parameters default values
#
APPLIANCE_IP = '192.168.10.32'
OUTPUT_DIR = 'generated_tests'
CLIENT_PORT = 0
SERVER_PORT = 1
VERBOSE = False

#
# Arguments parsing
#
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('appliance_ip', help='ip address of appliance')
    parser.add_argument('-o',  '--output_dir', help='dir to store generated tests')
    parser.add_argument('-cp', '--client_port', type=int, help='client port num')
    parser.add_argument('-sp', '--server_port', type=int, help='server port num')
    parser.add_argument('-v',  '--verbose', help='verbose mode', action='store_true')
    return parser.parse_args()

def print_args():
    print 'appliance ip: ' + APPLIANCE_IP
    print 'client port : ' + str(CLIENT_PORT)
    print 'server port : ' + str(SERVER_PORT)
    print 'output dir  : ' + OUTPUT_DIR
    print 'verbose     : ' + str(VERBOSE)

def analyze_args(args):
    global APPLIANCE_IP
    global CLIENT_PORT
    global SERVER_PORT
    global OUTPUT_DIR
    global VERBOSE

    if args.appliance_ip:
        APPLIANCE_IP = args.appliance_ip

    if args.client_port:
        CLIENT_PORT = args.client_port

    if args.server_port:
        SERVER_PORT = args.server_port

    if args.output_dir:
        OUTPUT_DIR = args.output_dir

    if args.verbose:
        VERBOSE = True
        print_args()


# test parameter name -> short mnemonic (for test name or else)

MAX_SCENARIOS = 3
TEST_NUM = 'num'
TEST_NAME_PREFIX = 'prefix'

ENTITY_DATA_LENGTH       = 'data'
CLIENT_CONTENT_MD5       = 'c_md5'
CLIENT_ACCEPT_ENCODING   = 'c_acc'
CLIENT_CONTENT_ENCODING  = 'c_ce'
CLIENT_TRANSFER_ENCODING = 'c_te'
CLIENT_EXPECT100         = 'c_expect'
SERVER_CONTENT_MD5       = 's_md5'
SERVER_FORCE_CHUNKED     = 's_chunked'

GET_AND_VERIFY = 'verify'

CE_IDENTITY = None
CE_GZIP     = 'gzip'
CE_DEFLATE  = 'deflate'

TE_NONE            = None
TE_CHUNKED         = '1'
TE_GZIP_CHUNKED    = '3'
TE_DEFLATE_CHUNKED = '5'

MB = pow(2, 20) # megabyte

class TestParams:
    def __init__(self):
        self.params = collections.OrderedDict()
        self.params[TEST_NAME_PREFIX]   = ['encodings_integrity']
        self.params[ENTITY_DATA_LENGTH] = [0, 1 , MB - 1, MB, MB + 1, 10*MB]

        self.params[CLIENT_CONTENT_MD5]       = [False]#, True] # since automation api is not supporting md5 counters yet - we disable them
        self.params[CLIENT_ACCEPT_ENCODING]   = [CE_IDENTITY, CE_GZIP]#, CE_DEFLATE] # deflate works nearly the same as gzip, so disable it to reduce size of test set
        self.params[CLIENT_CONTENT_ENCODING]  = [CE_IDENTITY, CE_GZIP]#, CE_DEFLATE]
        self.params[CLIENT_TRANSFER_ENCODING] = [TE_NONE, TE_CHUNKED, TE_GZIP_CHUNKED]#, TE_DEFLATE_CHUNKED]
        self.params[CLIENT_EXPECT100]         = [False]#, True] # check it when everything else is working

        self.params[SERVER_CONTENT_MD5]   = [False]#, True] # since automation api is not supporting md5 counters yet - we disable them
        self.params[SERVER_FORCE_CHUNKED] = [False, True]

        # True - PUT and GET scenario with data verifications checks
        # False - GET scenario without data verification
        self.params[GET_AND_VERIFY] = [True]

    def get_generator(self):
        return (collections.OrderedDict(itertools.izip(self.params, x)) for x in itertools.product(*self.params.itervalues()))

#
# Project definition
#
class TestProject:
    def __init__(self, variant):
        self.variant = variant
        self.project = self.create_project()

    def project_name(self):
        name = ''
        for k,v in self.variant.iteritems():
            if k != TEST_NUM and k != TEST_NAME_PREFIX:
                name += '_{0}_{1}'.format(str(k), str(v))
        return '{0}_{1}'.format(self.variant[TEST_NAME_PREFIX], str(self.variant[TEST_NUM]).zfill(5)) + name

    def get_config_dir_path(self):
        return os.path.join(OUTPUT_DIR, self.project_name(), 'AutomationConfig')

    def generate_automation_config(self):
        config_path = self.get_config_dir_path()
        if not os.path.exists(config_path):
            os.makedirs(config_path)
            xml = self.project.to_automation_xml(config_path)
            if VERBOSE and xml:
                print "AutomationConfig file saved to ", config_path
            self.generate_assertions()
        else:
            print config_path, ' already exist !!!'

    def generate_assertions(self):
        with open(os.path.join(OUTPUT_DIR, self.project_name(), 'encodings.assertions'), 'w') as f:
            s = '#==========================\n'
            s += '# this assertion file generated automatically special\n'
            s += '# for test case: ' + self.project_name() + '\n'
            s += '#==========================\n'
            s += '''
# default assertions
LAST load.actions.succeeds > 0
ANY load.actions.fails == 0
ANY load.actions.aborts == 0
LAST load.scenarios.succeeds > 0
ANY load.scenarios.fails == 0
ANY load.scenarios.aborts == 0
LAST load.connections.succeeds > 0
ANY load.connections.fails == 0
ANY load.connections.aborts == 0
ANY load.resultok.fails == 0
ANY load.resultok.aborts == 0

# catch fails and aborts
ANY httpenc.ce_total.fails == 0
ANY httpenc.ce_sent.fails == 0
ANY httpenc.ce_recv.fails == 0
ANY httpenc.ce_identity_total.fails == 0
ANY httpenc.ce_identity_sent.fails == 0
ANY httpenc.ce_identity_recv.fails == 0
ANY httpenc.ce_gzip_total.fails == 0
ANY httpenc.ce_gzip_sent.fails == 0
ANY httpenc.ce_gzip_recv.fails == 0
ANY httpenc.ce_deflate_total.fails == 0
ANY httpenc.ce_deflate_sent.fails == 0
ANY httpenc.ce_deflate_recv.fails == 0
ANY httpenc.te_total.fails == 0
ANY httpenc.te_sent.fails == 0
ANY httpenc.te_recv.fails == 0
ANY httpenc.te_chunked_total.fails == 0
ANY httpenc.te_chunked_sent.fails == 0
ANY httpenc.te_chunked_recv.fails == 0
ANY httpenc.te_gzip_total.fails == 0
ANY httpenc.te_gzip_sent.fails == 0
ANY httpenc.te_gzip_recv.fails == 0
ANY httpenc.te_deflate_total.fails == 0
ANY httpenc.te_deflate_sent.fails == 0
ANY httpenc.te_deflate_recv.fails == 0
ANY httpenc.ce_total.aborts == 0
ANY httpenc.ce_sent.aborts == 0
ANY httpenc.ce_recv.aborts == 0
ANY httpenc.ce_identity_total.aborts == 0
ANY httpenc.ce_identity_sent.aborts == 0
ANY httpenc.ce_identity_recv.aborts == 0
ANY httpenc.ce_gzip_total.aborts == 0
ANY httpenc.ce_gzip_sent.aborts == 0
ANY httpenc.ce_gzip_recv.aborts == 0
ANY httpenc.ce_deflate_total.aborts == 0
ANY httpenc.ce_deflate_sent.aborts == 0
ANY httpenc.ce_deflate_recv.aborts == 0
ANY httpenc.te_total.aborts == 0
ANY httpenc.te_sent.aborts == 0
ANY httpenc.te_recv.aborts == 0
ANY httpenc.te_chunked_total.aborts == 0
ANY httpenc.te_chunked_sent.aborts == 0
ANY httpenc.te_chunked_recv.aborts == 0
ANY httpenc.te_gzip_total.aborts == 0
ANY httpenc.te_gzip_sent.aborts == 0
ANY httpenc.te_gzip_recv.aborts == 0
ANY httpenc.te_deflate_total.aborts == 0
ANY httpenc.te_deflate_sent.aborts == 0
ANY httpenc.te_deflate_recv.aborts == 0

# all succeeds should be equal attempts
LAST httpenc.ce_total.succeeds == httpenc.ce_total.attempts
LAST httpenc.ce_sent.succeeds == httpenc.ce_sent.attempts
LAST httpenc.ce_recv.succeeds == httpenc.ce_recv.attempts
LAST httpenc.ce_identity_total.succeeds == httpenc.ce_identity_total.attempts
LAST httpenc.ce_identity_sent.succeeds == httpenc.ce_identity_sent.attempts
LAST httpenc.ce_identity_recv.succeeds == httpenc.ce_identity_recv.attempts
LAST httpenc.ce_gzip_total.succeeds == httpenc.ce_gzip_total.attempts
LAST httpenc.ce_gzip_sent.succeeds == httpenc.ce_gzip_sent.attempts
LAST httpenc.ce_gzip_recv.succeeds == httpenc.ce_gzip_recv.attempts
LAST httpenc.ce_deflate_total.succeeds == httpenc.ce_deflate_total.attempts
LAST httpenc.ce_deflate_sent.succeeds == httpenc.ce_deflate_sent.attempts
LAST httpenc.ce_deflate_recv.succeeds == httpenc.ce_deflate_recv.attempts
LAST httpenc.te_total.succeeds == httpenc.te_total.attempts
LAST httpenc.te_sent.succeeds == httpenc.te_sent.attempts
LAST httpenc.te_recv.succeeds == httpenc.te_recv.attempts
LAST httpenc.te_chunked_total.succeeds == httpenc.te_chunked_total.attempts
LAST httpenc.te_chunked_sent.succeeds == httpenc.te_chunked_sent.attempts
LAST httpenc.te_chunked_recv.succeeds == httpenc.te_chunked_recv.attempts
LAST httpenc.te_gzip_total.succeeds == httpenc.te_gzip_total.attempts
LAST httpenc.te_gzip_sent.succeeds == httpenc.te_gzip_sent.attempts
LAST httpenc.te_gzip_recv.succeeds == httpenc.te_gzip_recv.attempts
LAST httpenc.te_deflate_total.succeeds == httpenc.te_deflate_total.attempts
LAST httpenc.te_deflate_sent.succeeds == httpenc.te_deflate_sent.attempts
LAST httpenc.te_deflate_recv.succeeds == httpenc.te_deflate_recv.attempts

'''
            entity_length = self.variant[ENTITY_DATA_LENGTH]
            client_md5 = self.variant[CLIENT_CONTENT_MD5]
            client_ae = self.variant[CLIENT_ACCEPT_ENCODING]
            client_ce = self.variant[CLIENT_CONTENT_ENCODING]
            client_te = self.variant[CLIENT_TRANSFER_ENCODING]
            client_expect100 = self.variant[CLIENT_EXPECT100]
            server_md5 = self.variant[SERVER_CONTENT_MD5]
            server_chunked = self.variant[SERVER_FORCE_CHUNKED]
            verify = self.variant[GET_AND_VERIFY]

            PUT = 1
            GET = self.variant[GET_AND_VERIFY] + 0

            # k:input_bytes -> v:output_bytes
            identity = {0:0,  1:1,  MB-1:MB-1,   MB:MB,     MB+1:MB+1,   10*MB:10*MB}
            gzip     = {0:20, 1:21, MB-1:197754, MB:197755, MB+1:197755, 10*MB:1976727}
            deflate  = {0:2,  1:3,  MB-1:197736, MB:197737, MB+1:197737, 10*MB:1976709}
            chunked  = dict((bytes, chunked_bytes(bytes)) for bytes in [0, 1, MB-1, MB, MB+1, 10*MB])
            scenarios = MAX_SCENARIOS
            created_201 = 162 # bytes
            encoded = {'identity':identity, 'deflate':deflate, 'gzip': gzip, 'chunked':chunked}
            if client_ce is None:
                client_ce = 'identity'
            if client_ae is None:
                client_ae = 'identity'

            # remove this condition when 0 bytes entity verification is fixed
            if verify and entity_length > 0:
                s += '\n# http data verification'
                s += '\nANY http.verification.fails == 0'
                s += '\nANY http.verification.aborts == 0'
                s += '\nLAST cport.http.verification.attempts == ' + str(MAX_SCENARIOS)
                s += '\nLAST cport.http.verification.succeeds == ' + str(MAX_SCENARIOS)
                s += '\n'
            f.write(s)

            # following counters may be different for client and
            # server and should be calculated separately:
            #   httpenc.ce_sent.attempts
            #   httpenc.ce_sent_encoded.bytes
            #   httpenc.ce_sent_decoded.bytes
            #   httpenc.ce_identity_sent.attempts
            #   httpenc.ce_identity_sent_encoded.bytes
            #   httpenc.ce_identity_sent_decoded.bytes
            #   httpenc.ce_gzip_sent.attempts
            #   httpenc.ce_gzip_sent_encoded.bytes
            #   httpenc.ce_gzip_sent_decoded.bytes
            #   httpenc.ce_deflate_sent.attempts
            #   httpenc.ce_deflate_sent_encoded.bytes
            #   httpenc.ce_deflate_sent_decoded.bytes
            #   httpenc.te_sent.attempts
            #   httpenc.te_sent_encoded.bytes
            #   httpenc.te_sent_decoded.bytes
            #   httpenc.te_chunked_sent.attempts
            #   httpenc.te_chunked_sent_encoded.bytes
            #   httpenc.te_chunked_sent_decoded.bytes
            #   httpenc.te_gzip_sent.attempts
            #   httpenc.te_gzip_sent_encoded.bytes
            #   httpenc.te_gzip_sent_decoded.bytes
            #   httpenc.te_deflate_sent.attempts
            #   httpenc.te_deflate_sent_encoded.bytes
            #   httpenc.te_deflate_sent_decoded.bytes
            # then for each client.sent and server.sent counters we assume:
            # server.recv == client.sent and client.recv == server.sent

            # here and below we omit common prefix 'httpenc.' in
            # counter names for brevity, it will be added later,
            # before writing to file
            client = collections.OrderedDict()

            # common formula for encoding attempt is:
            #   scenarios * (PUT + GET)
            # common formula for sent bytes is:
            #   scenarios * (<bytes with PUT sent> + <bytes with GET sent>)
            if client_ce == 'identity':
                if entity_length > 0:
                    # no attempts for GET request
                    client['ce_identity_sent.attempts']      = scenarios * PUT
                    client['ce_identity_sent_decoded.bytes'] = scenarios * PUT * entity_length
                    client['ce_identity_sent_encoded.bytes'] = scenarios * PUT * encoded[client_ce][entity_length]
                else:
                    # https://swifttest.atlassian.net/browse/APPL-2404
                    client['ce_identity_sent.attempts']      = 0.0
                    client['ce_identity_sent_decoded.bytes'] = 0.0
                    client['ce_identity_sent_encoded.bytes'] = 0.0
                client['ce_gzip_sent.attempts']          = 0.0
                client['ce_gzip_sent_encoded.bytes']     = 0.0
                client['ce_gzip_sent_decoded.bytes']     = 0.0
                client['ce_deflate_sent.attempts']       = 0.0
                client['ce_deflate_sent_encoded.bytes']  = 0.0
                client['ce_deflate_sent_decoded.bytes']  = 0.0
            elif client_ce == 'gzip':
                client['ce_identity_sent.attempts']      = 0.0
                client['ce_identity_sent_decoded.bytes'] = 0.0
                client['ce_identity_sent_encoded.bytes'] = 0.0
                client['ce_gzip_sent.attempts']          = scenarios * PUT
                client['ce_gzip_sent_decoded.bytes']     = scenarios * PUT * entity_length
                client['ce_gzip_sent_encoded.bytes']     = scenarios * PUT * encoded[client_ce][entity_length]
                client['ce_deflate_sent.attempts']       = 0.0
                client['ce_deflate_sent_encoded.bytes']  = 0.0
                client['ce_deflate_sent_decoded.bytes']  = 0.0
            elif client_ce == 'deflate':
                client['ce_identity_sent.attempts']      = 0.0
                client['ce_identity_sent_decoded.bytes'] = 0.0
                client['ce_identity_sent_encoded.bytes'] = 0.0
                client['ce_gzip_sent.attempts']          = 0.0
                client['ce_gzip_sent_decoded.bytes']     = 0.0
                client['ce_gzip_sent_encoded.bytes']     = 0.0
                client['ce_deflate_sent.attempts']       = scenarios * PUT
                client['ce_deflate_sent_decoded.bytes']  = scenarios * PUT * entity_length
                client['ce_deflate_sent_encoded.bytes']  = scenarios * PUT * encoded[client_ce][entity_length]

            if client_te == TE_NONE and entity_length <= MB:
                client['te_chunked_sent.attempts']      = 0.0
                client['te_chunked_sent_decoded.bytes'] = 0.0
                client['te_chunked_sent_encoded.bytes'] = 0.0
                client['te_gzip_sent.attempts']         = 0.0
                client['te_gzip_sent_decoded.bytes']    = 0.0
                client['te_gzip_sent_encoded.bytes']    = 0.0
                client['te_deflate_sent.attempts']      = 0.0
                client['te_deflate_sent_decoded.bytes'] = 0.0
                client['te_deflate_sent_encoded.bytes'] = 0.0
            # chunked transfer encoding is enabled automatically if entity_length > MB and some compressing enabled
            elif (client_te == TE_CHUNKED or (client_te == TE_NONE and entity_length > MB and (client_ce == 'gzip' or client_ce == 'deflate'))):
                client['te_chunked_sent.attempts']      = scenarios * PUT
                client['te_chunked_sent_decoded.bytes'] = scenarios * PUT * encoded[client_ce][entity_length]
                client['te_chunked_sent_encoded.bytes'] = scenarios * PUT * chunked_bytes(encoded[client_ce][entity_length])
                client['te_gzip_sent.attempts']         = 0.0
                client['te_gzip_sent_decoded.bytes']    = 0.0
                client['te_gzip_sent_encoded.bytes']    = 0.0
                client['te_deflate_sent.attempts']      = 0.0
                client['te_deflate_sent_decoded.bytes'] = 0.0
                client['te_deflate_sent_encoded.bytes'] = 0.0
            elif client_te == TE_GZIP_CHUNKED:
                client['te_chunked_sent.attempts']      = scenarios * PUT
                # client['te_chunked_sent_decoded.bytes'] = ???
                # client['te_chunked_sent_encoded.bytes'] = ???
                client['te_gzip_sent.attempts']         = scenarios * PUT
                client['te_gzip_sent_decoded.bytes']    = scenarios * PUT * encoded[client_ce][entity_length]
                # client['te_gzip_sent_decoded.bytes']    = ???
                client['te_deflate_sent.attempts']      = 0.0
                client['te_deflate_sent_decoded.bytes'] = 0.0
                client['te_deflate_sent_encoded.bytes'] = 0.0
            elif client_te == TE_DEFLATE_CHUNKED:
                client['te_chunked_sent.attempts']      = scenarios * PUT
                # client['te_chunked_sent_decoded.bytes'] = ???
                # client['te_chunked_sent_encoded.bytes'] = ???
                client['te_gzip_sent.attempts']         = 0.0
                client['te_gzip_sent_decoded.bytes']    = 0.0
                client['te_gzip_sent_encoded.bytes']    = 0.0
                client['te_deflate_sent.attempts']      = scenarios * PUT
                client['te_deflate_sent_decoded.bytes'] = scenarios * PUT * encoded[client_ce][entity_length]
                # client['te_deflate_sent_encoded.bytes'] = ???

            server = collections.OrderedDict()

            # server processing client accept encoding only for GET
            # requests transfer encoding 'chunked' enabled on server
            # if server_chunked is True or when it is GET request and
            # ce == gzip|deflate and entity_length > 1MB

            # if file of entity_length more than MB is requested from
            # server, identity content encoding is enabled
            # automatically
            if entity_length > MB:
                client_ae = 'identity'

            if client_ae == 'identity':
                if entity_length > 0:
                    server['ce_identity_sent.attempts']      = scenarios * (PUT + GET)
                    server['ce_identity_sent_decoded.bytes'] = scenarios * (PUT * created_201 + GET * entity_length)
                    server['ce_identity_sent_encoded.bytes'] = scenarios * (PUT * created_201 + GET * entity_length)
                else:
                    server['ce_identity_sent.attempts']      = scenarios * (PUT)
                    server['ce_identity_sent_decoded.bytes'] = scenarios * (PUT * created_201)
                    server['ce_identity_sent_encoded.bytes'] = scenarios * (PUT * created_201)
                server['ce_gzip_sent.attempts']          = 0.0
                server['ce_gzip_sent_encoded.bytes']     = 0.0
                server['ce_gzip_sent_decoded.bytes']     = 0.0
                server['ce_deflate_sent.attempts']       = 0.0
                server['ce_deflate_sent_encoded.bytes']  = 0.0
                server['ce_deflate_sent_decoded.bytes']  = 0.0
            elif client_ae == 'gzip':
                server['ce_identity_sent.attempts']      = scenarios * (PUT)
                server['ce_identity_sent_decoded.bytes'] = scenarios * (PUT * created_201)
                server['ce_identity_sent_encoded.bytes'] = scenarios * (PUT * created_201)
                server['ce_gzip_sent.attempts']          = scenarios * (GET)
                server['ce_gzip_sent_decoded.bytes']     = scenarios * (GET * entity_length)
                server['ce_gzip_sent_encoded.bytes']     = scenarios * (GET * encoded[client_ae][entity_length])
                server['ce_deflate_sent.attempts']       = 0.0
                server['ce_deflate_sent_encoded.bytes']  = 0.0
                server['ce_deflate_sent_decoded.bytes']  = 0.0
            elif client_ae == 'deflate':
                server['ce_identity_sent.attempts']      = scenarios * (PUT)
                server['ce_identity_sent_decoded.bytes'] = scenarios * (PUT * created_201)
                server['ce_identity_sent_encoded.bytes'] = scenarios * (PUT * created_201)
                server['ce_gzip_sent.attempts']          = 0.0
                server['ce_gzip_sent_decoded.bytes']     = 0.0
                server['ce_gzip_sent_encoded.bytes']     = 0.0
                server['ce_deflate_sent.attempts']       = scenarios * (GET)
                server['ce_deflate_sent_decoded.bytes']  = scenarios * (GET * entity_length)
                server['ce_deflate_sent_encoded.bytes']  = scenarios * (GET * encoded[client_ae][entity_length])

            if server_chunked and verify:
                server['te_chunked_sent.attempts']      = scenarios * (GET)
                server['te_chunked_sent_decoded.bytes'] = scenarios * (GET * encoded[client_ae][entity_length])
                server['te_chunked_sent_encoded.bytes'] = scenarios * (GET * chunked_bytes(encoded[client_ae][entity_length]))
            else:
                server['te_chunked_sent.attempts']      = 0.0
                server['te_chunked_sent_decoded.bytes'] = 0.0
                server['te_chunked_sent_encoded.bytes'] = 0.0
            server['te_gzip_sent.attempts']         = 0.0
            server['te_gzip_sent_decoded.bytes']    = 0.0
            server['te_gzip_sent_encoded.bytes']    = 0.0
            server['te_deflate_sent.attempts']      = 0.0
            server['te_deflate_sent_decoded.bytes'] = 0.0
            server['te_deflate_sent_encoded.bytes'] = 0.0

            # here we implement out assumption that all that sent by
            # client is received by server and vice versa:
            # client.sent == server.recv
            for (k,v) in client.iteritems():
                if 'sent' in k:
                    server[k.replace('sent', 'recv')] = v

            # server.sent == client.recv
            for (k,v) in server.iteritems():
                if 'sent' in k:
                    client[k.replace('sent', 'recv')] = v

            # dump client and server assertions to file and add prefix for counters
            s = ''
            for (k,v) in client.iteritems():
                s += '\nLAST cport.httpenc.' + k + ' == ' + str(v)

            s += '\n'
            for (k,v) in server.iteritems():
                s += '\nLAST sport.httpenc.' + k + ' == ' + str(v)
            f.write(s)

    def create_project(self):
        project = swifttest.Project(self.project_name())
        project.add_port(self.client_port())
        project.add_port(self.server_port())
        return project

    def client_port(self):
        port = swifttest.Port(swifttest.Port.CLIENT)
        port.appliance = APPLIANCE_IP
        port.portnum = CLIENT_PORT
        trace = swifttest.TraceParameters(4*MB, 0)
        trace.set_max_packet_size(64)
        trace.set_max_packet_size_enabled(False)
        port.add_trace_parameters(trace)
        port.add_net(self.client_net())
        port.add_data_content(self.client_data_content())
        return port

    def server_port(self):
        port = swifttest.Port(swifttest.Port.SERVER)
        port.appliance = APPLIANCE_IP
        port.portnum = SERVER_PORT
        trace = swifttest.TraceParameters(4*MB, 0)
        trace.set_max_packet_size(64)
        trace.set_max_packet_size_enabled(False)
        port.add_trace_parameters(trace)
        port.add_net(self.server_net())
        return port

    def client_data_content(self):
        dc = swifttest.DataContent()
        dc.add_provider(swifttest.DataContent.RANDOM,        '::DataContent(0)')
        dc.add_provider(swifttest.DataContent.SEQUENTIAL,    '::DataContent(1)')
        dc.add_provider(swifttest.DataContent.SEEDED_RANDOM, '::DataContent(2)', seed=1)
        return dc

    def client_net(self):
        net = swifttest.Net('172.16.240.1', '255.255.0.0', 254, 1, '172.16.1.1')
        net.gw_enabled = False
        net.add_scenario(self.client_scenario())
        return net

    def server_net(self):
        net = swifttest.Net('172.16.244.1', '255.255.0.0', 1, 1, '172.16.1.1')
        net.gw_enabled = False
        net.add_scenario(self.server_scenario())
        return net

    def client_scenario(self):
        scenario = swifttest.Scenario()
        self.add_client_load(scenario)
        self.add_client_actions(scenario)
        return scenario

    def server_scenario(self):
        scenario = swifttest.Scenario()
        self.add_server_load(scenario)
        self.add_server_actions(scenario)
        return scenario

    def add_client_load(self, scenario):
        #    /|----|----|----|\
        #   / |    |    |    | \
        #  /  |    |    |    |  \
        # /   |    |    |    |   \
        #  1s        3s        1s
        #  up     scenarios   down
        rampup = swifttest.Load(swifttest.Load.RAMPUP)
        rampup.set_duration(1)
        scenarios = swifttest.Load(swifttest.Load.SCENARIOS)
        scenarios.set_duration(3)
        scenarios.set_max_concurrent(1)
        scenarios.set_max_scenarios(MAX_SCENARIOS)
        rampdown = swifttest.Load(swifttest.Load.RAMPDOWN)
        rampdown.set_duration(1)
        #
        scenario.add_load(rampup)
        scenario.add_load(scenarios)
        scenario.add_load(rampdown)

    def add_server_load(self, scenario):
        scenarios = swifttest.Load(swifttest.Load.SCENARIOS)
        scenarios.set_duration(5)
        scenarios.set_max_concurrent(1)
        #
        scenario.add_load(scenarios)

    def add_client_actions(self, scenario):
        scenario.add_action(swifttest.Action('HTTP', 'Open HTTP Connection', {'Destination Address':'172.16.244.1'}))
        scenario.add_action(self.create_put_action())
        if self.variant[GET_AND_VERIFY]:
            scenario.add_action(self.create_get_action())
        scenario.add_action(swifttest.Action('HTTP', 'Close HTTP Connection'))

    def create_put_action(self):
        action = swifttest.Action('HTTP', 'PUT')
        action.set_parameter('Request URI', '= @STRING(/' + str(self.variant[ENTITY_DATA_LENGTH]) + 'b) + @SCENARIOCOUNTER()')
        action.set_parameter('Data source', '::DataContent(1)')
        action.set_parameter('Data Length', str(self.variant[ENTITY_DATA_LENGTH]))

        if self.variant[CLIENT_CONTENT_MD5]:
            action.set_parameter('Include Content-MD5', 'True')

        headers = 'User-Agent:SwiftTest (http://www.swifttest.com)\r\nAccept:text/html, text/plain, text/css, text/sgml, */*;q=0.01\r\nAccept-Language:en\r\nAccept-Encoding:identity'

        if self.variant[CLIENT_EXPECT100]:
            headers += '\r\nExpect: 100-Continue'

        if self.variant[CLIENT_CONTENT_ENCODING]:
            headers += '\r\nContent-Encoding:' + self.variant[CLIENT_CONTENT_ENCODING]

        action.set_parameter('Request Headers', headers)

        if self.variant[CLIENT_TRANSFER_ENCODING]:
            action.set_parameter('Transfer Encoding', self.variant[CLIENT_TRANSFER_ENCODING])

        return action

    def create_get_action(self):
        action = swifttest.Action('HTTP', 'GET')
        action.set_parameter('Request URI', '= @STRING(/' + str(self.variant[ENTITY_DATA_LENGTH]) + 'b) + @SCENARIOCOUNTER()')
        action.set_parameter('Verify with', '::DataContent(1)')

        headers = 'User-Agent:SwiftTest (http://www.swifttest.com)\r\nAccept:text/html, text/plain, text/css, text/sgml, */*;q=0.01\r\nAccept-Language:en'

        if self.variant[CLIENT_ACCEPT_ENCODING]:
            headers += '\r\nAccept-Encoding:' + self.variant[CLIENT_ACCEPT_ENCODING]
        else:
            headers += '\r\nAccept-Encoding:identity'

        action.set_parameter('Request Headers', headers)

        return action

    def add_server_actions(self, scenario):
        action = swifttest.Action('HTTP', 'Start HTTP server', {'IPv4 Address':'172.16.244.1'})

        if self.variant[SERVER_CONTENT_MD5]:
            action.set_parameter('Include Content-MD5', '1')
        if self.variant[SERVER_FORCE_CHUNKED]:
            action.set_parameter('Enable Chunked Encoding', '1')

        scenario.add_action(action)


#
# Utils
#
def chunked_bytes(entity_size, chunk_size=4096):
    chunks = entity_size / chunk_size
    tail_size = entity_size % chunk_size
    size_of_chunk_length = len(hex(chunk_size)[2:])
    size_of_tail_length = len(hex(tail_size)[2:])
    crlf = 2 # bytes
    ret = chunks*(size_of_chunk_length + crlf + chunk_size + crlf)
    if tail_size > 0:
        ret += size_of_tail_length + crlf + tail_size + crlf
    ret += len(hex(0)[2:]) + crlf + crlf # ending 0 bytes chunk
    return ret

#
# Main
#
def main():
    analyze_args(parse_args())
    t = TestParams()
    g = t.get_generator()

    if not os.path.exists(OUTPUT_DIR):
        os.mkdir(OUTPUT_DIR)

    num = 1
    for variant in g:
        variant[TEST_NUM] = num
        p = TestProject(variant)
        p.generate_automation_config()
        num += 1

if __name__ == '__main__':
    main()
