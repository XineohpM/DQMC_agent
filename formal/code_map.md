# Code Map

This map describes the functional roles of the files in `/Users/a9012/Desktop/dqmc-dev/`.
It intentionally omits `test/`, `.git/`, `.venv/`, `__pycache__/`, generated logs, and generated numerical data files.

## Simulation pipeline

### 1. Choose model parameters and generate HDF5 inputs

The standard simulation starts from a Python generator that creates one or more HDF5 files. These files contain the model metadata, DQMC parameters, initial Hubbard-Stratonovich state, random-number state, and zero-initialized measurement datasets.

Primary input generators:

- `util/gen_1band_unified_hub.py`
  - Generates HDF5 input files for the unified one-band Hubbard model.
  - Builds lattice geometry, hopping matrices, Peierls phases, Hubbard-Stratonovich parameters, measurement flags, index maps, and initial measurement groups.
- `util/gen_3band_hub.py`
  - Generates HDF5 input files for a three-band Hubbard model.
- `util/gen_topo_3band_hub.py`
  - Generates HDF5 input files for topological/trivial three-band models.

Shared generator support:

- `util/gen_util_shared.py`
  - Provides shared command-line options, RNG helpers, batch-generation helpers, and Hubbard-Stratonovich setup helpers.
- `util/tight_binding.py`
  - Constructs tight-binding Hamiltonians and Peierls matrices for supported lattice geometries.

Batch and scan generators:

- `scripts/gen_beta_scan.py`
  - Generates a beta scan by choosing compatible imaginary-time discretizations and calling the input generator.
- `scripts/gen_beta_mu_scan.py`
  - Generates a combined beta and chemical-potential scan.
- `scripts/mu_tuning_coarse/*`
  - Coarse chemical-potential tuning workflow scripts.
- `scripts/mu_tuning_fine/*`
  - Fine chemical-potential tuning workflow scripts.

### 2. Build the DQMC executables

The C source is compiled through the makefiles and platform build scripts in `build/`.

- `build/Makefile`
  - Main build recipe.
- `build/Makefile_cplx`
  - Complex-number build recipe.
- `build/Makefile.icx`, `build/gcc.imkl.Makefile`, `build/aocc.Makefile`, `build/colab.Makefile`, `build/cori.Makefile`, `build/mobius.Makefile`, `build/perlmt-cpu.Makefile`
  - Compiler/platform-specific build recipes.
- `build/build_rc_*.sh`
  - Platform-specific convenience build scripts.

### 3. Run DQMC on an HDF5 file or stack of files

DQMC wrapper and core:

- `src/dqmc.c`
  - `dqmc_wrapper(...)` opens the HDF5 file, checks compatibility, estimates memory, reads data, runs the DQMC core, and saves final data.
  - The internal `dqmc(...)` function performs sweeps, Hubbard-Stratonovich updates, Green-function stabilization/recalculation, equal-time measurements, unequal-time measurements, checkpoint saves, and cleanup.
- `src/dqmc.h`
  - Declares the DQMC wrapper interface and return-code conventions.

Core numerical helpers:

- `src/updates.c`, `src/updates.h`
  - Local Hubbard-Stratonovich update kernels and delayed Green-function update logic.
- `src/greens.c`, `src/greens.h`
  - Equal-time and unequal-time Green-function construction and stabilization.
- `src/linalg.h`, `src/linalg_generic.h`, `src/linalg_mkl.h`
  - Linear algebra abstraction layer and backend-specific implementations.
- `src/rand.h`
  - RNG state and random-number helpers.
- `src/time_.h`
  - Wall-clock timing utilities.
- `src/sig.c`, `src/sig.h`
  - Signal and timeout handling.
- `src/prof.c`, `src/prof.h`
  - Runtime profiling timers and report printing.
- `src/util.h`
  - Shared C utility macros and allocation/error helpers.

### 4. Measure observables during the DQMC run

Measurements are scheduled by `src/dqmc.c` and implemented by `src/meas.c`.

- Equal-time measurements:
  - Triggered after warmup when `period_eqlt > 0` and the current time slice matches the equal-time measurement period.
  - `src/dqmc.c` half-wraps the Green functions and calls `measure_eqlt(...)`.
  - `src/meas.c` accumulates density, double occupancy, equal-time Green functions, spin/charge/pair correlations, and optional flagged observables.

