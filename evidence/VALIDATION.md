# Validation evidence

Generated UTC: 2026-10-18T22:57:58.071791+00:00

These results were produced by executing the supplied RTL and implementation
flow. The source hashes in this directory identify the checked files.

| Check | Observed result |
| --- | --- |
| Automated RTL and mapped-netlist tests | 11 passed |
| Parallel-core completed transactions | 13,846 exact matches |
| Serial-core completed transactions | 13,846 exact matches |
| Parallel-core initiation interval | 1 clock cycle without stalls |
| Parallel-core input-to-output transfer latency | 4 clock cycles without stalls |
| Serial-core initiation interval | 9 clock cycles without stalls |
| Artix-7 DSP48E1 mapping | 8 parallel; 1 serial |
| iCEBreaker implementation clock constraint | 12.00 MHz |
| Routed static maximum-frequency estimate | 29.14 MHz |
| iCE40 logic cells, including ROM self-test | 1229 / 5280 |
| iCE40 DSP blocks | 8 / 8 |
| Bitstream | Generated successfully |
| Physical FPGA board run | Not performed |

The randomized handshake test uses 12,288 vectors for each core across seeds
42, 2026, and 8675309. Other tests cover directed arithmetic extremes and reset
with work in flight. The four-stage pipeline retains pending output data while
the receiver applies backpressure.

The board self-test is checked at RTL and again after synthesis using the iCE40
primitive models. These are functional simulations without SDF back-annotation.
The routed timing report is a separate static check at the 12 MHz board clock.
The static maximum-frequency estimate is not a measured operating frequency.

The standalone Artix-7 mapping is a resource comparison. It has no associated
Artix-7 place-and-route result. The iCE40 report covers the complete demonstration
top, which deliberately stalls its output periodically.
