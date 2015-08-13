#!/usr/bin/env python
# Copyright (c) PLUMgrid, Inc.
# Licensed under the Apache License, Version 2.0 (the "License")

from sys import argv
from builtins import input
from pyroute2 import IPRoute, NetNS, IPDB, NSPopen
from simulation import Simulation
from subprocess import PIPE, call, Popen

if len(argv) > 1 and argv[1] == "mesh":
  multicast = 0
else:
  multicast = 1

ipr = IPRoute()
ipdb = IPDB(nl=ipr)

num_hosts = 3
null = open("/dev/null", "w")

class TunnelSimulation(Simulation):
    def __init__(self, ipdb):
        super(TunnelSimulation, self).__init__(ipdb)

    def start(self):
        # each entry is tuple of ns_ipdb, out_ifc, in_ifc
        host_info = []
        for i in range(0, num_hosts):
            print("Launching host %i of %i" % (i + 1, num_hosts))
            ipaddr = "172.16.1.%d/24" % (100 + i)
            host_info.append(self._create_ns("host%d" % i, ipaddr=ipaddr,
                disable_ipv6=True))
            if multicast:
              cmd = ["python", "tunnel.py", str(i)]
            else:
              cmd = ["python", "tunnel_mesh.py", str(num_hosts), str(i)]
            p = NSPopen(host_info[i][0].nl.netns, cmd, stdin=PIPE)
            self.processes.append(p)
        with self.ipdb.create(ifname="br-fabric", kind="bridge") as br:
            for host in host_info: br.add_port(host[1])
            br.up()
        print("Validating connectivity")
        for i in range(1, num_hosts):
            for j in range(0, 2):
                retry = -1
                while retry < 0:
                    check = Popen(["ip", "netns", "exec", "host%d" % i,
                                   "ip", "addr", "show", "br%d" % j], stdout=PIPE, stderr=PIPE)
                    out = check.stdout.read()
                    checkip = "99.1.%d.%d" % (j, i+1)
                    retry = out.find(checkip)
                print("VNI%d between host0 and host%d" % (10000 + j, i))
                call(["ip", "netns", "exec", "host%d" % i,
                      "ping", "99.1.%d.1" % j, "-c", "3", "-i", "0.2", "-q"])

try:
    sim = TunnelSimulation(ipdb)
    sim.start()
    input("Press enter to quit:")
    for p in sim.processes: p.communicate(b"\n")
except:
    if "sim" in locals():
        for p in sim.processes: p.kill(); p.wait(); p.release()
finally:
    if "br-fabric" in ipdb.interfaces: ipdb.interfaces["br-fabric"].remove().commit()
    if "sim" in locals(): sim.release()
    ipdb.release()
    null.close()
