# PingScope

**Local network-quality monitor for Windows.** Measure response time, latency variation (jitter), and packet loss for a game server, router, or any host you choose. Watch a live chart, then save the session as CSV.

PingScope uses the Windows `ping` utility and Python's standard library. It does not change network settings, require administrator access, install a driver, or upload measurements.

## Run

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/) and enable **Add Python to PATH**.
2. Download this repository and extract it.
3. Double-click `run.bat` (or run `py ping_scope.py` in this folder).

No packages need to be installed. Windows Firewall or the target host may block ICMP echo requests; in that case the application records packet loss, which does not necessarily mean the game server itself is unreachable.

## Read the measurements

- **Average latency** is the arithmetic mean of received echo replies.
- **Jitter** is the mean absolute change between consecutive received replies. It is a simple session indicator, not a substitute for a protocol-specific voice or game jitter metric.
- **Packet loss** is the fraction of unanswered ICMP probes in this session.
- **Chart** shows up to the latest 200 probes. A cross marks a probe with no recognized reply.
- **CSV export** includes each probe's local timestamp and outcome plus a compact session summary.

Use a host relevant to your route. A public DNS address is only a convenient connectivity example, not a proxy for any particular game's server.

## Limitations

PingScope measures ICMP round-trip time from this computer. It cannot measure game-server tick delay, congestion inside the game, FPS, or guarantee that another protocol follows the same route. Results are most useful when comparing repeated sessions from the same location and connection.

## Development

```powershell
py ping_scope.py
```

The interface and measurements are local. CSV export happens only when you explicitly choose a destination.

## License

MIT. See [LICENSE](LICENSE).
