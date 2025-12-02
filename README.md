# Real-Time Scheduling Simulator

A Python-based simulation tool for analyzing and visualizing Hard Real-Time Scheduling algorithms. This application supports Periodic and Aperiodic tasks, various scheduling policies, and specific server mechanisms for handling aperiodic workloads.

## Features

* **Scheduling Algorithms:** Rate Monotonic (RM), Deadline Monotonic (DM), Earliest Deadline First (EDF), Least Laxity First (LLF).
* **Aperiodic Servers:** Background, Polling Server, Deferrable Server.
* **Precise Simulation:** Uses a time-slicing mechanism (quantum = 0.01s) to handle non-integer timings.
* **Visual Feedback:** Generates dynamic Gantt charts using Matplotlib.
* **Error Detection:** Automatically detects and visualizes Deadline Misses with a red indicator.
* **Multi-Instance Support:** Correctly handles cases where Deadline > Period ($D > T$).

## Prerequisites

* **Python 3.x**
* **Matplotlib** (for plotting charts)
* **Tkinter** (usually included with standard Python installations)

### Installation

Install the required library using pip:

```bash
pip install matplotlib

python rts_scheduler.py