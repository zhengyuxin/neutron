# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 Nicira Networks, Inc.
# Copyright 2011 Citrix Systems
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
# @author: Somik Behera, Nicira Networks, Inc.
# @author: Brad Hall, Nicira Networks, Inc.

import httplib
import logging as LOG
import json
import socket
import sys
import urllib

from manager import QuantumManager
from optparse import OptionParser
from quantum.common.wsgi import Serializer

FORMAT = "json"
CONTENT_TYPE = "application/" + FORMAT


### --- Miniclient (taking from the test directory)
### TODO(bgh): move this to a library within quantum
class MiniClient(object):
    """A base client class - derived from Glance.BaseClient"""
    action_prefix = '/v0.1/tenants/{tenant_id}'

    def __init__(self, host, port, use_ssl):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.connection = None

    def get_connection_type(self):
        if self.use_ssl:
            return httplib.HTTPSConnection
        else:
            return httplib.HTTPConnection

    def do_request(self, tenant, method, action, body=None,
                   headers=None, params=None):
        action = MiniClient.action_prefix + action
        action = action.replace('{tenant_id}', tenant)
        if type(params) is dict:
            action += '?' + urllib.urlencode(params)
        try:
            connection_type = self.get_connection_type()
            headers = headers or {}
            # Open connection and send request
            c = connection_type(self.host, self.port)
            c.request(method, action, body, headers)
            res = c.getresponse()
            status_code = self.get_status_code(res)
            if status_code in (httplib.OK, httplib.CREATED,
                               httplib.ACCEPTED, httplib.NO_CONTENT):
                return res
            else:
                raise Exception("Server returned error: %s" % res.read())
        except (socket.error, IOError), e:
            raise Exception("Unable to connect to server. Got error: %s" % e)

    def get_status_code(self, response):
        if hasattr(response, 'status_int'):
            return response.status_int
        else:
            return response.status
### -- end of miniclient

### -- Core CLI functions


def list_nets(manager, *args):
    tenant_id = args[0]
    networks = manager.get_all_networks(tenant_id)
    print "Virtual Networks on Tenant:%s\n" % tenant_id
    for net in networks:
        id = net["net-id"]
        name = net["net-name"]
        print "\tNetwork ID:%s \n\tNetwork Name:%s \n" % (id, name)


def api_list_nets(client, *args):
    tenant_id = args[0]
    res = client.do_request(tenant_id, 'GET', "/networks." + FORMAT)
    resdict = json.loads(res.read())
    LOG.debug(resdict)
    print "Virtual Networks on Tenant:%s\n" % tenant_id
    for n in resdict["networks"]:
        net_id = n["id"]
        print "\tNetwork ID:%s\n" % (net_id)
        # TODO(bgh): we should make this call pass back the name too
        # name = n["net-name"]
        # LOG.info("\tNetwork ID:%s \n\tNetwork Name:%s \n" % (id, name))


def create_net(manager, *args):
    tid, name = args
    new_net_id = manager.create_network(tid, name)
    print "Created a new Virtual Network with ID:%s\n" % new_net_id


def api_create_net(client, *args):
    tid, name = args
    data = {'network': {'network-name': '%s' % name}}
    body = Serializer().serialize(data, CONTENT_TYPE)
    res = client.do_request(tid, 'POST', "/networks." + FORMAT, body=body)
    rd = json.loads(res.read())
    LOG.debug(rd)
    nid = None
    try:
        nid = rd["networks"]["network"]["id"]
    except Exception, e:
        print "Failed to create network"
        # TODO(bgh): grab error details from ws request result
        return
    print "Created a new Virtual Network with ID:%s\n" % nid


def delete_net(manager, *args):
    tid, nid = args
    manager.delete_network(tid, nid)
    print "Deleted Virtual Network with ID:%s" % nid


def api_delete_net(client, *args):
    tid, nid = args
    res = client.do_request(tid, 'DELETE', "/networks/" + nid + "." + FORMAT)
    status = res.status
    if status != 202:
        print "Failed to delete network"
        output = res.read()
        print output
    else:
        print "Deleted Virtual Network with ID:%s" % nid


def detail_net(manager, *args):
    tid, nid = args
    iface_list = manager.get_network_details(tid, nid)
    print "Remote Interfaces on Virtual Network:%s\n" % nid
    for iface in iface_list:
        print "\tRemote interface:%s" % iface


def api_detail_net(client, *args):
    tid, nid = args
    res = client.do_request(tid, 'GET',
      "/networks/%s/ports.%s" % (nid, FORMAT))
    output = res.read()
    if res.status != 200:
        LOG.error("Failed to list ports: %s" % output)
        return
    rd = json.loads(output)
    LOG.debug(rd)
    print "Remote Interfaces on Virtual Network:%s\n" % nid
    for port in rd["ports"]:
        pid = port["id"]
        res = client.do_request(tid, 'GET',
          "/networks/%s/ports/%s/attachment.%s" % (nid, pid, FORMAT))
        output = res.read()
        rd = json.loads(output)
        LOG.debug(rd)
        remote_iface = rd["attachment"]
        print "\tRemote interface:%s" % remote_iface


