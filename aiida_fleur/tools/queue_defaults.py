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
In this file/module, YOU, the user can specify some default resource values for
queues of different computers
This might be really useful for high-throughput calculation.
You can modify, adjust this file to your needs
"""

# TODO: move computers dict somewhere else?
# TODO find AiiDA solution for this

from __future__ import print_function
def queue_defaults(queue_name, computer=None):
    """
    In this class you specify defaults methods which you can use for workflows
    or normal calculations.
    """
    '''
    code = Code.get_from_string(codename)
    code2 = Code.get_from_string(codename2)
    computer = Computer.get(computer_n
    ame)
    '''
    queue_resources = None
    print(queue_name)
    computers = {
        'iff003':
            {'th1' : {'resources' : {"num_machines": 1, "num_mpiprocs_per_machine" : 12},
                      'walltime_sec' : 30 * 60},
             'th1_small' : {'resources' : {"num_machines": 1, "num_mpiprocs_per_machine" : 12},
                            'walltime_sec' : 20 * 60}}}

    if computer:
        #print 'computer'
        c_name = computer
        queue = computers.get(c_name, {}).get(queue_name, {})
        res = queue.get('resources', None)
        wt = queue.get('walltime_sec', None)
    else:
        #print 'no computer'
        c_name = None
        res = None
        wt = None
        for comp in computers.keys():
            queue = computers.get(comp, {}).get(queue_name, {})
            #print 'queue {}'.format(queue)
            if queue:
                res = queue.get('resources', None)
                wt = queue.get('walltime_sec', None)

    queue_resources = {'resources' : res, 'walltime_sec' : wt}
    #print queue_resources

    return queue_resources
