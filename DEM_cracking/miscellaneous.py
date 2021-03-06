# coding: utf-8
from dolfin import *
import numpy as np
from numpy.linalg import norm
from scipy.sparse import dok_matrix,csr_matrix

def local_project(v, V, u=None):
    """Element-wise projection using LocalSolver"""
    dv = TrialFunction(V)
    v_ = TestFunction(V)
    a_proj = inner(dv, v_)*dx
    b_proj = inner(v, v_)*dx
    solver = LocalSolver(a_proj, b_proj)
    solver.factorize()
    if u is None:
        u = Function(V)
        solver.solve_local_rhs(u)
        return u
    else:
        solver.solve_local_rhs(u)
        return

def mass_matrix(rho_):
    if problem.d_ == problem.dim: #vectorial problem
        one = Constant(np.ones(problem.dim)) #to get the diagonal
    elif problem.d == 1: #scalar problem
        one = Constant(1.) #to get the diagonal

    #original mass matrix
    u_DG = TrialFunction(problem.DG)
    v_DG = TestFunction(problem.DG)
    M = rho_ * inner(u_DG,v_DG) * dx
    res = assemble(action(M, one)).get_local()
    res.resize(problem.nb_dof_DEM)

    return res

def gradient_matrix(problem):
    """Creates a matrix computing the cell-wise gradient from the facet values stored in a Crouzeix-raviart FE vector."""
    vol = CellVolume(problem.mesh)

    #variational form gradient
    u_CR = TrialFunction(problem.CR)
    Dv_DG = TestFunction(problem.W)
    a = inner(grad(u_CR), Dv_DG) / vol * dx
    A = assemble(a)
    row,col,val = as_backend_type(A).mat().getValuesCSR()
    return csr_matrix((val, col, row))

def DEM_interpolation(self, func):
    """Interpolates a function or expression to return a DEM vector containg the interpolation."""

    return self.DEM_to_DG.T * local_project(func, self.DG_0).vector().get_local() + self.trace_matrix.T * local_project(func, self.CR).vector().get_local()

def assemble_volume_load(load, problem):
    v = TestFunction(problem.DG_0)
    form = inner(load, v) * dx
    L = assemble(form)
    return problem.DEM_to_DG.T * L

def schur_matrices(self):
    aux = list(np.arange(self.nb_dof_cells))
    aux_bis = list(np.arange(self.nb_dof_cells, self.nb_dof_DEM))

    #Get non Dirichlet values
    mat_not_D = dok_matrix((self.nb_dof_cells, self.nb_dof_DEM))
    for (i,j) in zip(range(mat_not_D.shape[0]),aux):
        mat_not_D[i,j] = 1.

    #Get Dirichlet boundary conditions
    mat_D = dok_matrix((self.nb_dof_DEM - self.nb_dof_cells, self.nb_dof_DEM))
    for (i,j) in zip(range(mat_D.shape[0]),aux_bis):
        mat_D[i,j] = 1.
    return mat_not_D.tocsr(), mat_D.tocsr()

def schur_complement(self, A):
    """ Returns the matrices of the Schur complement to remove the vqlues of Dirichlet dofs impose strongly. """
    
    #A_D = self.mat_D * A * self.mat_D.T
    A_not_D = self.mat_not_D * A * self.mat_not_D.T
    B = self.mat_not_D * A * self.mat_D.T
    
    return A_not_D,B

def output_stress(problem, sigma=grad, eps=grad):
    vol = CellVolume(problem.mesh)
    Du_DG = TrialFunction(problem.W)
    Dv_DG = TestFunction(problem.W)
    
    a = inner(sigma(eps(Du_DG)), Dv_DG) / vol * dx
    A = assemble(a)
    row,col,val = as_backend_type(A).mat().getValuesCSR()
    mat_stress = csr_matrix((val, col, row))
    
    return mat_stress

def output_strain(problem, eps=grad):
    vol = CellVolume(problem.mesh)
    Du_DG = TrialFunction(problem.W)
    Dv_DG = TestFunction(problem.W)
    
    a = inner(eps(Du_DG), Dv_DG) / vol * dx
    A = assemble(a)
    row,col,val = as_backend_type(A).mat().getValuesCSR()
    mat_stress = csr_matrix((val, col, row))
    
    return mat_stress

def complete_solution(self, u_reduced, u_D):
    return self.mat_not_D.T * u_reduced + self.trace_matrix.T * local_project(u_D, self.CR).vector().get_local()
