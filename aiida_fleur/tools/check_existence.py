#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# Copyright (c), Forschungszentrum Jülich GmbH, IAS-1/PGI-1, Germany.         #
#                All rights reserved.                                         #
# This file is part of the AiiDA-FLEUR package.                               #
#                                                                             #
# The code is hosted on GitHub at https://github.com/JuDFTteam/aiida-fleur    #
# For further information on the license, see the LICENSE.txt file            #
# For further information please visit http://www.flapw.de or                 #
# http://aiida-fleur.readthedocs.io/en/develop/                               #
###############################################################################

"""
DO NOT USE, this is crab so far. The development was stoped because this is done 
with AiiDA 'caching' now.

Here are methods to check the existence of something in the database
example if a (successful) SCF with the same inputs exists

Since cashing is not there for data yet, and below are some basic querries I 
leave the code here for now.
"""
from __future__ import absolute_import
from aiida.plugins import DataFactory
from aiida.orm import QueryBuilder
from aiida.engine.calculation.job import CalcJob
from aiida.orm import Node


'''
def check_existence_calc(input_nodes, successful=True):
    """
    This methods checks in the database waether a certain type of node with the given
    input nodes already exists. If yes it returns the output nodes of that node.

    param: input_nodes : List of input nodes

    returns output nodes
    """
    #TODO: some checks and inputnodes could be parsed in different formats
    inputnodesuuid = [node.uuid for node in input_nodes]

    qb=QueryBuilder()
    qb.append(
       JobCalculation, tag='calc', project='*',
       filters={'state' : {'==':'FINISHED'}})

    for idx, uuid in enumerate(inputnodesuuid):
        qb.append(Node, input_of='calc', filters={'uuid':uuid}, 
                  tag='input_{}'.format(idx))

    qb.order_by({JobCalculation:'ctime'})
    res = qb.all()
    if res:
        return res[-1][0].get_outputs()
    else:
        return None

def check_existence_wf(input_nodes, successful=True):
    """
    This methods checks in the database waether a certain type of node with the given
    input nodes already exists. If yes it returns the output nodes of that node.

    param: input_nodes : List of input nodes

    returns output nodes
    """
    #TODO: some checks and inputnodes could be parsed in different formats
    inputnodesuuid = [node.uuid for node in input_nodes]

    qb=QueryBuilder()
    qb.append(
       JobCalculation, tag='calc', project='*',
       filters={'state' : {'==':'FINISHED'}})

    for idx, uuid in enumerate(inputnodesuuid):
        qb.append(Node, input_of='calc', filters={'uuid':uuid}, tag='input_{}'.format(idx))

    qb.order_by({JobCalculation:'ctime'})
    res = qb.all()
    if res:
        return res[-1][0].get_outputs()
    else:
        return None

'''
'''
def intersectlist(l1, l2):
    common = []
    for element in l1:
        if element in l2:
            common.append(element)
    return common

def check_existence_calc(input_nodes, successful=True):
    """
    This methods checks in the database waether a certain type of node with the given
    input nodes already exists. If yes it returns the output nodes of that node.

    param: input_nodes : List of input nodes

    returns output nodes
    """
    inputnodesuuid = [node.uuid for node in input_nodes]
    overall_results = []

    for node in inputnodesuuid:
        suc = successful
        qb=QueryBuilder()
        qb.append(Node,
            filters={
                'uuid' : {'==': node},
            },
            tag='input')
        if suc:
            qb.append(
                JobCalculation,
                filters={
                    'state' : {'==':'FINISHED'}
                },
                output_of='input')
        else:
            qb.append(
                JobCalculation,
                output_of='input',
                project=['uuid'])
        res = qb.all()
        if res: # if there is no node with such an input return
            resnodesuuid = [node[0].uuid for node in res] # needed for common list parts
            overall_results.append(resnodesuuid)
        else:
            return None

    intersect = overall_results[0]
    if len(overall_results) > 1:
        for res in overall_results[1:]:
            intersect = intersectlist(intersect, res)
    qb1=QueryBuilder()
    qb1.append(
        JobCalculation,
        filters={
            'uuid' : {'in': intersect}
            })
    res = qb1.all()
    # we
    return res[0][0].outputs()
'''
'''
def check_existence(target_nodetype, input_nodes, successful=False):
    """
    This methods checks in the database waether a certain type of node with the given
    input nodes already exists. If yes it returns the output nodes of that node.

    param: target_nodetype
    param: input_nodes : List of input nodes

    returns output nodes

    Hints; successful is only for calculations types
    """
    inputnodesuuid = [node.uuid for node in input_nodes]
    qb=QueryBuilder()
    qb.append(Node,
        filters={
            'uuid' : {'in': inputnodesuuid},
        },
        tag='input')
    if successful:
        qb.append(
            target_nodetype,
            filters={
                'state' : {'==':'FINISHED'}
            },
            output_of='input')
    else:
        qb.append(
            target_nodetype,
            output_of='input')
    res = qb.all()
    print(len(res))
    if res:
        return res[0][0].ouputs()
    else:
        return None

def check_existence_calc(input_nodes, successful=True):
    """
    This methods checks in the database waether a certain type of node with the given
    input nodes already exists. If yes it returns the output nodes of that node.

    param: input_nodes : List of input nodes

    returns output nodes
    """
    inputnodesuuid = [node.uuid for node in input_nodes]
    qb=QueryBuilder()
    qb.append(Node,
        filters={
            'uuid' : {'in': inputnodesuuid},
        },
        tag='input')
    if successful:
        qb.append(
            JobCalculation,
            filters={
                'state' : {'==':'FINISHED'}
            },
            output_of='input')
    else:
        qb.append(
            JobCalculation,
            output_of='input')

    res = qb.all()
    print(len(res))
    if res:
        return res[0][0].ouputs()
    else:
        return None

def check_existence_wf(target_nodetype, input_nodes, successful=True):
    """
    This methods checks in the database waether a certain type of node with the given
    input nodes already exists. If yes it returns the output nodes of that node.

    param: input_nodes : List of input nodes

    returns output nodes
    """
    inputnodesuuid = [node.uuid for node in input_nodes]
    qb=QueryBuilder()
    qb.append(Node,
        filters={
            'uuid' : {'in': inputnodesuuid},
        },
        tag='input')
    if successful:
        qb.append(
            target_nodetype,
            filters={
                'state' : {'==':'FINISHED'}
            },
            output_of='input')
    else:
        qb.append(
            target_nodetype,
            output_of='input')
    res = qb.all()
    print(len(res))
    if res:
        return res[0][0].ouputs()
    else:
        return None
'''