def rename_net(manager, *args):
    tid, nid, name = args
    manager.rename_network(tid, nid, name)
    print "Renamed Virtual Network with ID:%s" % nid


def api_rename_net(client, *args):
    tid, nid, name = args
    data = {'network': {'network-name': '%s' % name}}
    body = Serializer().serialize(data, CONTENT_TYPE)
    res = client.do_request(tid, 'PUT', "/networks/%s.%s" % (nid, FORMAT),
      body=body)
    resdict = json.loads(res.read())
    LOG.debug(resdict)
    print "Renamed Virtual Network with ID:%s" % nid


def list_ports(manager, *args):
    tid, nid = args
    ports = manager.get_all_ports(tid, nid)
    print "Ports on Virtual Network:%s\n" % nid
    for port in ports:
        print "\tVirtual Port:%s" % port["port-id"]


def api_list_ports(client, *args):
    tid, nid = args
    res = client.do_request(tid, 'GET',
      "/networks/%s/ports.%s" % (nid, FORMAT))
    output = res.read()
    if res.status != 200:
        LOG.error("Failed to list ports: %s" % output)
        return
    rd = json.loads(output)
    LOG.debug(rd)
    print "Ports on Virtual Network:%s\n" % nid
    for port in rd["ports"]:
        print "\tVirtual Port:%s" % port["id"]


def create_port(manager, *args):
    tid, nid = args
    new_port = manager.create_port(tid, nid)
    print "Created Virtual Port:%s " \
          "on Virtual Network:%s" % (new_port, nid)


def api_create_port(client, *args):
    tid, nid = args
    res = client.do_request(tid, 'POST',
      "/networks/%s/ports.%s" % (nid, FORMAT))
    output = res.read()
    if res.status != 200:
        LOG.error("Failed to create port: %s" % output)
        return
    rd = json.loads(output)
    new_port = rd["ports"]["port"]["id"]
    print "Created Virtual Port:%s " \
          "on Virtual Network:%s" % (new_port, nid)


def delete_port(manager, *args):
    tid, nid, pid = args
    LOG.info("Deleted Virtual Port:%s " \
          "on Virtual Network:%s" % (pid, nid))


def api_delete_port(client, *args):
    tid, nid, pid = args
    res = client.do_request(tid, 'DELETE',
      "/networks/%s/ports/%s.%s" % (nid, pid, FORMAT))
    output = res.read()
    if res.status != 202:
        LOG.error("Failed to delete port: %s" % output)
        return
    LOG.info("Deleted Virtual Port:%s " \
          "on Virtual Network:%s" % (pid, nid))


def detail_port(manager, *args):
    tid, nid, pid = args
    port_detail = manager.get_port_details(tid, nid, pid)
    print "Virtual Port:%s on Virtual Network:%s " \
          "contains remote interface:%s" % (pid, nid, port_detail)


def api_detail_port(client, *args):
    tid, nid, pid = args
    res = client.do_request(tid, 'GET',
      "/networks/%s/ports/%s.%s" % (nid, pid, FORMAT))
    output = res.read()
    if res.status != 200:
        LOG.error("Failed to get port details: %s" % output)
        return
    rd = json.loads(output)
    port = rd["ports"]["port"]
    id = port["id"]
    attachment = port["attachment"]
    LOG.debug(port)
    print "Virtual Port:%s on Virtual Network:%s " \
          "contains remote interface:%s" % (pid, nid, attachment)


def plug_iface(manager, *args):
    tid, nid, pid, vid = args
    manager.plug_interface(tid, nid, pid, vid)
    print "Plugged remote interface:%s " \
      "into Virtual Network:%s" % (vid, nid)


def api_plug_iface(client, *args):
    tid, nid, pid, vid = args
    data = {'port': {'attachment-id': '%s' % vid}}
    body = Serializer().serialize(data, CONTENT_TYPE)
    res = client.do_request(tid, 'PUT',
      "/networks/%s/ports/%s/attachment.%s" % (nid, pid, FORMAT), body=body)
    output = res.read()
    LOG.debug(output)
    if res.status != 202:
        LOG.error("Failed to plug iface \"%s\" to port \"%s\": %s" % (vid,
          pid, output))
        return
    print "Plugged interface \"%s\" to port:%s on network:%s" % (vid, pid, nid)


def unplug_iface(manager, *args):
    tid, nid, pid = args
    manager.unplug_interface(tid, nid, pid)
    print "UnPlugged remote interface " \
      "from Virtual Port:%s Virtual Network:%s" % (pid, nid)


