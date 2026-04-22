# Broadcast Traffic Control System
### Course: UE24CS252B — Computer Networks
### Project 12: Control Excessive Broadcast Traffic in the Network

---

## Problem Statement

In a computer network, hosts communicate by first sending **ARP broadcast packets** to discover MAC addresses. While this is normal behavior, a misbehaving or misconfigured host can flood the network with excessive broadcasts, consuming bandwidth and degrading performance for all other hosts — a problem known as a **broadcast storm**.

Traditional switches cannot automatically detect or stop this behavior without manual intervention. This project solves the problem using **Software Defined Networking (SDN)** — a POX controller monitors all traffic, detects excessive broadcasts, and automatically installs DROP flow rules on the switch to block offending hosts, while keeping all legitimate unicast traffic flowing normally.

---

## Objectives
- Detect broadcast packets in the network
- Limit excessive flooding using flow rules
- Install selective forwarding rules for unicast traffic
- Evaluate improvement in network performance

---

## Network Topology

```
h1 (10.0.0.1) ─┐
h2 (10.0.0.2) ─┤─── s1 ─── POX Controller (127.0.0.1:6633)
h3 (10.0.0.3) ─┤
h4 (10.0.0.4) ─┘
```

- 4 hosts connected to 1 Open vSwitch
- All links: 10 Mbps bandwidth
- Controller: POX running OpenFlow 1.0
- Broadcast Rate Limit: 10 broadcasts per 10 second window
- Block Duration: 30 seconds

---

## Technologies Used

| Tool | Purpose |
|------|---------|
| Mininet | Network emulation |
| POX Controller | SDN controller (Python) |
| Open vSwitch | Virtual OpenFlow switch |
| OpenFlow 1.0 | Protocol between controller and switch |
| Wireshark | Packet capture and analysis |
| iperf | Throughput measurement |
| arping | ARP broadcast generation for testing |

---

## SDN Logic & Flow Rule Design

### packet_in Handling
Every new packet with no matching flow rule is sent to the POX controller as a packet_in event. The controller then:
1. Learns the source MAC to port mapping
2. Checks if packet is broadcast (dst = ff:ff:ff:ff:ff:ff)
3. Increments broadcast counter for source MAC
4. Decides to allow or block

### Match-Action Rules

**Broadcast DROP rule (when limit exceeded):**
```
Match:  dl_src = <offending host MAC>
        dl_dst = ff:ff:ff:ff:ff:ff
Action: DROP (empty action list)
Priority: 100
Timeout: 30 seconds
```

**Unicast Selective Forwarding rule:**
```
Match:  dl_src = <source MAC>
        dl_dst = <destination MAC>
        in_port = <input port>
Action: output:<specific port>
Priority: 10
Timeout: 30 seconds
```

---

## Setup & Execution Steps

### Prerequisites
```bash
sudo apt update
sudo apt install mininet -y
sudo apt install openvswitch-switch -y
sudo apt install iperf -y
sudo apt install wireshark -y
sudo apt install iputils-arping -y
```

### Install POX Controller
```bash
git clone https://github.com/noxrepo/pox
cd pox
```

### Project Structure
```
cn_mininet/
├── broadcast_control.py      # POX controller application
├── topology_broadcast.py     # Mininet topology and test scenarios
└── pox/                      # POX controller framework
    └── ext/
        └── broadcast_control.py  # copy of controller here
```

### Copy Controller to POX
```bash
cp ~/Desktop/cn_mininet/broadcast_control.py ~/Desktop/cn_mininet/pox/ext/
```

### Run the Project

**Terminal 1 — Start POX Controller:**
```bash
cd ~/Desktop/cn_mininet/pox
python3 pox.py broadcast_control
```

**Terminal 2 — Start Mininet Topology:**
```bash
sudo python3 ~/Desktop/cn_mininet/topology_broadcast.py
```

### Cleanup
```bash
exit        # exit Mininet CLI
sudo mn -c  # clean up all virtual interfaces
```

---

## Test Scenarios

### Scenario 1 — Normal Broadcast (Allowed)
```bash
h1 arping -c 5 10.0.0.100
```
**Expected:** 5 broadcasts allowed, POX logs show BCAST count=1/10 to 5/10

---

### Scenario 2 — Excessive Broadcast (Blocked)
```bash
h2 arping -c 20 10.0.0.100
```
**Expected:** First 10 allowed, then BLOCKED log appears, DROP rule installed on switch

---

### Scenario 3 — Unicast Still Works (Regression)
```bash
pingall
```
**Expected:** 0% packet loss — proves unicast traffic unaffected by broadcast blocking

---

### Scenario 4 — Performance Evaluation
```bash
h3 iperf -s &
h1 iperf -c 10.0.0.3 -t 5
```
**Expected:** ~9.5 Mbits/sec throughput — full performance maintained

---

### Scenario 5 — Flow Table Verification
```bash
dpctl dump-flows
```
**Expected:** DROP rules and forwarding rules visible with correct match/action fields

---

## Expected Output

### POX Controller Logs
```
INFO: Broadcast Traffic Control System Ready
INFO: Broadcast Rate Limit : 10 per 10s window
INFO: Block Duration       : 30s
INFO: Switch 00-00-00-00-00-01 connected.
INFO: [HH:MM:SS] BCAST  | src=00:00:00:00:00:01 | count=1/10
INFO: [HH:MM:SS] UNICAST| src=00:00:00:00:00:01 | selective forward to port 2
INFO: [HH:MM:SS] BLOCKED| src=00:00:00:00:00:02 | broadcast rate exceeded 10/10
```

### Flow Table (dpctl dump-flows)
```
cookie=0x0, priority=100, dl_src=00:00:00:00:00:02,
dl_dst=ff:ff:ff:ff:ff:ff actions=drop

cookie=0x0, priority=10, dl_src=00:00:00:00:00:01,
dl_dst=00:00:00:00:00:02 actions=output:2
```

### Statistics Output (every 10 seconds)
```
INFO: BROADCAST TRAFFIC CONTROL — STATISTICS
INFO: Total Broadcasts   : 177
INFO: Total Unicasts     : 103
INFO: Broadcasts Blocked : 7
INFO: Known MACs         : [h1, h2, h3, h4]
```

### iperf Output
```
[  3]  0.0- 5.0 sec  X.XX MBytes  ~9.5 Mbits/sec
```

---

## Proof of Execution

Add your screenshots here after running the project:

- Screenshot 1 — POX Controller Started
![alt text](1.png)
- Screenshot 2 — Topology Built
![alt text](2.png)
- Screenshot 3 — BCAST Allowed Logs
![alt text](3,9.png)
- Screenshot 4 — BLOCKED Logs
![alt text](4.png)
- Screenshot 5 — pingall 0% Loss
![alt text](5.png)
- Screenshot 6 — Flow Tables (dpctl dump-flows)
![alt text](6.png)
- Screenshot 7 — iperf Throughput
![alt text](7.png)
- Screenshot 8 — Wireshark ARP Capture
![alt text](8.png)
- Screenshot 9 — Statistics Output
![alt text](3,9-1.png)

---

## References

[1] Mininet Overview — https://mininet.org/overview/

[2] Mininet Walkthrough — https://mininet.org/walkthrough/

[3] POX Controller Wiki — https://github.com/noxrepo/pox/wiki

[4] OpenFlow 1.0 Specification — https://opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf

[5] Open vSwitch Documentation — https://docs.openvswitch.org/

[6] SDN Overview — https://opennetworking.org/sdn-definition/

[7] Mininet GitHub — https://github.com/mininet/mininet