- Unequal-time measurements:
  - Triggered after warmup when `period_uneqlt > 0` and the sweep index matches the unequal-time measurement period.
  - `src/dqmc.c` constructs `G(0,t)`, `G(t,t)`, and `G(t,0)` for both spins and calls `measure_uneqlt(...)`.
  - `src/meas.c` accumulates unequal-time Green functions, dynamic spin/charge/pair correlations, and optional bond/current/thermal/nematic/general-susceptibility observables.

Measurement data structures:

- `src/data.h`
  - Defines `struct meas_eqlt`, `struct meas_uneqlt`, `struct sim_params`, `struct sim_state`, and `struct sim_data`.
- `src/meas.h`
  - Declares the measurement entry points.

### 5. Read and write HDF5 state and measurement data

Initial HDF5 creation:

- `util/gen_1band_unified_hub.py`, `util/gen_3band_hub.py`, `util/gen_topo_3band_hub.py`
  - Use `h5py` to create `/metadata`, `/params`, `/state`, `/meas_eqlt`, and `/meas_uneqlt`.
  - Measurement arrays are created with the output layout expected by the C reader/writer.

Runtime HDF5 I/O:

- `src/data.c`
  - Reads HDF5 input into C structs with `sim_data_read_alloc(...)`.
  - Writes checkpoints and final simulation data with `sim_data_save(...)`.
  - Maintains the `partial_write` guard to detect interrupted/corrupted writes.
  - Reads and writes `/state`, `/meas_eqlt`, and `/meas_uneqlt`.
- `src/data.h`
  - Declares the HDF5 read/save/free functions and all in-memory layouts.

### 6. Analyze, validate, and plot simulation outputs

General loading/statistics:

- `util/util.py`
  - HDF5 loading helpers and jackknife estimators.
- `util/data_analysis.py`
  - Higher-level equal-time analysis, momentum transforms, metadata inference, and jackknife workflows.

Physical analysis modules:

- `util/thermal.py`
  - Thermal and energy-related analysis helpers.
- `util/transport.py`
  - Transport analysis, current correlations, Kubo/MaxEnt-related processing.
- `util/jqjq.py`, `util/jqjq_wen.py`
  - Heat-current and current-current correlation analysis.
- `util/maxent.py`
  - Maximum entropy analytic continuation utilities.

Convenience tools:

- `util/get_mu.py`
  - Chemical-potential lookup/tuning helper.
- `util/print_n.py`
  - Prints density/filling information from HDF5 outputs.
- `util/info.py`
  - Prints or summarizes simulation-file information.
- `util/summary.py`
  - Summarizes simulation output directories.
- `util/push.py`
  - Pushes simulation files or directories into stack/workflow files.

Analysis scripts:

- `scripts/check_h5_completion.py`
  - Checks whether HDF5 runs appear complete from saved state and logs.
- `scripts/check_sum_rule.py`
  - Checks measurement sum rules.
- `scripts/check_warm.py`
  - Diagnoses warmup/thermalization using measured time series.
- `scripts/compute_specific_heat.py`
  - Computes specific heat from measured energy-like observables.
- `scripts/conductivity_plot.py`
  - Plots conductivity-related results.
- `scripts/resistivity_plot.py`, `scripts/resistivity_proxy.py`
  - Computes or plots resistivity estimates/proxies.
- `scripts/extract_1_particle_local_g.py`
  - Extracts local one-particle Green-function data.
- `scripts/extract_energy_perfile.py`
  - Extracts energy observables per file.
- `scripts/extract_local_moment.py`
  - Extracts local moment estimates.
- `scripts/extract_perbin_jj.py`
  - Extracts per-bin current-current correlation data.
- `scripts/get_n_from_best_mu.py`
  - Reads density at selected/best chemical potentials.
- `scripts/make_bootstrap.py`
  - Generates bootstrap samples for downstream analysis.
- `scripts/save_boot_stats.py`
  - Saves bootstrap statistics.
- `scripts/maxent.py`, `scripts/run_maxent.py`, `scripts/run_maxent_anneal.py`, `scripts/run_maxent_phoenix.py`
  - Maximum entropy workflows.
