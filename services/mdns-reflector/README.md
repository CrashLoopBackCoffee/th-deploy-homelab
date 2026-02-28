# mdns-reflector

Runs [avahi-daemon](https://avahi.org/) as an mDNS reflector on a dedicated LXC container (`192.168.2.5`), bridging multicast DNS traffic across VLANs so services like AirPlay, Chromecast, and printer discovery work across segmented networks.

Alloy is installed alongside it to forward systemd journal logs to the central OTel pipeline.

## How it works

avahi-daemon is configured with `enable-reflector=yes` and `allow-interfaces` set to all non-loopback interfaces detected on the host. It joins the mDNS multicast group (`224.0.0.251`, UDP 5353) on each interface and re-broadcasts packets across all of them — currently bridging eth2, eth20, and eth40.

See: [Making mDNS work across VLANs with Avahi](https://www.xda-developers.com/make-mdns-work-across-vlans/)

## Usage

```bash
# Deploy
./run-ansible.sh

# Dry-run
./run-ansible.sh --check --diff
```
