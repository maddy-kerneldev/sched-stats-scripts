#
# Script to understand scheduler strategy.
#
# Madhavan Srinivasan, IBM Corp 2021
#
# Scripts needs perf.data created using commandline 
#
#   #sudo perf record -e sched:sched_switch -a sleep 5
#
# Script Uages:
#
#   #sudo perf script -i <path to perf.data file> -s ./sched-strategy-script.py
#

from __future__ import print_function

import os
import sys

sys.path.append(os.environ['PERF_EXEC_PATH'] + \
	'/scripts/python/Perf-Trace-Util/lib/Perf/Trace')

from perf_trace_context import *
from Core import *

#disct = {<pid>: {<tid>:{'name':"", 'cpu':0, 'disp':0, 'affin':0, 'sc':0, 'bc':0, 'oc':0}}}
pid_dis = {}

def trace_end():
    print("%16s %12s %12s %7s %7s %7s %7s %7s %7s %7s %7s %7s" % ("Process", "tid", "pid", "#Disp", "#affin", "%affin", "#sc", "%sc", "#bc", "%bc", "#oc", "%oc"))
    print("-------------------------------------------------------------------------------------------------------------------")
    for pid, tid_dis in sorted(pid_dis.items()):
        for tid in tid_dis:
            print('%16s %12s %12s %7d %7d %7.2f %7d %7.2f %7d %7.2f %7d %7.2f' % (tid_dis[tid]['name'],
                tid, pid, tid_dis[tid]['disp'], tid_dis[tid]['affin'],
                (tid_dis[tid]['affin']*100/tid_dis[tid]['disp']),
                tid_dis[tid]['sc'], (tid_dis[tid]['sc']*100/tid_dis[tid]['disp']),
                tid_dis[tid]['bc'], (tid_dis[tid]['bc']*100/tid_dis[tid]['disp']),
                tid_dis[tid]['oc'], (tid_dis[tid]['oc']*100/tid_dis[tid]['disp']),
                ))

def sched__sched_switch(event_name, context, common_cpu,
	common_secs, common_nsecs, common_pid, common_comm,
	common_callchain, prev_comm, prev_pid, prev_prio, prev_state, 
	next_comm, next_pid, next_prio, perf_sample_dict):
    pid = perf_sample_dict['sample'].get('pid')
    tid = perf_sample_dict['sample'].get('tid')

    if (pid in pid_dis):
        if (tid in pid_dis[pid]):
            pid_dis[pid][tid]['disp'] += 1
            if (pid_dis[pid][tid]['cpu'] == common_cpu):
                pid_dis[pid][tid]['affin'] += 1
            else:
                old_bc = int(pid_dis[pid][tid]['cpu'] / 8)
                new_bc = int(common_cpu / 8)

                if (old_bc != new_bc):
                    pid_dis[pid][tid]['oc'] += 1
                else:
                    if (int(pid_dis[pid][tid]['cpu'] % 2) == int(common_cpu % 2)):
                        pid_dis[pid][tid]['sc'] += 1
                    else:
                        pid_dis[pid][tid]['bc'] += 1	

                pid_dis[pid][tid]['cpu'] = common_cpu

        else:
            pid_dis[pid][tid] = {
                    'name': prev_comm, 'cpu': common_cpu, 'disp': 1, 'affin': 1, 'sc': 0, 'bc': 0, 'oc': 0,
            }
    else:
        pid_dis[pid] = {
            tid: {
                'name': prev_comm, 'cpu': common_cpu, 'disp': 1, 'affin': 1, 'sc': 0, 'bc': 0, 'oc': 0,
            }
        }

def trace_unhandled(event_name, context, event_fields_dict, perf_sample_dict):
		print(get_dict_as_string(event_fields_dict))
		print('Sample: {'+get_dict_as_string(perf_sample_dict['sample'], ', ')+'}')

def print_header(event_name, cpu, secs, nsecs, pid, comm):
	print("%-20s %5u %05u.%09u %8u %-20s " % \
	(event_name, cpu, secs, nsecs, pid, comm), end="")

def get_dict_as_string(a_dict, delimiter=' '):
	return delimiter.join(['%s=%s'%(k,str(v))for k,v in sorted(a_dict.items())])