- `scripts/plot_JNJN.py`
  - Plots particle/heat-current correlation data.
- `scripts/plot_best_mu_vs_T.py`
  - Plots best chemical potential versus temperature.
- `scripts/plot_charge_order.py`
  - Plots charge-order observables.
- `scripts/plot_compressibility_from_best_mu.py`
  - Computes/plots compressibility using best-mu directories.
- `scripts/plot_compressibility_from_n_mu.py`
  - Computes/plots compressibility from density versus chemical potential.
- `scripts/plot_dos.py`
  - Plots density of states data, typically after analytic continuation.
- `scripts/plot_double_occ.py`
  - Plots double occupancy.
- `scripts/s_wave_pairing.py`
  - Computes and plots onsite s-wave pairing structure-factor estimates.
- `scripts/data_analysis.py`
  - Script-level analysis entry point or local copy of analysis helpers.

Cluster/workflow scripts:

- `scripts/run_stack_owners.sh`
  - Runs stack jobs grouped by owners/workers.
- `scripts/run_stack_simes.sh`
  - Runs stack-style simulations.
- `scripts/multi_dir_push_stack.sh`
  - Pushes simulation files from multiple directories into stack files.
- `scripts/multi_dir_submit_sbatch.sh`
  - Submits jobs for multiple directories to an sbatch-style scheduler.

High-temperature expansion side workflow:

- `scripts/wen_high_T_expansion/Makefile`
  - Builds the high-temperature-expansion helper code.
- `scripts/wen_high_T_expansion/main_tp0_all.cpp`
  - C++ implementation for high-temperature-expansion calculations.
- `scripts/wen_high_T_expansion/high-temperature-expansion/main.cpp`
  - Additional high-temperature-expansion C++ code.
- `scripts/wen_high_T_expansion/high-temperature-expansion/go8_n1.sh`, `scripts/wen_high_T_expansion/high-temperature-expansion/gocheckU6.sh`
  - Run/check helper scripts for the high-temperature-expansion workflow.

## Code specification

### Project root

- `README.md`
  - Project-level usage and orientation documentation.
- `TESTING.md`
  - Testing notes and expected test workflows.

### `src/`

- `src/dqmc.c`
  - Main DQMC runtime implementation.
  - `dqmc_wrapper(...)` handles logging, compatibility checks, memory estimates, HDF5 read, DQMC execution, final save, and cleanup.
  - The internal DQMC loop performs sweeps, local updates, Green-function wrapping/recalculation, equal-time measurements, unequal-time measurements, and checkpointing.

- `src/dqmc.h`
  - Public interface for `dqmc_wrapper(...)`.
  - Defines wrapper-level return codes used by single-file and stack executables.

- `src/data.c`
  - HDF5 runtime I/O layer.
  - Reads metadata, parameters, maps, state, and accumulated measurements from HDF5.
  - Allocates/free simulation memory and saves checkpoints/final results.
  - Maintains `partial_write` protection for interrupted HDF5 writes.

- `src/data.h`
  - Defines core C data structures: simulation parameters, state, equal-time measurements, unequal-time measurements, and aggregate simulation data.
  - Declares memory/I/O functions used by the DQMC wrapper.

- `src/meas.c`
  - Measurement kernels for equal-time and unequal-time observables.
  - Accumulates sign-weighted density, double occupancy, Green functions, charge/spin correlations, pair correlations, currents, thermal correlations, chiral observables, nematic observables, and general susceptibility tensors depending on flags.

- `src/meas.h`
  - Declares `measure_eqlt(...)`, `measure_uneqlt(...)`, and helper measurement interfaces.

- `src/greens.c`
  - Green-function construction, propagation, stabilization, and unequal-time Green-function calculation.
  - Supplies the numerical routines used by the DQMC loop after updates and before measurements.

- `src/greens.h`
  - Declarations for Green-function and stabilization routines.

- `src/updates.c`
  - Hubbard-Stratonovich local update routines.
  - Computes update probabilities and applies delayed Green-function updates.

- `src/updates.h`
  - Declarations for update kernels.

- `src/linalg.h`
  - Linear algebra abstraction include layer.
  - Selects the generic or optimized backend depending on build configuration.

