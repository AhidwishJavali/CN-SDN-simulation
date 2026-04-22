"""
Broadcast Traffic Control System
Course: UE24CS252B - Computer Networks
Project 12: Control excessive broadcast traffic in the network.

Controller: POX | OpenFlow: 1.0

How it works:
- Normal unicast traffic is handled by a learning switch
- Broadcast packets (ARP, unknown destinations) are detected and counted
- After a host exceeds the broadcast rate limit, a temporary DROP rule is installed
- Selective forwarding rules are installed for known unicast flows
- Statistics are displayed periodically
"""

from pox.core import core
from pox.lib.addresses import EthAddr
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.recoco import Timer
import datetime

log = core.getLogger()

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
BROADCAST_RATE_LIMIT = 10      # max broadcasts allowed per time window
RATE_WINDOW_SECONDS  = 10      # time window in seconds
BLOCK_DURATION       = 30      # seconds to block a spamming host
STATS_INTERVAL       = 10      # print stats every N seconds

# Broadcast MAC address
BROADCAST_MAC = EthAddr("ff:ff:ff:ff:ff:ff")

# ─────────────────────────────────────────

class BroadcastController(object):

    def __init__(self, connection):
        self.connection   = connection
        self.mac_to_port  = {}          # learned MAC → port mapping
        self.bcast_count  = {}          # MAC → broadcast count in current window
        self.bcast_blocked = set()      # MACs currently blocked for broadcasting
        self.total_bcast  = 0           # total broadcasts seen
        self.total_unicast = 0          # total unicast packets seen
        self.blocked_count = 0          # total packets blocked
        self.window_start = datetime.datetime.now()

        connection.addListeners(self)
        log.info("Switch %s connected.", dpid_to_str(connection.dpid))

        # Start periodic stats timer
        Timer(STATS_INTERVAL, self._print_stats, recurring=True)

    # ── Logging helper ────────────────────────────────────────
    def _log(self, action, src, dst, reason=""):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        log.info("[%s] %s | src=%s dst=%s | %s", ts, action, src, dst, reason)

    # ── Reset broadcast counters every time window ────────────
    def _reset_window_if_needed(self):
        now = datetime.datetime.now()
        elapsed = (now - self.window_start).total_seconds()
        if elapsed >= RATE_WINDOW_SECONDS:
            self.bcast_count  = {}
            self.bcast_blocked = set()
            self.window_start = now
            log.info("--- Rate window reset ---")

    # ── Install a DROP rule for broadcast spammer ─────────────
    def _install_broadcast_drop(self, src_mac):
        msg = of.ofp_flow_mod()
        msg.priority     = 100
        msg.idle_timeout = BLOCK_DURATION
        msg.hard_timeout = BLOCK_DURATION
        msg.match.dl_src = src_mac
        msg.match.dl_dst = BROADCAST_MAC
        # No actions = DROP
        self.connection.send(msg)
        self.bcast_blocked.add(src_mac)
        self._log("BLOCKED", src_mac, "ff:ff:ff:ff:ff:ff",
                  "broadcast rate exceeded (%d/%d)" % (
                      self.bcast_count.get(src_mac, 0), BROADCAST_RATE_LIMIT))

    # ── Install selective unicast forwarding rule ─────────────
    def _install_forward_rule(self, src_mac, dst_mac, in_port, out_port):
        msg = of.ofp_flow_mod()
        msg.priority     = 10
        msg.idle_timeout = 30
        msg.match.dl_src = src_mac
        msg.match.dl_dst = dst_mac
        msg.match.in_port = in_port
        msg.actions.append(of.ofp_action_output(port=out_port))
        self.connection.send(msg)

    # ── Send packet out ───────────────────────────────────────
    def _send_packet(self, packet_in, out_port):
        msg = of.ofp_packet_out()
        msg.data = packet_in
        msg.actions.append(of.ofp_action_output(port=out_port))
        self.connection.send(msg)

    # ── Print periodic statistics ─────────────────────────────
    def _print_stats(self):
        log.info("=" * 55)
        log.info("  BROADCAST TRAFFIC CONTROL — STATISTICS")
        log.info("  Total Broadcasts   : %d", self.total_bcast)
        log.info("  Total Unicasts     : %d", self.total_unicast)
        log.info("  Broadcasts Blocked : %d", self.blocked_count)
        log.info("  Known MACs         : %s", list(str(m) for m in self.mac_to_port))
        log.info("=" * 55)

    # ── Main PacketIn handler ─────────────────────────────────
    def _handle_PacketIn(self, event):
        pkt      = event.parsed
        src_mac  = pkt.src
        dst_mac  = pkt.dst
        in_port  = event.port

        # Reset rate window if needed
        self._reset_window_if_needed()

        # Learn source MAC → port
        self.mac_to_port[src_mac] = in_port

        # ── BROADCAST DETECTION ───────────────────────────────
        is_broadcast = (dst_mac == BROADCAST_MAC)

        if is_broadcast:
            self.total_bcast += 1

            # Count broadcasts per source
            self.bcast_count[src_mac] = self.bcast_count.get(src_mac, 0) + 1

            # Check if already blocked
            if src_mac in self.bcast_blocked:
                self.blocked_count += 1
                return  # drop silently

            # Check if rate limit exceeded
            if self.bcast_count[src_mac] > BROADCAST_RATE_LIMIT:
                self.blocked_count += 1
                self._install_broadcast_drop(src_mac)
                return  # drop this packet too

            # Allow this broadcast (within limit)
            self._log("BCAST", src_mac, str(dst_mac),
                      "count=%d/%d" % (self.bcast_count[src_mac], BROADCAST_RATE_LIMIT))
            self._send_packet(event.ofp, of.OFPP_FLOOD)
            return

        # ── UNICAST — selective forwarding ────────────────────
        self.total_unicast += 1

        if dst_mac in self.mac_to_port:
            out_port = self.mac_to_port[dst_mac]
            self._log("UNICAST", src_mac, str(dst_mac),
                      "selective forward → port %d" % out_port)
            self._install_forward_rule(src_mac, dst_mac, in_port, out_port)
            self._send_packet(event.ofp, out_port)
        else:
            # Destination unknown — flood but count as broadcast
            self.total_bcast += 1
            self._log("FLOOD", src_mac, str(dst_mac), "dst unknown")
            self._send_packet(event.ofp, of.OFPP_FLOOD)


class BroadcastControlLauncher(object):
    def __init__(self):
        core.openflow.addListenerByName("ConnectionUp", self._handle_ConnectionUp)
        log.info("=" * 55)
        log.info("  Broadcast Traffic Control System Ready")
        log.info("  Broadcast Rate Limit : %d per %ds window",
                 BROADCAST_RATE_LIMIT, RATE_WINDOW_SECONDS)
        log.info("  Block Duration       : %ds", BLOCK_DURATION)
        log.info("=" * 55)

    def _handle_ConnectionUp(self, event):
        BroadcastController(event.connection)


def launch():
    core.registerNew(BroadcastControlLauncher)
