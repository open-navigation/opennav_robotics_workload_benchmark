/**
 * Per-platform verdicts.
 *
 * These are translations of what the technical report and the announcement
 * post already say about each platform, kept close to the original wording.
 * No claim here is new; if a claim is not in the report, the README, or the
 * announcement post, it does not belong in this file.
 */

export interface PlatformNotes {
  verdict: string;
  strengths: string[];
  limits: string[];
}

export const PLATFORM_NOTES: Record<string, PlatformNotes> = {
  amd_strix_halo: {
    verdict:
      'Production-capable for this workload and the platform with the most CPU left over ' +
      'with 82% of the CPU bandwidth available to application developers. It can absorb work ' +
      'that today is split between a Jetson Orin and a separate x86 computer.',
    strengths: [
      'Highest available CPU capability per watt. Can absorb at least an additional eight cores of load with no change in application performance.',
      'Completed every mission while holding the lowest control-loop miss rate.',
      'Best in class GPU performance inline with NVIDIA Jetson Thor.',
      'Unified memory: free system RAM is directly available to the GPU for larger models.',
      'x86, so existing x86-only robotics software runs without porting.',
    ],
    limits: [
      'Runs the hottest of the three, so thermal design in a sealed enclosure needs attention.',
      'In the balanced-power category it shows more control-loop misses than at max power, because the generic BIOS balanced profile allocates TDP toward the saturated GPU rather than the CPU.',
      'No equivalent of the Jetson software ecosystem (yet).',
    ],
  },
  jetson_thor: {
    verdict:
      'Production-capable for this workload, Thor has state of the art GPU and memory ' +
      'performance, and is more efficient in GPU-only compute. It has a strong and ' +
      'established NVIDIA software backing and Isaac SDK support.',
    strengths: [
      'Excellent GPU compute and memory bandwidth efficiency.',
      'Unified memory: free system RAM is directly available to the GPU for larger models.',
      'Completed every mission and kept the VLM fed throughout.',
      'The Jetson ecosystem, including Isaac SDK, is available and mature.',
    ],
    limits: [
      'Control-loop misses roughly 3.5x those of Strix Halo at max power.',
      'About half the CPU is consumed by the benchmark workload, leaving materially less for the rest of an application.',
    ],
  },
  jetson_orin: {
    verdict:
      'Significantly behind newer platforms like the Thor or Strix Halo. The Orin AGX was ' +
      'unable to process simulatneous navigation and AI workload in real time. It remains ' +
      'the current workhorse of many production robotics deployments, but not for a stack ' +
      'that adds a modern physical AI workloads.',
    strengths: [
      'The established embedded AI platform, widely adopted and well understood in production robotics.',
      'The lowest cost and power platform.',
      'Fine for the detection, segmentation, and reinforcement-learning workloads it was designed around.',
    ],
    limits: [
      'Mean CPU utitilization near 100% saturated.',
      'Unable to complete 70% of missions in the allotted time due to resource saturation.',
      "Zero VLM queries were successfully processed in the mission's execution time.",
      'The highest control-loop miss rate.',
    ],
  },
};
