# Diagnostics Playbook

This playbook includes diagnostics for common numerical issues while running DQMC simulations using the given project.

## File generation & parameter input

### Fermion sign problem

There is no free lunch, and the hidden “gotcha” of the DQMC algorithm lies in the fermion sign problem, i.e. the fact that the weights $w_{s}$ are not always positive semi-definite. This can be fundamentally attributed to negative signs introduced by braiding fermion world lines. For most generic models, parameters, lattices, and choice of Hubbard-Stratonovich decomposition (or more generally, bosonization procedure), the DQMC simulation is “sign-problem-full”.

What’s worse, the fermion sign problem is exponentially bad, in the sense that if system size is $N$ and inverse temperature is $\beta$, then the average sign $\left< s \right>$ exponentially decays as $\left< s \right> \propto e^{-\left( \# \right) N}$ and $\left< s \right> \propto e^{-\left( \# \right) \beta }$ for sufficiently large lattice size and sufficiently low temperature. When the average sign $\left< s \right>$ is small, applying sign reweighting will

1. Introduce bias. Assuming $\left< Os \right>_{\mathrm{MC} ,\left\vert w\left( s \right) \right\vert}$ and $\left< s \right>_{\mathrm{MC} ,\left\vert w\left( s \right) \right\vert}$ are each individually normally distributed, their ratio is not necessarily normally distributed. In pratice, we always correct for this bias using jackknife or bootstrap resampling.

2. Amplify statistical fluctuations. To acquire meaningful information from a Monte Carlo algorithm, we need to average over a large enough number $N_{s}$ of configurations $s$ to obtain an expectation value $\left< A \right>$ with some relative statistical error $\epsilon =\frac{\sigma A}{\left< A \right>}$, where $\epsilon $ is small. However, as $\left< s \right>$ becomes exponentially small, its relative error $\frac{\sigma s}{\left< s \right>}$ blows up, which means the number of samples one must acquire to reach the desired error tolerance also grows exponentially.

Due to the second point, the exponentially bad fermion sign problem prevents us from obtaining informative simulation data in many cases of physical interest. It’s important to note that the fermion sign is a property of both the model Hamiltonian and the representation we choose to simulate it. A given model Hamiltonian may not admit a sign-free representation, and if a model does admit a sign-free representation, it’s not guaranteed that we are clever enough to find it. As the fermion sign problem is believed to be NP-hard, we don’t expect a general “solution” to the fermion sign problem to exist. Nevertheless, it is possible to reduce or completely remove the sign problem for DQMC simulations of some classes of non-generic Hamiltonians. On the other hand, once we fix the simulation scheme, e.g. to be of DQMC type, then we find the presence and severity of the fermion sign problem are correlated with physical properties of a model Hamiltonian.

### Trotter error

The parameter $L$ is some integer defined by $\beta = L\Delta \tau$ , where $\Delta \tau$ is chosen to be a small number. $L$ is referred to as the number of imaginary time slices and $\Delta \tau$ is referred to as the imaginary time discretization. Technically, DQMC is exact only when $\Delta \tau \to 0$. Empirically, the associated systematic error for $\Delta \tau > 0$, known as the Trotter error, is negligibly small for $\left( \Delta \tau \right)^{2} U t \leqslant \frac{1}{8}$.

### Number of sweeps

DQMC simulations require enough sweeps for thermalization of the system and obtaining reasonable results. Small value of number of warm-up sweeps can result in the first few measured bins still retain the initial state memory, which manifests as: the early part of the time series being significantly higher or lower than normal; the running mean fluctuating continuously with the number of data points discarded; and significant disparity between the mean values of the first and second halves. Systems with larger on-site interaction $\left| U \right|$ or under lower temperature generally needs more sweeps to warm-up. Simple warm-up check could be done with scripts such as ```dqmc-dev/scripts/check_warm.py```.

Provided that the thermalisation is complete, increasing the number of sweeps in the formal measurement can reduce the error bar within a certain range.

## $\mu $-tuning

The convention for the Hamiltonian of Hubbard model in the project is shifted potential, i.e. $U \left(n_{\uparrow}- \frac{1}{2} \right) \left(n_{\downarrow}- \frac{1}{2} \right)$, meaning that the chemical potential at half-filling $n = 1$ is $\mu = 0$.

Since we are in the grand-canonical ensemble, we need to select the correct $\mu$ value to simulate the correct target filling $n$.

The $\mu$-tuning process are usually splitted into 2 steps: a coarse $\mu$ grid and then a fine $\mu$ grid based on the values from the coarse grid. We can also run a single $\mu$-tuning sweep over a fine grid on a relatively large scale instead of doing both coarse and fine tuning.

### Determination of target filling $n$

For a single-band spinful Hubbard model, $n$ ranges from $0$ to $2$, and half filling corresponds to $n = 1$. Hole doping is usually defined as $p = 1 - n$, while electron doping corresponds to $n - 1$. The playbook should always state which convention is used.

Since the simulation is performed in the grand-canonical ensemble, $n$ is not fixed directly by the input. Instead, the user fixes $\mu $ and measures the resulting density. Therefore, $\mu $-tuning should be treated as a root-finding problem for $f\left( \mu \right) = n\left( \mu \right) - n_{\mathrm{target}}$. Generally speaking, for a system with $n \geqslant 0.5$, a production run could be considered correctly tuned only if $\left| n_{\mathrm{measured}} - n_{\mathrm{target}}\right| \leqslant 0.01$, i.e. the $n$ obtained from the best $\mu $ value should at least be accurate up to the second digit.

Charge compressibility is defined as $\chi = \frac{dn}{d \mu }$, which should normally be some positive number. Therefore, increasing $\mu $ generally leads to an increase in $n$.

### Step size & scanning range of chemical potential $\mu $

The $\mu $ grid should be chosen based on the expected slope $\frac{dn}{d \mu }$, i.e. the compressibility. In regions where $n$ changes rapidly with $\mu $, a smaller $\mu $ step is needed. In incompressible or weakly compressible regimes, such as near a Mott plateau, a larger $\mu $ interval may be needed to see a visible density change.

When doing $\mu $-tuning, a range of $\mu $ that brackets the $\mu $ correspond to the target filling $n_{\mathrm{target}}$ allows for a relatively accurate prediction of $\mu$ using interpolation. Therefore, the $\mu $ range of coarse tuning should try to bracket the final $\mu $ we want. If possible, this can be achieved by comparing the results with those from $\mu$-tuning on datasets with similar parameters; for example, if all other conditions remain constant, the $\mu$ value varies little with system size, so the range of $\mu$ values used for $\mu$-tuning can be determined by comparing the results with those from datasets that differ only in lattice size.

When it comes to fine-tuning, the step size for $\mu$ should not be too small. An excessively fine $\mu$ grid may be overwhelmed by statistical errors, thereby yielding non-physical results. When performing fine-tuning around the $\mu$ values predicted by coarse-tuning, a reasonable step size for $\mu$ is $0.05–0.1$.

## Analytic continuation

### Binning

MaxEnt does not merely require error bars for each $\tau$ point; ideally, it requires the covariance matrix of the entire imaginary-time correlator. This covariance matrix is estimated from bin samples. If the number of bins is insufficient, the covariance matrix will become singular, and the $\chi^{2}$ term in MaxEnt cannot be properly defined. A typical number of bins to get reasonable MaxEnt results is $n_{\mathrm{bin}} = 2L$.
