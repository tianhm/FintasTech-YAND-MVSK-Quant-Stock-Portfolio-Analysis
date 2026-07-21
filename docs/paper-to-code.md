# Paper To Code: YAND-MVSK

This document maps *Yau's Affine-Normal Descent for Large-Scale Unrestricted Higher-Moment
Portfolio Optimization* (arXiv:2604.25378) onto the implementation in
`packages/quant_core/`. Equation references follow the paper's numbering.

## 1. Exact sample oracle (paper §4.1, Prop. 1, Eq. 2–5)

Store only the sample mean `mu` and the centered return matrix `A = R - 1 mu^T`; never build
covariance, coskewness, or cokurtosis tensors. With `z = A x`:

| Paper quantity | Formula | Code |
| --- | --- | --- |
| Objective `f(x)` (Eq. 2) | `-c1 mu^T x + (c2/T)Σz² - (c3/T)Σz³ + (c4/T)Σz⁴` | `MVSKOracle.value` |
| Gradient (Eq. 3) | `-c1 mu + (2c2/T)Aᵀz - (3c3/T)Aᵀz°² + (4c4/T)Aᵀz°³` | `MVSKOracle.value_grad` |
| Hessian action (Eq. 4) | `(1/T)Aᵀ(ψ''(z) ∘ Av)` | `MVSKOracle.hvp` |
| Third-order action (Eq. 5) | `(1/T)Aᵀ(ψ'''(z) ∘ Au ∘ Av)` | `MVSKOracle.third` |

where `ψ(s) = c2 s² - c3 s³ + c4 s⁴` is the scalar response (`psi_second` / `psi_third` expose its
derivatives). Every oracle call costs `O(Tn)` arithmetic and `O(T + n)` memory
(paper Corollary 4), versus `Θ(n³ + n⁴)` for explicit tensors.

## 2. Affine-normal direction on the simplex (paper §4.2, Algorithm 1)

The simplex is handled through reduced coordinates `x = x_ref + U y` with `U` an orthonormal basis
of the tangent space `{v : 1ᵀv = 0}` (`simplex.tangent_basis`). At each iterate:

1. Reduced gradient `ḡ = Uᵀ∇f(x)`, normal `ν = ḡ/‖ḡ‖₂`.
2. Householder frame `Q` with `QᵀQ = I`, `Qᵀν = 0`
   (`optimizer._householder_vector`, applied matrix-free via `_apply_q` / `_apply_qt`).
3. Tangent system `H_{T,λ} η = Qᵀ Uᵀ ∇²f(x) (U Q η) + λη` and normal load
   `h = Qᵀ Uᵀ ∇²f(x) (U ν)`.
4. Exact log-determinant correction vector `a` from the reduced third-order oracle, then

   ```text
   u = H_{T,λ}⁻¹ (h - (‖ḡ‖₂ / n) a),    d_y = Q u - ν,    d = U d_y.
   ```

Because `Qᵀḡ = 0`, the direction always satisfies `∇f(x)ᵀ d = -‖ḡ‖₂ < 0`: the affine-normal step
is a guaranteed descent direction whose tangential component adapts to level-set curvature.

**Exact-trace correction.** Using the curvature factorization `∇²f = (1/T) Aᵀ diag(ψ''(z)) A`
(paper Prop. 2), the tangent Hessian on the current face is `H_T = (1/T) Mᵀ diag(ψ''(z)) M` with
`M = A U Q`, and the log-determinant derivative reduces to

```text
a = (1/T) Mᵀ (ψ'''(z) ∘ diag(M H_{T,λ}⁻¹ Mᵀ)),
```

computed with one triangular solve against `Mᵀ` — no third-order tensor is ever formed
(`optimizer._direct_tangent_component`).

**Configurations.** Mirroring the paper's implementation split, `use_pcg_threshold` switches from
the direct Cholesky solve to a matrix-free conjugate-gradient tangent solve built purely on
Hessian-vector products (`_pcg_tangent_component`). In PCG mode the log-determinant correction is
omitted by default (`logdet_correction="auto"`), which corresponds to a Newton-type tangent step;
the exact-trace variant remains available for the direct configuration.

## 3. Quartic exact line search (paper §4.3, Prop. 5 / 22)

Along any tangent direction `d` with `w = A d`, the restricted objective is a univariate quartic
whose coefficients come from mixed sample power sums `s_rs = (1/T) Σ z^r w^s`, `r+s ≤ 4`
(`MVSKOracle.line_coefficients`). The exact minimizer on `[0, α_max]` checks the interval
endpoints plus the real roots of the cubic derivative (`MVSKOracle.exact_quartic_step`), with the
feasibility cap `α_max(x, d; τ) = min_{d_i<0} (x_i - τ)/(-d_i)` from Lemma 21
(`simplex.alpha_max_for_simplex`).

## 4. Boundary handling and face continuation (paper §4.3, Algorithm 1 lines 11–15)

Long-only optima frequently sit on faces of the simplex where some weights hit the interior
margin `τ`. The solver keeps Newton-type progress there instead of stalling:

- Coordinates at the floor whose multiplier points outward form the active face; the YAND system
  is reassembled on the free coordinates only (`_free_set`, face-aware `_yand_direction`).
- Pinned coordinates whose reduced gradient favors re-entry are released.
- If the assembled direction is still blocked at the floor, the blocking coordinates are pinned
  and the direction is recomputed on the newly exposed face (face-continuation loop in `solve`).
- As a safeguard, exact line search along projected-gradient segments at several scales replaces
  a failed step (`_projected_segment_step`).

Convergence is measured by the projected KKT residual for the long-only simplex
(`simplex.projected_kkt_residual`), reported per iteration in `YANDResult.history`.

## 5. Coefficients: CRRA calibration and convexity certificate (paper §5.3)

- `MVSKCoefficients.crra(gamma)` implements the standard fourth-order CRRA Taylor calibration
  `c = (1, γ/2, γ(γ+1)/6, γ(γ+1)(γ+2)/24)` used throughout the paper's benchmarks (γ = 6).
- `MVSKCoefficients.convexity_certified` implements the coefficient-only convexity test: `ψ'' > 0`
  everywhere iff `c2 > 0`, `c4 > 0`, and `3c3² < 8c2c4` — in that regime the MVSK objective is
  convex on the simplex regardless of the data map, so the reported KKT point is a global optimum.

## 6. What is deliberately out of paper scope

The screening, train/test research pipeline, MV/equal-weight baselines, backtest metrics, API,
and dashboard are this project's engineering additions, not part of the paper. Two solver-level
simplifications relative to the paper's large-scale configuration: PCG mode omits the
log-determinant correction by default, and the stall-recovery restart schedule (projected steps
0.045/0.02) is replaced by the multi-scale projected-segment safeguard above.

## 7. Research interpretation

The paper's empirical message is conditional, not magical: higher moments add value when the
return mandate leaves enough allocation freedom for skewness and kurtosis to reshape the payoff
distribution — and the appendix rolling-window checks show the MV/MVSK separation is
market-window dependent. This project therefore always compares MVSK against MV and equal-weight
baselines on a strict out-of-sample split, and reports realized skewness/kurtosis, KKT residual,
active share, effective assets, drawdown, and CVaR so that "MVSK won" claims can be interrogated
rather than assumed.