def api_unplug_iface(client, *args):
    tid, nid, pid = args
    data = {'port': {'attachment-id': ''}}
    body = Serializer().serialize(data, CONTENT_TYPE)
    res = client.do_request(tid, 'DELETE',
      "/networks/%s/ports/%s/attachment.%s" % (nid, pid, FORMAT), body=body)
    output = res.read()
    LOG.debug(output)
    if res.status != 202:
        LOG.error("Failed to unplug iface from port \"%s\": %s" % (pid, output))
        return
    print "Unplugged interface from port:%s on network:%s" % (pid, nid)


commands = {
  "list_nets": {
    "func": list_nets,
    "api_func": api_list_nets,
    "args": ["tenant-id"]},
  "create_net": {
    "func": create_net,
    "api_func": api_create_net,
    "args": ["tenant-id", "net-name"]},
  "delete_net": {
    "func": delete_net,
    "api_func": api_delete_net,
    "args": ["tenant-id", "net-id"]},
  "detail_net": {
    "func": detail_net,
    "api_func": api_detail_net,
    "args": ["tenant-id", "net-id"]},
  "rename_net": {
    "func": rename_net,
    "api_func": api_rename_net,
    "args": ["tenant-id", "net-id", "new-name"]},
  "list_ports": {
    "func": list_ports,
    "api_func": api_list_ports,
    "args": ["tenant-id", "net-id"]},
  "create_port": {
    "func": create_port,
    "api_func": api_create_port,
    "args": ["tenant-id", "net-id"]},
  "delete_port": {
    "func": delete_port,
    "api_func": api_delete_port,
    "args": ["tenant-id", "net-id", "port-id"]},
  "detail_port": {
    "func": detail_port,
    "api_func": api_detail_port,
    "args": ["tenant-id", "net-id", "port-id"]},
  "plug_iface": {
    "func": plug_iface,
    "api_func": api_plug_iface,
    "args": ["tenant-id", "net-id", "port-id", "iface-id"]},
  "unplug_iface": {
    "func": unplug_iface,
    "api_func": api_unplug_iface,
    "args": ["tenant-id", "net-id", "port-id"]}, }


def help():
    print "\nCommands:"
    for k in commands.keys():
        print "    %s %s" % (k,
          " ".join(["<%s>" % y for y in commands[k]["args"]]))


def build_args(cmd, cmdargs, arglist):
    args = []
    orig_arglist = arglist[:]
    try:
        for x in cmdargs:
            args.append(arglist[0])
            del arglist[0]
    except Exception, e:
        LOG.error("Not enough arguments for \"%s\" (expected: %d, got: %d)" % (
          cmd, len(cmdargs), len(orig_arglist)))
        print "Usage:\n    %s %s" % (cmd,
          " ".join(["<%s>" % y for y in commands[cmd]["args"]]))
        return None
    if len(arglist) > 0:
        LOG.error("Too many arguments for \"%s\" (expected: %d, got: %d)" % (
          cmd, len(cmdargs), len(orig_arglist)))
        print "Usage:\n    %s %s" % (cmd,
          " ".join(["<%s>" % y for y in commands[cmd]["args"]]))
        return None
    return args


if __name__ == "__main__":
    usagestr = "Usage: %prog [OPTIONS] <command> [args]"
    parser = OptionParser(usage=usagestr)
    parser.add_option("-l", "--load-plugin", dest="load_plugin",
      action="store_true", default=False,
      help="Load plugin directly instead of using WS API")
    parser.add_option("-H", "--host", dest="host",
      type="string", default="127.0.0.1", help="ip address of api host")
    parser.add_option("-p", "--port", dest="port",
      type="int", default=9696, help="api poort")
    parser.add_option("-s", "--ssl", dest="ssl",
      action="store_true", default=False, help="use ssl")
    parser.add_option("-v", "--verbose", dest="verbose",
      action="store_true", default=False, help="turn on verbose logging")

    options, args = parser.parse_args()

    if options.verbose:
        LOG.basicConfig(level=LOG.DEBUG)
    else:
        LOG.basicConfig(level=LOG.WARN)

    if len(args) < 1:
        parser.print_help()
        help()
        sys.exit(1)

    cmd = args[0]
    if cmd not in commands.keys():
        LOG.error("Unknown command: %s" % cmd)
        help()
        sys.exit(1)

    args = build_args(cmd, commands[cmd]["args"], args[1:])
    if not args:
        sys.exit(1)
    LOG.debug("Executing command \"%s\" with args: %s" % (cmd, args))
    if not options.load_plugin:
        client = MiniClient(options.host, options.port, options.ssl)
        if "api_func" not in commands[cmd]:
            LOG.error("API version of \"%s\" is not yet implemented" % cmd)
            sys.exit(1)
        commands[cmd]["api_func"](client, *args)
    else:
        quantum = QuantumManager()
        manager = quantum.get_manager()
        commands[cmd]["func"](manager, *args)
    sys.exit(0)
