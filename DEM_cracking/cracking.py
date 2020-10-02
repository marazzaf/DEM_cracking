#coding: utf-8
import numpy as np
from DEM_cracking.facet_reconstruction import bary_coord
from scipy.sparse import lil_matrix,dok_matrix
import networkx as nx

def adapting_after_crack(problem, cracking_facets, already_cracked_facets):
    impacted_facets = adapting_graph(problem, cracking_facets)
    adapting_facet_reconstruction(problem, cracking_facets, already_cracked_facets, impacted_facets)
    adapting_grad_matrix(problem, cracking_facets)
    return

def adapting_graph(problem, cracking_facets):
    impacted_facets = set()
    #Modifying connectivity graph
    for f in cracking_facets:
        n1,n2 = problem.facet_num.get(f) #n1 : plus, n2 : minus    
        #retrieving facets impacted by rutpure:
        impacted_facets.update(problem.Graph[n1][n2]['recon']) #impacted facets will have a new CR reconstruction
        ex_dofs = problem.Graph[n1][n2]['dof_CR']
        ex_num = problem.Graph[n1][n2]['num']
        ex_bary = problem.Graph[n1][n2]['barycentre']
        ex_normal = problem.Graph[n1][n2]['normal']
        ex_measure = problem.Graph[n1][n2]['measure']
        ex_vertices = problem.Graph[n1][n2]['vertices']
        ex_pen = problem.Graph[n1][n2]['pen_factor']
        
        #removing link between the two cell dofs
        problem.Graph.remove_edge(n1,n2)
        
        #adding the new facet dofs
        problem.Graph.add_node(problem.nb_dof_cells // problem.d + f, pos=ex_bary, sign=int(1), vertices=np.array([])) #linked with n1
        problem.Graph.add_node(-problem.nb_dof_cells // problem.d - f, pos=ex_bary, sign=int(-1), vertices=np.array([])) #linked with n2

        #adding the connectivity between cell dofs and new facet dofs
        problem.Graph.add_edge(n1, problem.nb_dof_cells // problem.d + f, num=ex_num, dof_CR=ex_dofs, measure=ex_measure, barycentre=ex_bary, normal=ex_normal, breakable=False, vertices=ex_vertices, pen_factor = ex_pen)
        problem.facet_num[f] = [n1]
        new_dof_CR = list(np.arange(problem.nb_dof_CR, problem.nb_dof_CR+problem.d))
        problem.Graph.add_edge(-problem.nb_dof_cells // problem.d - f, n2, num=problem.nb_dof_CR//problem.d, dof_CR=new_dof_CR, measure=ex_measure, barycentre=ex_bary, normal=ex_normal, breakable=False, vertices=ex_vertices, pen_factor = ex_pen)
        problem.nb_dof_CR += problem.d
        problem.facet_num[-f] = [n2]

    return impacted_facets #will be used to update CR reconstruction

def adapting_facet_reconstruction(problem, cracking_facets, already_cracked_facets, impacted_facets):
    #Modifying matrix passage_CR
    problem.DEM_to_CR.resize((problem.nb_dof_CR,problem.nb_dof_DEM))
    passage_CR_new = problem.DEM_to_CR.tolil()
    

    tetra_coord_bary = dict()
    tetra_coord_num = dict()
    #fill rows for new dof
    #Putting ones in new facet dofs and putting 0 where there were barycentric reconstructions
    for f in cracking_facets:
        n1 = problem.facet_num.get(f)[0]
        n2 = problem.facet_num.get(-f)[0]
        num_global_ddl_1 = problem.Graph[n1][f + problem.nb_dof_cells // problem.d]['dof_CR']
        num_global_ddl_2 = problem.Graph[-f - problem.nb_dof_cells // problem.d][n2]['dof_CR']
            
        #deleting previous barycentric reconstruction
        passage_CR_new[num_global_ddl_1[0], :] = np.zeros(passage_CR_new.shape[1])
        if problem.d >= 2: #deuxième ligne
            passage_CR_new[num_global_ddl_1[1], :] = np.zeros(passage_CR_new.shape[1])
        if problem.d == 3: #troisième ligne
            passage_CR_new[num_global_ddl_1[2], :] = np.zeros(passage_CR_new.shape[1])
        #recomputing the CR reconstruction
        coord_bary_1,coord_num_1,connectivity_recon_1 = bary_coord(f, problem)
        coord_bary_2,coord_num_2,connectivity_recon_2 = bary_coord(-f, problem)

        #Filling-in the new reconstruction
        for i1,j1,i2,j2 in zip(coord_num_1,coord_bary_1,coord_num_2,coord_bary_2):
            passage_CR_new[num_global_ddl_1[0],i1[0]] += j1
            passage_CR_new[num_global_ddl_2[0],i2[0]] += j2 
            if problem.d >= 2:
                passage_CR_new[num_global_ddl_1[1],i1[1]] += j1
                passage_CR_new[num_global_ddl_2[1],i2[1]] += j2
            if problem.d == 3:
                passage_CR_new[num_global_ddl_1[2],i1[2]] += j1
                passage_CR_new[num_global_ddl_2[2],i2[2]] += j2

    impacted_facets.difference_update(already_cracked_facets) #removing already cracked facets from the set of facets that need a new CR reconstruction

    #The connectivity recon will be recomputed. Thus retrieving the num of the facet from the potentially impacted. Will be upadted afterwards.
    for (u,v,r) in problem.Graph.edges(data='recon'):
        if r != None:
            r.difference_update(impacted_facets)

    #computing the new CR reconstruction for impacted facets
    for f in impacted_facets:
        #if len(face_num.get(g)) > 1: #facet not on boundary otherwise reconstruction does not change
        coord_bary,coord_num,connectivity_recon = bary_coord(f, problem)
        tetra_coord_bary[f] = coord_bary
        tetra_coord_num[f] = coord_num

        #updating the connectivity_recon in the graph. Adding the new connectivity recon in graph.
        for k in connectivity_recon:
            if(len(problem.facet_num.get(k))) == 2:
                n1,n2 = problem.facet_num.get(k)
                problem.Graph[n1][n2]['recon'].add(f)

    #Putting-in the new barycentric coordinates for inner facet reconstruction that changed
    for f in impacted_facets:
        if len(problem.facet_num.get(f)) > 1: #facet not on boundary
            n1,n2 = problem.facet_num.get(f)
            num_global_ddl = problem.Graph[n1][n2]['dof_CR']
        else: #facet on boundary
            n = problem.facet_num.get(f)[0]
            num_global_ddl = problem.Graph[n][f + problem.nb_dof_cells // problem.d]['dof_CR']
        #erasing previous values
        passage_CR_new[num_global_ddl[0],:] = np.zeros(passage_CR_new.shape[1])
        if problem.d >= 2:
            passage_CR_new[num_global_ddl[1],:] = np.zeros(passage_CR_new.shape[1])
        if problem.d == 3:
            passage_CR_new[num_global_ddl[2],:] = np.zeros(passage_CR_new.shape[1])
            #Putting new values in
        for i,j in zip(tetra_coord_num.get(f),tetra_coord_bary.get(f)):
            passage_CR_new[num_global_ddl[0],i[0]] += j 
            if problem.d >= 2:
                passage_CR_new[num_global_ddl[1],i[1]] += j
            if problem.d == 3:
                passage_CR_new[num_global_ddl[2],i[2]] += j

    #Optimization
    problem.DEM_to_CR = passage_CR_new.tocsr()
    problem.DEM_to_CR.eliminate_zeros()

    return

#What about mat_D and mat_not_D ??????????

def adapting_grad_matrix(problem, cracking_facets):
    #Modifying the gradient reconstruction matrix
    #No renumbering because uses CR dofs and not ccG dofs !!!
    problem.mat_grad.resize((problem.mat_grad.shape[0],problem.nb_dof_CR))
    mat_grad_new = problem.mat_grad.tolil() #only changes for cells having a facet that broke
    for f in cracking_facets:
        #first newly facet dof and associated cell
        c1 = problem.facet_num[f][0]
        mat_grad_new[c1 * problem.d * problem.dim : (c1+1) * problem.d * problem.dim, :] = local_gradient_matrix(c1, problem)
        c2 = problem.facet_num[-f][0]
        mat_grad_new[c2 * problem.d * problem.dim : (c2+1) * problem.d * problem.dim, :] = local_gradient_matrix(c2, problem)

    problem.mat_grad = problem.mat_grad.tocsr()
    
    return

def out_cracked_facets(folder,num_computation, num_output, cracked_facets_vertices, dim_): #Sortie au format vtk
    crack = open('%s/crack_%i_%i.vtk' % (folder,num_computation,num_output), 'w')
    nb_facets = len(cracked_facets_vertices)

    #header of vtk file
    crack.write("# vtk DataFile Version 3.0\n")
    crack.write("#Simulation Euler\n")
    crack.write("ASCII\n")
    crack.write('\n') #saut de ligne
    crack.write("DATASET UNSTRUCTURED_GRID\n")
    crack.write("POINTS %i DOUBLE\n" % (dim_ * nb_facets))

    nb_vertex = 0
    for f in cracked_facets_vertices:
        for ll in f:
            if dim_ == 3:
                crack.write('%.15f %.15f %.15f\n' % (ll[0], ll[1], ll[2]))
            elif dim_ == 2:
                crack.write('%.15f %.15f 0.0\n' % (ll[0], ll[1]))
            nb_vertex += dim_
    crack.write("\n")

    point_tmp = 0;
    crack.write("CELLS %i %i\n" % (nb_facets, (dim_+ 1) * nb_facets))
    for i in range(nb_facets):
        crack.write('%i ' % dim_)
        for i in range(dim_):
            crack.write('%i ' % point_tmp)
            point_tmp += 1
        crack.write('\n')
    crack.write("\n")
    #
    crack.write("CELL_TYPES %i\n" % nb_facets)
    for i in range(nb_facets):
        if dim_ == 3:
            crack.write('5\n') #triangle
        elif dim_ == 2:
            crack.write('3\n') #edge #mettre 4 ?
    #
    crack.write("\n")
    crack.close()
    return

def local_gradient_matrix(num_cell, problem):
    res = lil_matrix((problem.d * problem.dim, problem.nb_dof_CR))
    bary_cell = problem.Graph.nodes[num_cell]['pos']
    vol = problem.Graph.nodes[num_cell]['measure']
    for (u,v) in nx.edges(problem.Graph, nbunch=num_cell): #getting facets of the cell (in edges)
        f = problem.Graph[u][v] #edge corresponding to the facet
        normal = f['normal']
        normal = normal * np.sign( np.dot(normal, f['barycentre'] - bary_cell) ) #getting the outer normal to the facet with respect to the cell
        dofs = f['dof_CR'] #getting the right number of the dof corresponding to the facet
        aux = np.zeros((problem.d * problem.dim, problem.d)) #local contribution to the gradient for facet
        if problem.d > 1: #vectorial problem
            for k in range(problem.d):
                for j in range(problem.d):
                    aux[k*problem.dim+j,k] = normal[j]
        else: #scalar problem
            for i in range(len(normal)):
                aux[i,0] = normal[i]
        aux = f['measure'] / vol * aux
        
        res[:, dofs[0] : dofs[problem.d-1] + 1] = aux #importation dans la matrice locale de la cellule
    return res

def removing_penalty(problem, cracking_facets):
    dofmap_tens_DG_0 = problem.W.dofmap()
    
    #creating jump matrix
    mat_jump_1 = dok_matrix((problem.nb_dof_CR,problem.nb_dof_DEM))
    mat_jump_2 = dok_matrix((problem.nb_dof_CR_,problem.nb_dof_grad))

    for f in cracking_facets: #utiliser facet_num pour avoir les voisins ?
        assert len(problem.facet_num.get(f)) == 2 
        c1,c2 = problem.facet_num.get(f) #must be two otherwise external facet broke
        num_global_ddl = problem.Graph[c1][c2]['dof_CR']
        coeff_pen = problem.Graph[c1][c2]['pen_factor']
        pos_bary_facet = problem.Graph[c1][c2]['barycentre'] #position barycentre of facet
        #filling-in the DG 0 part of the jump
        mat_jump_1[num_global_ddl[0]:num_global_ddl[-1]+1,problem.d * c1 : (c1+1) * problem.d] = np.sqrt(coeff_pen)*np.eye(problem.d)
        mat_jump_1[num_global_ddl[0]:num_global_ddl[-1]+1,problem.d * c2 : (c2+1) * problem.d] = -np.sqrt(coeff_pen)*np.eye(problem.d)

        for num_cell,sign in zip([c1,c2],[1., -1.]):
            #filling-in the DG 1 part of the jump...
            pos_bary_cell = problem.Graph.nodes[num_cell]['pos']
            diff = pos_bary_facet - pos_bary_cell
            pen_diff = np.sqrt(coeff_pen)*diff
            tens_dof_position = dofmap_tens_DG_0.cell_dofs(num_cell)
            for num,dof_CR in enumerate(num_global_ddl):
                for i in range(dim_):
                    mat_jump_2[dof_CR,tens_dof_position[(num % problem.d)*problem.d + i]] = sign*pen_diff[i]

    return mat_jump_1.tocsr(), mat_jump_2.tocsr()

def cracking_criterion(problem):
    return 
