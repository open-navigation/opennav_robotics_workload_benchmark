# Practitioner's Guide

This is a guide for practitioners that seek to reproduce the experiments. This is a step-by-step set of instructions to run the benchmarks from this repository. It is expected that you have read the `README.md` in `opennav_benchmark_pipeline` and have done the initial setup of your platforms so that they are ready for evaluation.

Unless specified, run all steps on all machines: simulation and testbed platforms.

1. Clone the repository on all machines

```bash
git clone https://github.com/open-navigation/opennav_robotics_workload_benchmark
cd opennav_robotics_workload_benchmark
```

2. Set the DDS network settings if not set in `/etc/sysctl.d/`

```bash
sudo sysctl -w net.core.rmem_max=2147483647
sudo sysctl -w net.core.wmem_max=2147483647
```

3. Change the AMR Simulation and AMR Robotics Workload Dockerfiles to use `cyclone_hil.xml`

Edit the two `Dockerfile`s and adjust the `cyclone_localhost.xml` to `cyclone_hil.xml`.

In the 2x `cyclone_hil.xml` files, set your subnet for the static IP range the connect them over.
We use `10.2.1.0`. To set the static IP addresses of the computers, run the following:

```bash
nmcli con show  # Shows connections, plug in a cable find the one that's active

# Change the IP address
nmcli con mod "Wired connection 1" \
  ipv4.method manual \
  ipv4.addresses 10.2.1.10/24 \  # <-- set this computer's IP here. Each should be unique.
  ipv4.gateway 10.2.1.1 \
  ipv4.dns "8.8.8.8 1.1.1.1"

nmcli con up "Wired connection 1"  # Connect to the network

ifconfig # Verify the changes
```

For example we set it up as:
* Thor to `10.2.1.10`
* Orin to `10.2.1.20`
* Strix Halo to `10.2.1.30`
* Developer or Simulation Machine `10.2.1.40`

Only if you are running the simulation on a separate machine from the testbed platform to isolate to only run-time experimentation.

4. Build all 3 Dockerfiles using the instructions in the `opennav_benchmark_pipeline/README.md`

Take care to set the AI workload tag appropriately to your current testbed platform.

If this is the first time you're building the AI images, it will take some time as it will download the complete models.

5. If not already connected over ethernet, do so now.

Verify connection with `ifconfig` on the subnet of your choosing.

6. Run the simulation from the instructions in `opennav_benchmark_pipeline/README.md` on one machine.

7. Run the benchmark from the instrucitons in `opennav_benchmark_pipeline/README.md` on the other machine.

If you want to run with a VLM model, make sure to set `VLM_IMAGE=opennav_benchmark/ai_workload:<your platform here>` before the script to launch that server.

8. Wait for results!

On the simulation computer, if you're logged in with a display, Rviz will show up for you to follow along with. If the simulation computer is being accessed headlessly, it will not.

Results will be posted on the `opennav_benchmark_logs` directory.

You can analyze them using the scripts in `opennav_benchmark_analysis` if you like :-)

Happy benchmarking!

- Steve
