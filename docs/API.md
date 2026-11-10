# Gateway API

Base URL `http://<laptop>:8000`. Interactive documentation is served at `/docs`.

| Route | Method | Used by | Purpose |
|---|---|---|---|
| `/telemetry` | POST | nodes | one JSON message per sample |
| `/command/{node_id}` | GET | nodes | oldest pending command, or `{"id": 0, "command": "none"}` |
| `/command/{id}/ack` | POST | nodes | confirm a command was carried out |
| `/command` | POST | dashboard | queue `relay_on`, `relay_off`, `buzzer_on` or `buzzer_off` for a node |
| `/status` | GET | dashboard | live state: nodes, decision, experiment, models |
| `/experiment/start` | POST | dashboard | start a run and, for digital scenarios, the injector |
| `/experiment/stop` | POST | dashboard | end the run |
| `/health` | GET | anyone | liveness check |

## Telemetry message

| Field | Type | Notes |
|---|---|---|
| `node_id` | text | `A` or `B` |
| `seq` | integer | increases by one per message |
| `uptime_ms` | integer | milliseconds since the node started |
| `bus_v`, `current_a`, `power_w` | decimal | from the INA226 |
| `vsense_v` | decimal | Node A only, from the voltage sensor |
| `relay_on` | boolean | Node B only |
| `rssi`, `fw` | integer, text | link strength and firmware tag |

## Experiment request

```json
{"name": "fdi 1", "scenario": "fdi", "node": "A", "field": "current_a", "params": {"factor": 0.6}}
```

Scenarios: `normal`, `physical_fault`, `fdi`, `drift`, `replay`, `interruption`.
`fdi` takes `factor` and `offset`, `drift` takes `rate_per_min`, `replay` takes `depth`.
