from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .oracle import MVSKOracle
from .simplex import alpha_max_for_simplex, project_simplex, projected_kkt_residual, tangent_basis


@dataclass(frozen=True)
class YANDConfig:
    max_iter: int = 120
    tolerance: float = 1e-6
    tau: float = 1e-8
    regularization: float = 1e-4
    max_regularization: float = 1e2
    projected_trial_steps: tuple[float, ...] = (0.02, 0.1, 0.4)
    use_pcg_threshold: int = 120
    pcg_max_iter: int = 25
    pcg_tol: float = 1e-3
    # "auto" uses the exact-trace log-determinant correction in direct mode and omits it in
    # matrix-free PCG mode; "exact" forces it, "off" disables it everywhere.
    logdet_correction: str = "auto"


@dataclass
class YANDResult:
    weights: np.ndarray
    objective: float
    kkt_residual: float
    iterations: int
    converged: bool
    method: str
    history: list[dict[str, float]] = field(default_factory=list)


class YANDMVSKOptimizer:
    """YAND-MVSK solver following Algorithm 1 of arXiv:2604.25378.

    Each iteration runs the paper's four blocks on the simplex:

    1. Oracle block: exact sample-oracle evaluation of f, its gradient, and the reduced gradient
       g_bar = U^T grad through the centered return matrix (no comoment tensors).
    2. Affine-normal block: normalize the reduced gradient into nu, build the Householder frame Q
       with Q^T nu = 0, assemble the regularized tangent system H_{T,lambda} and the exact
       log-determinant correction vector a, then solve
           u = H_{T,lambda}^{-1} (h - (||g_bar|| / n) a),   d_y = Q u - nu,   d = U d_y.
       Because Q^T g_bar = 0, the direction always satisfies g^T d = -||g_bar|| < 0, i.e. it is a
       guaranteed descent direction whose tangential twist adapts to level-set curvature.
    3. Quartic step block: exact line search on [0, alpha_max] using the closed-form quartic
       restriction of the MVSK objective (sample power sums, cubic root finding).
    4. Boundary block (face continuation): coordinates pinned at the interior margin tau whose
       multipliers point outward are treated as an active face; the affine-normal system is then
       assembled on the free coordinates only, so boundary solutions keep Newton-type steps
       instead of stalling at alpha_max = 0. Pinned coordinates whose reduced gradient favors
       re-entry are released back into the free set.

    The exact-trace correction uses the factorization H_T = (1/T) M^T diag(psi''(z)) M with
    M = A U Q on the current face, which yields
        a = (1/T) M^T (psi'''(z) ∘ diag(M H_{T,lambda}^{-1} M^T))
    without any explicit third-order tensor. In matrix-free PCG mode the correction is omitted by
    default (config.logdet_correction="auto"), matching a Newton-type tangent solve.
    """

    def __init__(self, oracle: MVSKOracle, config: YANDConfig | None = None):
        self.oracle = oracle
        self.config = config or YANDConfig()
        self.xref = np.ones(oracle.n, dtype=float) / oracle.n
        self._basis_cache: dict[int, np.ndarray] = {}

    def solve(self, x0: np.ndarray | None = None) -> YANDResult:
        n = self.oracle.n
        x = project_simplex(self.xref if x0 is None else x0, floor=self.config.tau)
        method = "pcg" if n >= self.config.use_pcg_threshold else "direct"
        active_tol = self.config.tau * 10.0
        history: list[dict[str, float]] = []

        for iteration in range(1, self.config.max_iter + 1):
            value, grad = self.oracle.value_grad(x)
            kkt = projected_kkt_residual(x, grad, tol=active_tol)
            history.append({"objective": value, "kkt_residual": kkt})
            if kkt <= self.config.tolerance:
                return YANDResult(x, value, kkt, iteration - 1, True, method, history)

            free = self._free_set(x, grad, active_tol)
            direction = None
            alpha_max = 0.0
            # Face-continuation loop: if the affine-normal step is blocked by coordinates sitting
            # exactly on the floor, pin them and reassemble the direction on the exposed face.
            while int(free.sum()) >= 2:
                direction = self._yand_direction(x, grad, free, method)
                if (
                    direction is None
                    or not np.all(np.isfinite(direction))
                    or np.linalg.norm(direction) <= 1e-14
                    or float(grad @ direction) >= 0.0
                ):
                    direction = None
                    break
                alpha_max = alpha_max_for_simplex(x, direction, tau=self.config.tau)
                if alpha_max > 1e-12:
                    break
                blocking = (x <= active_tol) & (direction < 0.0)
                if not np.any(blocking) or not np.any(free & blocking):
                    direction = None
                    break
                free = free & ~blocking

            x_next = x
            if direction is not None and alpha_max > 1e-12:
                alpha = self.oracle.exact_quartic_step(x, direction, alpha_max)
                if alpha > 0.0:
                    candidate = x + alpha * direction
                    displacement = float(np.abs(candidate - x).sum())
                    if displacement > 1e-12 and self.oracle.value(candidate) <= value:
                        x_next = candidate

            if x_next is x:
                x_next = self._projected_segment_step(x, value, grad)

            if np.min(x_next) < self.config.tau or abs(np.sum(x_next) - 1.0) > 1e-8:
                x_next = project_simplex(x_next, floor=self.config.tau)

            if np.linalg.norm(x_next - x, ord=1) <= 1e-13:
                break
            x = x_next

        value, grad = self.oracle.value_grad(x)
        kkt = projected_kkt_residual(x, grad, tol=active_tol)
        return YANDResult(
            weights=x,
            objective=value,
            kkt_residual=kkt,
            iterations=len(history),
            converged=kkt <= self.config.tolerance,
            method=method,
            history=history,
        )

    # ------------------------------------------------------------------ face bookkeeping

    def _free_set(self, x: np.ndarray, grad: np.ndarray, active_tol: float) -> np.ndarray:
        """Active-face estimate: pinned coordinates re-enter when their multiplier is negative."""

        free = x > active_tol
        if not np.any(free):
            return np.ones_like(free)
        lagrange = float(np.mean(grad[free]))
        return free | (grad < lagrange - 1e-15)

    def _projected_segment_step(self, x: np.ndarray, value: float, grad: np.ndarray) -> np.ndarray:
        """Fallback: exact line search along projected-gradient segments at several scales."""

        projected = grad - np.mean(grad)
        norm = float(np.linalg.norm(projected))
        if norm <= 1e-14:
            return x
        unit = projected / norm
        best_x, best_value = x, value
        for eta in self.config.projected_trial_steps:
            trial = project_simplex(x - eta * unit, floor=self.config.tau)
            segment = trial - x
            if np.linalg.norm(segment) <= 1e-14 or float(grad @ segment) >= 0.0:
                continue
            alpha = self.oracle.exact_quartic_step(x, segment, 1.0)
            if alpha <= 0.0:
                continue
            candidate = x + alpha * segment
            candidate_value = self.oracle.value(candidate)
            if candidate_value < best_value:
                best_x, best_value = candidate, candidate_value
        return best_x

    # ------------------------------------------------------------------ direction assembly

    def _face_basis(self, size: int) -> np.ndarray:
        if size not in self._basis_cache:
            self._basis_cache[size] = tangent_basis(size)
        return self._basis_cache[size]

    def _yand_direction(
        self, x: np.ndarray, grad: np.ndarray, free: np.ndarray, method: str
    ) -> np.ndarray | None:
        free_idx = np.flatnonzero(free)
        n_free = free_idx.size
        basis = self._face_basis(n_free)
        reduced_grad = basis.T @ grad[free_idx]
        grad_norm = float(np.linalg.norm(reduced_grad))
        if grad_norm <= 1e-14:
            return None
        nu = reduced_grad / grad_norm

        if n_free == 2:
            # The level-set tangent space on this face is empty: the YAND step is -nu itself.
            d_reduced = -nu
        else:
            householder = _householder_vector(nu)
            if method == "direct":
                tangent = self._direct_tangent_component(
                    x, nu, householder, grad_norm, free_idx, basis
                )
            else:
                tangent = self._pcg_tangent_component(x, nu, householder, free_idx, basis)
            if tangent is None:
                return None
            d_reduced = _apply_q(householder, tangent) - nu

        direction = np.zeros_like(x)
        direction[free_idx] = basis @ d_reduced
        return direction

    def _direct_tangent_component(
        self,
        x: np.ndarray,
        nu: np.ndarray,
        householder: np.ndarray,
        grad_norm: float,
        free_idx: np.ndarray,
        basis: np.ndarray,
    ) -> np.ndarray | None:
        """Exact-trace YAND tangent solve: u = H_{T,lambda}^{-1} (h - (||g||/n) a)."""

        z = self.oracle.a @ x
        curvature = self.oracle.psi_second(z)
        a_face = self.oracle.a[:, free_idx]

        # M = A U Q maps level-set tangent coordinates of the current face into sample space.
        frame = _apply_q_matrix(householder, nu.size)  # (n_free-1, n_free-2)
        m = a_face @ (basis @ frame)  # (T, n_free-2)
        h_t = (m.T * curvature) @ m / self.oracle.t
        h_t = 0.5 * (h_t + h_t.T)

        p = a_face @ (basis @ nu)
        h_vec = m.T @ (curvature * p) / self.oracle.t

        lam = self.config.regularization
        dim = h_t.shape[0]
        chol = None
        while lam <= self.config.max_regularization:
            try:
                chol = np.linalg.cholesky(h_t + lam * np.eye(dim))
                break
            except np.linalg.LinAlgError:
                lam *= 10.0
        if chol is None:
            return None

        rhs = h_vec
        if self.config.logdet_correction in ("auto", "exact"):
            # diag(M H_{T,lambda}^{-1} M^T) via one triangular solve against M^T.
            half = np.linalg.solve(chol, m.T)  # (n_free-2, T)
            leverage = np.einsum("jt,jt->t", half, half)
            correction = m.T @ (self.oracle.psi_third(z) * leverage) / self.oracle.t
            rhs = h_vec - (grad_norm / free_idx.size) * correction

        y = np.linalg.solve(chol, rhs)
        return np.linalg.solve(chol.T, y)

    def _pcg_tangent_component(
        self,
        x: np.ndarray,
        nu: np.ndarray,
        householder: np.ndarray,
        free_idx: np.ndarray,
        basis: np.ndarray,
    ) -> np.ndarray | None:
        """Matrix-free tangent solve through Hessian-vector products (correction omitted)."""

        n = self.oracle.n
        dim = nu.size - 1
        if dim <= 0:
            return np.zeros(0)

        def lift(coords: np.ndarray) -> np.ndarray:
            ambient = np.zeros(n)
            ambient[free_idx] = basis @ coords
            return ambient

        def restrict(ambient: np.ndarray) -> np.ndarray:
            return basis.T @ ambient[free_idx]

        def matvec(eta: np.ndarray) -> np.ndarray:
            lifted = lift(_apply_q(householder, eta))
            reduced = restrict(self.oracle.hvp(x, lifted))
            return _apply_qt(householder, reduced) + self.config.regularization * eta

        b = _apply_qt(householder, restrict(self.oracle.hvp(x, lift(nu))))

        y = np.zeros_like(b)
        r = b - matvec(y)
        p = r.copy()
        rs_old = float(r @ r)
        if rs_old <= 1e-24:
            return y
        for _ in range(self.config.pcg_max_iter):
            ap = matvec(p)
            denom = float(p @ ap)
            if abs(denom) <= 1e-18:
                break
            alpha = rs_old / denom
            y = y + alpha * p
            r = r - alpha * ap
            rs_new = float(r @ r)
            if np.sqrt(rs_new) <= self.config.pcg_tol * max(1.0, np.linalg.norm(b)):
                break
            p = r + (rs_new / rs_old) * p
            rs_old = rs_new
        return y


def _householder_vector(nu: np.ndarray) -> np.ndarray:
    """Householder vector v such that P = I - 2 vv^T/(v^T v) maps nu onto ±e1.

    The trailing columns of P then form an orthonormal frame Q with Q^T nu = 0.
    """

    v = nu.copy()
    v[0] += np.copysign(1.0, nu[0])
    norm = float(np.linalg.norm(v))
    if norm <= 1e-14:
        v = np.zeros_like(nu)
        v[0] = 1.0
        return v
    return v / norm


def _apply_q(v: np.ndarray, eta: np.ndarray) -> np.ndarray:
    """Compute Q eta = P [0; eta] without forming P."""

    padded = np.concatenate(([0.0], eta))
    return padded - 2.0 * v * float(v @ padded)


def _apply_qt(v: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Compute Q^T w = (P w)[1:] without forming P."""

    return (w - 2.0 * v * float(v @ w))[1:]


def _apply_q_matrix(v: np.ndarray, dim: int) -> np.ndarray:
    """Materialize Q = P[:, 1:] for the direct exact-trace configuration."""

    p = np.eye(dim) - 2.0 * np.outer(v, v)
    return p[:, 1:]
