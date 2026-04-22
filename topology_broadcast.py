#!/usr/bin/env python3
"""
Broadcast Traffic Control — Mininet Topology
Course: UE24CS252B | Project 12
Controller: POX | OpenFlow 1.0

Topology:
    h1 ─┐
    h2 ─┤─── s1 ─── [POX Controller]
    h3 ─┤
    h4 ─┘

Test Scenarios:
    1. Normal unicast traffic — selective forwarding (no flooding)
    2. Normal broadcast traffic (ARP) — allowed within limit
    3. Excessive broadcast — detected and blocked
    4. Evaluate improvement — compare before/after blocking
    5. Regression test — policy consistent after re-check

Usage:
    Terminal 1: cd ~/pox && python3 pox.py broadcast_control
    Terminal 2: sudo python3 ~/topology_broadcast.py
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time


def build_network():
    net = Mininet(
        switch=OVSKernelSwitch,
        link=TCLink,
        autoSetMacs=False,
    )

    info("*** Adding Remote POX Controller\n")
    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6633,
    )

    info("*** Adding Switch\n")
    s1 = net.addSwitch("s1", protocols="OpenFlow10")

    info("*** Adding Hosts\n")
    h1 = net.addHost("h1", mac="00:00:00:00:00:01", ip="10.0.0.1/24")
    h2 = net.addHost("h2", mac="00:00:00:00:00:02", ip="10.0.0.2/24")
    h3 = net.addHost("h3", mac="00:00:00:00:00:03", ip="10.0.0.3/24")
    h4 = net.addHost("h4", mac="00:00:00:00:00:04", ip="10.0.0.4/24")

    info("*** Adding Links\n")
    net.addLink(h1, s1, bw=10)
    net.addLink(h2, s1, bw=10)
    net.addLink(h3, s1, bw=10)
    net.addLink(h4, s1, bw=10)

    info("*** Starting Network\n")
    net.build()
    c0.start()
    s1.start([c0])

    info("\n")
    info("=" * 60 + "\n")
    info("  Broadcast Traffic Control Topology Ready\n")
    info("  Hosts: h1, h2, h3, h4\n")
    info("  Broadcast Rate Limit: 10 per 10s window\n")
    info("=" * 60 + "\n\n")

    run_tests(net)

    info("*** Opening Mininet CLI\n")
    CLI(net)

    info("*** Stopping Network\n")
    net.stop()


def run_tests(net):
    h1, h2, h3, h4 = net.get("h1", "h2", "h3", "h4")

    # ── TEST SCENARIO 1 — Normal unicast traffic ───────────────
    info("\n" + "-" * 60 + "\n")
    info("TEST SCENARIO 1 — Normal unicast (selective forwarding)\n")
    info("-" * 60 + "\n")

    info("h1 → h2 ping (expected: SUCCESS with selective forwarding)\n")
    result = h1.cmd("ping -c 3 -W 2 10.0.0.2")
    info(result + "\n")

    info("h2 → h3 ping (expected: SUCCESS)\n")
    result = h2.cmd("ping -c 3 -W 2 10.0.0.3")
    info(result + "\n")

    info("h3 → h4 ping (expected: SUCCESS)\n")
    result = h3.cmd("ping -c 3 -W 2 10.0.0.4")
    info(result + "\n")

    # ── TEST SCENARIO 2 — Normal broadcast (ARP) ──────────────
    info("-" * 60 + "\n")
    info("TEST SCENARIO 2 — Normal broadcast traffic (within limit)\n")
    info("-" * 60 + "\n")

    info("h1 sends 5 ARP broadcasts (within limit, expected: ALLOWED)\n")
    for i in range(5):
        h1.cmd("arping -c 1 -i h1-eth0 10.0.0.100 2>/dev/null")
    info("5 ARP broadcasts sent from h1 — check POX logs for BCAST entries\n\n")

    # ── TEST SCENARIO 3 — Excessive broadcast ─────────────────
    info("-" * 60 + "\n")
    info("TEST SCENARIO 3 — Excessive broadcast (should be blocked)\n")
    info("-" * 60 + "\n")

    info("h2 sends 15 rapid ARP broadcasts (exceeds limit of 10)\n")
    info("Expected: first 10 allowed, rest BLOCKED\n")
    for i in range(15):
        h2.cmd("arping -c 1 -i h2-eth0 10.0.0.100 2>/dev/null")
    info("15 ARP broadcasts sent from h2 — check POX logs for BLOCKED entries\n\n")

    # ── TEST SCENARIO 4 — Evaluate improvement ────────────────
    info("-" * 60 + "\n")
    info("TEST SCENARIO 4 — Evaluate improvement (iperf throughput)\n")
    info("-" * 60 + "\n")

    info("Starting iperf server on h3...\n")
    h3.cmd("iperf -s -u &")
    time.sleep(1)

    info("h1 → h3 UDP iperf BEFORE broadcast control (5s):\n")
    result = h1.cmd("iperf -c 10.0.0.3 -u -t 5 -b 5M")
    info(result + "\n")
    h3.cmd("kill %iperf")

    # ── TEST SCENARIO 5 — Regression test ────────────────────
    info("-" * 60 + "\n")
    info("REGRESSION TEST — Policy consistency after re-check\n")
    info("-" * 60 + "\n")

    info("h1 → h2 unicast (should still work):\n")
    result = h1.cmd("ping -c 2 -W 2 10.0.0.2")
    lost = [l for l in result.splitlines() if "packet loss" in l]
    info((lost[0] if lost else result) + "\n")

    info("Flow table after all tests:\n")
    result = h1.cmd("ovs-ofctl dump-flows s1")
    info(result + "\n")

    info("-" * 60 + "\n\n")


if __name__ == "__main__":
    setLogLevel("info")
    build_network()