- `src/linalg_generic.h`
  - Generic C/CBLAS-style linear algebra helpers.
  - Provides matrix multiplication, decomposition, and matrix utility wrappers when the generic backend is used.

- `src/linalg_mkl.h`
  - Intel MKL-oriented linear algebra backend.
  - Provides optimized numerical kernels for MKL builds.

- `src/rand.h`
  - Random-number generator helpers and RNG state operations.
  - Used for Hubbard-Stratonovich initialization, update decisions, and site-order shuffling.

- `src/sig.c`
  - Signal handling and wall-time interruption logic.
  - Allows simulations to checkpoint and exit cleanly on timeout or interrupt.

- `src/sig.h`
  - Declarations for signal/timeout handling.

- `src/prof.c`
  - Profiling counters and timing accumulation.
  - Prints timing breakdowns after DQMC wrapper cleanup.

- `src/prof.h`
  - Profiling macro and function declarations.

- `src/time_.h`
  - Wall-clock timer helpers and time unit constants.

- `src/util.h`
  - Shared C utility macros, allocation wrappers, error-return helpers, and type-level convenience definitions.

- `src/.clang-format`
  - Formatting configuration for C source files.

### `util/`

- `util/gen_1band_unified_hub.py`
  - Main one-band Hubbard HDF5 generator.
  - Builds geometry, hopping, Peierls factors, exponentiated kinetic matrices, HS transformation parameters, index maps, measurement flags, and initial HDF5 datasets.
  - Supports single-file and batch generation.

- `util/gen_3band_hub.py`
  - Three-band Hubbard HDF5 generator.
  - Similar in structure to the one-band generator but with three-band model-specific geometry and parameters.

- `util/gen_topo_3band_hub.py`
  - Topological/trivial three-band HDF5 generator.
  - Uses three-band tight-binding models from `tight_binding.py`.

- `util/gen_util_shared.py`
  - Shared generator infrastructure.
  - Provides command-line option builders, seed/RNG setup, batch file helpers, and Hubbard-Stratonovich decoupling helpers.

- `util/tight_binding.py`
  - Tight-binding model construction library.
  - Generates hopping matrices and Peierls factors for square, triangular, honeycomb, kagome, topological three-band, and trivial three-band models.

- `util/util.py`
  - General HDF5 data loading and statistical utilities.
  - Provides `load_file`, `load_firstfile`, `load`, `jackknife`, and `jackknife_noniid`.

- `util/data_analysis.py`
  - General analysis module for measured DQMC data.
  - Includes jackknife handling, metadata inference, equal-time observable analysis, momentum transforms, and chemical-potential parsing helpers.

- `util/thermal.py`
  - Thermal observable analysis helpers.
  - Used for energy, heat capacity, and related thermal quantities.

- `util/transport.py`
  - Transport-analysis module.
  - Loads current and correlation observables, constructs conductivity/thermal-conductivity inputs, and interfaces with MaxEnt workflows.

- `util/jqjq.py`
  - Heat-current/current-current correlation analysis utilities.
  - Supports processing of `JQJQ`-type measured correlations.

- `util/jqjq_wen.py`
  - Alternate or Wen-style `JQJQ` analysis utilities.

- `util/maxent.py`
  - Maximum entropy analytic continuation implementation and helpers.

- `util/get_mu.py`
  - Chemical-potential selection and lookup helper.
  - Used in filling-targeted workflows.

- `util/print_n.py`
  - Reads DQMC outputs and prints density/filling information.

- `util/info.py`
  - Prints summary information about HDF5 simulation files or directories.

- `util/summary.py`
  - Produces directory-level summaries of DQMC runs and measured quantities.

- `util/push.py`
  - Workflow helper for pushing simulation files into stack files or job lists.

### `scripts/`

- `scripts/gen_beta_scan.py`
  - Generates input files or commands for a beta scan.
  - Chooses compatible `L`, `dt`, block sizes, and measurement options.

- `scripts/gen_beta_mu_scan.py`
  - Generates input files or commands for a combined beta and chemical-potential scan.
  - Expands both beta and mu axes and forwards measurement options.

- `scripts/check_h5_completion.py`
  - Checks whether HDF5 files appear complete.
  - Uses simulation state and log-tail markers such as successful final save.

- `scripts/check_sum_rule.py`
  - Validates measured observables against expected sum rules.

- `scripts/check_warm.py`
  - Diagnoses warmup quality and running means for selected observables.
  - Produces warmup plots and summaries.

- `scripts/compute_specific_heat.py`
  - Computes specific heat from energy or thermal observables.

- `scripts/conductivity_plot.py`
  - Plots conductivity results from processed transport data.

- `scripts/resistivity_plot.py`
  - Plots resistivity as a function of temperature or other scan axes.

- `scripts/resistivity_proxy.py`
  - Computes resistivity proxy quantities from imaginary-time/current-correlation data.

- `scripts/extract_1_particle_local_g.py`
  - Extracts local one-particle Green-function data from HDF5 outputs.

- `scripts/extract_energy_perfile.py`
  - Extracts energy-related quantities per simulation file.

- `scripts/extract_local_moment.py`
  - Extracts local moment data from density/double-occupancy observables.

- `scripts/extract_perbin_jj.py`
  - Extracts per-bin current-current correlation data for later bootstrap/plotting.

- `scripts/get_n_from_best_mu.py`
  - Reads densities from selected best-mu runs.

- `scripts/make_bootstrap.py`
  - Generates bootstrap resamples for downstream uncertainty estimates.

- `scripts/save_boot_stats.py`
  - Saves bootstrap statistics in reusable files.

- `scripts/maxent.py`
  - Script-level maximum entropy workflow.

- `scripts/run_maxent.py`
  - Runs a standard MaxEnt analysis workflow.

- `scripts/run_maxent_anneal.py`
  - Runs MaxEnt with annealing-related options.

- `scripts/run_maxent_phoenix.py`
  - Phoenix-cluster-oriented MaxEnt runner.

- `scripts/plot_JNJN.py`
  - Plots `JNJN` or related current-correlation curves with uncertainties.

- `scripts/plot_best_mu_vs_T.py`
  - Plots selected/best chemical potential versus temperature.

- `scripts/plot_charge_order.py`
  - Plots charge-order observables.

- `scripts/plot_compressibility_from_best_mu.py`
  - Computes and plots compressibility using best-mu simulation directories.

- `scripts/plot_compressibility_from_n_mu.py`
  - Computes and plots charge compressibility from density versus chemical potential.

- `scripts/plot_dos.py`
  - Plots density-of-states data, typically after analytic continuation.

- `scripts/plot_double_occ.py`
  - Plots double occupancy.

- `scripts/s_wave_pairing.py`
  - Computes onsite s-wave pairing structure-factor estimates from `pair_sw` and double occupancy.

- `scripts/data_analysis.py`
  - Script-level analysis helper or local analysis entry point.

- `scripts/run_stack_owners.sh`
  - Runs stack jobs with owner/worker-style organization.

- `scripts/run_stack_simes.sh`
  - Runs stack-based simulations.

- `scripts/multi_dir_push_stack.sh`
  - Collects simulation files from multiple directories into stack files.

- `scripts/multi_dir_submit_sbatch.sh`
  - Submits multiple run directories to an sbatch scheduler.

### `scripts/mu_tuning_coarse/`

- `scripts/mu_tuning_coarse/gen_all.sh`
  - Top-level coarse mu-tuning generation workflow.

- `scripts/mu_tuning_coarse/gen_sim_files.sh`
  - Generates HDF5 simulation files for coarse mu tuning.

- `scripts/mu_tuning_coarse/get_all_mu.sh`
  - Collects chemical-potential estimates across coarse tuning runs.

- `scripts/mu_tuning_coarse/get_mu.sh`
  - Extracts or computes chemical-potential information for one run/set.

- `scripts/mu_tuning_coarse/mu_tuning_gen_dir.py`
  - Creates the coarse mu-tuning directory structure.

- `scripts/mu_tuning_coarse/repush_all.sh`
  - Re-pushes coarse tuning jobs into stack/workflow files.

- `scripts/mu_tuning_coarse/run_stack_owners.sh`
  - Runs coarse tuning stack jobs.

- `scripts/mu_tuning_coarse/sweep_state.sh`
  - Inspects sweep progress/state for coarse tuning runs.

### `scripts/mu_tuning_fine/`

- `scripts/mu_tuning_fine/gen_all.sh`
  - Top-level fine mu-tuning generation workflow.

- `scripts/mu_tuning_fine/gen_dir.py`
  - Creates fine mu-tuning directory structures and copies workflow scripts.

- `scripts/mu_tuning_fine/gen_sim_files.sh`
  - Generates HDF5 simulation files for fine mu tuning.

- `scripts/mu_tuning_fine/get_all_mu.sh`
  - Collects fine chemical-potential estimates across runs.

- `scripts/mu_tuning_fine/get_mu.sh`
  - Extracts or computes chemical-potential information for a fine tuning run/set.

- `scripts/mu_tuning_fine/repush_all.sh`
  - Re-pushes fine tuning jobs into stack/workflow files.

- `scripts/mu_tuning_fine/run_stack_owners.sh`
  - Runs fine tuning stack jobs.

- `scripts/mu_tuning_fine/sweep_state.sh`
  - Inspects sweep progress/state for fine tuning runs.

### `scripts/wen_high_T_expansion/`

- `scripts/wen_high_T_expansion/Makefile`
  - Build recipe for the high-temperature-expansion helper program.

- `scripts/wen_high_T_expansion/main_tp0_all.cpp`
  - C++ high-temperature-expansion calculation for the `tp=0` workflow.

- `scripts/wen_high_T_expansion/ht_moments`
  - Built or executable helper for high-temperature moments.

- `scripts/wen_high_T_expansion/U8-12tp0.ipynb`
  - Notebook artifact for high-temperature-expansion exploration/analysis.

- `scripts/wen_high_T_expansion/U-6_6x6_tp0_nflux0_holedoping_highT_cmds.txt`
  - Command list for high-temperature-expansion runs.

- `scripts/wen_high_T_expansion/U-6_n0p1_o9.txt` through `scripts/wen_high_T_expansion/U-6_n1_o9.txt`
  - High-temperature-expansion output or tabulated result files for selected dopings.

- `scripts/wen_high_T_expansion/high-temperature-expansion/main.cpp`
  - Additional C++ high-temperature-expansion implementation.

- `scripts/wen_high_T_expansion/high-temperature-expansion/go8_n1.sh`
  - Run helper for a specific high-temperature-expansion setting.

- `scripts/wen_high_T_expansion/high-temperature-expansion/gocheckU6.sh`
  - Check/run helper for the `U=6` high-temperature-expansion setting.

- `scripts/wen_high_T_expansion/high-temperature-expansion/U8tp0_8_n1`, `scripts/wen_high_T_expansion/high-temperature-expansion/U8tp0_9_n1`, `scripts/wen_high_T_expansion/high-temperature-expansion/U10tp0_8_n1`, `scripts/wen_high_T_expansion/high-temperature-expansion/U10tp0_9_n1`, `scripts/wen_high_T_expansion/high-temperature-expansion/U12tp0_8_n1`, `scripts/wen_high_T_expansion/high-temperature-expansion/U12tp0_9_n1`, `scripts/wen_high_T_expansion/high-temperature-expansion/checkU6`, `scripts/wen_high_T_expansion/high-temperature-expansion/a`
  - Built executables or generated helper binaries/data for high-temperature-expansion runs.

### `build/`

- `build/Makefile`
  - Main build file for the C DQMC executables.

- `build/Makefile_cplx`
  - Complex-number build configuration.

- `build/Makefile.icx`
  - Intel `icx` build configuration.

- `build/gcc.imkl.Makefile`
  - GCC plus Intel MKL build configuration.

- `build/aocc.Makefile`
  - AOCC compiler build configuration.

- `build/colab.Makefile`
  - Colab-oriented build configuration.

- `build/cori.Makefile`
  - NERSC Cori-oriented build configuration.

- `build/mobius.Makefile`
  - Mobius-cluster-oriented build configuration.

- `build/perlmt-cpu.Makefile`
  - Perlmutter CPU build configuration.

- `build/build_rc_amd.sh`
  - AMD-platform build helper.

- `build/build_rc_colab.sh`
  - Colab build helper.

- `build/build_rc_icx.sh`
  - Intel `icx` build helper.

- `build/build_rc_mobius.sh`
  - Mobius build helper.

- `build/build_rc_pcpu.sh`
  - Perlmutter CPU build helper.
