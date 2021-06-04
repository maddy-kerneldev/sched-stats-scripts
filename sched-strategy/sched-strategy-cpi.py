#
# Script to understand scheduler strategy.
#
# Madhavan Srinivasan, IBM Corp 2021
#
# Scripts needs perf.data created using a custom kernel and this commandline 
#
#   #sudo perf record -e sched:sched_switch -a sleep 5
#
# Script Uages:
#   #sudo perf stat -e "{r1001e,r20002}" -a sleep 200&
#   #sudo perf record -e sched:sched_switch -a sleep 5
#   #sudo perf script -i <path to perf.data file> -s ./sched-strategy-script.py
#
# Custom Kernel:
#   Need to add pmu counter cycles and instruction in sched_switch tracepoint
#
# Output:
#
#                               Affinity: ('af'-Affined, 'sc'-dispatched in a same-cache core,
#                                 ^        'bc'-dispatched in big core, 'oc'-dispatched in other core)
#                                 |
#       Task Name   TID     PID   |         | -> Cycles/Instruction(CPI) for that duration of run 
#          ^         ^       ^    |         |      How long task ran in us or ms
#          |         |       |    |         |      |
#        Process     tid     pid affinity   cpi  ran_time
#        kubelet   32180   32180       af  2.16 28.00 us
#        kubelet   32181   32180       af  1.72 15.00 us
#

from __future__ import print_function

import os
import sys

sys.path.append(os.environ['PERF_EXEC_PATH'] + \
	'/scripts/python/Perf-Trace-Util/lib/Perf/Trace')

from perf_trace_context import *
from Core import *

#disct = {<pid>: {<tid>:{'name':"", 'cpu':0, 'disp':0, 'affin':0, 'sc':0, 'bc':0, 'oc':0,'nsec':0, 'hist':[0,0,0,0,0,0], 'cpi':0.0}}}
#disct = {<cpu>: {<pid>: {<tid>:{ 'nsec':0, 'cycles':0, 'instructions':0}}}}
pid_dis = {}
cpu_dis = {}
lnsecs = 0
affinity = ['af','sc','bc','oc']

def trace_begin():
     print("%15s %7s %7s %8s %5s %9s  "%("Process", "tid", "pid", "affinity", "cpi", "ran_time"))

def trace_end():
     print("in trace_end")

def sched__sched_switch(event_name, context, common_cpu,
	common_secs, common_nsecs, common_pid, common_comm,
	common_callchain, prev_comm, prev_pid, prev_prio, prev_state, 
	next_comm, next_pid, next_prio, pmc_cycles, pmc_insts, 
		perf_sample_dict):
    global lnsecs
    pid = perf_sample_dict['sample'].get('pid')
    tid = perf_sample_dict['sample'].get('tid')
    nsecs = 0
    index = 0
    af_index = 0
    lstr = ""

    if (pid in pid_dis):
        if (tid in pid_dis[pid]):
            pid_dis[pid][tid]['disp'] += 1
            if (pid_dis[pid][tid]['cpu'] == common_cpu):
                pid_dis[pid][tid]['affin'] += 1
                af_index = 0
            else:
                old_bc = int(pid_dis[pid][tid]['cpu'] / 8)
                new_bc = int(common_cpu / 8)

                if (old_bc != new_bc):
                    pid_dis[pid][tid]['oc'] += 1
                    af_index = 3
                else:
                    if (int(pid_dis[pid][tid]['cpu'] % 2) == int(common_cpu % 2)):
                        pid_dis[pid][tid]['sc'] += 1
                        af_index = 1
                    else:
                        pid_dis[pid][tid]['bc'] += 1	
                        af_index = 2
                pid_dis[pid][tid]['cpu'] = common_cpu
        else:
            pid_dis[pid][tid] = {
                    'name': prev_comm, 'cpu': common_cpu, 'disp': 1, 'affin': 1, 'sc': 0, 'bc': 0, 'oc': 0, 'nsec': common_nsecs, 'hist':[0,0,0,0,0,0],
            }
    else:
        pid_dis[pid] = {
            tid: {
                'name': prev_comm, 'cpu': common_cpu, 'disp': 1, 'affin': 1, 'sc': 0, 'bc': 0, 'oc': 0, 'nsec': common_nsecs, 'hist':[0,0,0,0,0,0],
            }
        }

    if (common_cpu in cpu_dis):
        lnsecs = cpu_dis[common_cpu]['nsec']
        if (int(common_nsecs) < int(lnsecs)):
            nsecs = int(999999999 - int(lnsecs))
            nsecs += int(common_nsecs)
            msecs = int(nsecs/1000000)
        else: 
            nsecs = int(common_nsecs-lnsecs)
            msecs = int(nsecs/1000000)

        mindex = int(msecs/5)
        if (mindex <= 1):
            usecs = int(nsecs/1000)
            lstr = "us"
            if (usecs <= 100):
                 index = 0
            elif (usecs > 100 and usecs <= 500):
                 index = 1
            elif (usecs > 500 and usecs <= 1000):
                 index = 2
            val = usecs
        elif (mindex == 2):
            index = 3
            lstr = "ms"
            val = int(msecs/5)
        elif (mindex >= 2 and mindex <= 4):
            index = 4
            lstr = "ms"
            val = int(msecs/5)
        elif (int(mindex) >= 5):
            index = 5         
            lstr = "ms"
            val = int(msecs/5)

        cpi = 0.0
        prev_cycles = cpu_dis[common_cpu]['cycles']
        prev_instructions = cpu_dis[common_cpu]['instructions']
        cycles = pmc_cycles - prev_cycles
        instructions = pmc_insts - prev_instructions

        pid_dis[pid][tid]['hist'][index] += 1
        cpi = float(cycles/instructions)
        pid_dis[pid][tid]['cpi'] = float(cpi)
        print("%15s %7d %7d %8s %5.2f %5.2f %2s"%(prev_comm, tid, pid, affinity[af_index], cpi, val,lstr))
        cpu_dis[common_cpu]['nsec'] = common_nsecs
        cpu_dis[common_cpu]['cycles'] = pmc_cycles
        cpu_dis[common_cpu]['instructions'] = pmc_insts
    else:
        cpu_dis[common_cpu] = {'nsec':common_nsecs, 'cycles':pmc_cycles, 'instructions':pmc_insts}


def trace_unhandled(event_name, context, event_fields_dict, perf_sample_dict):
		print(get_dict_as_string(event_fields_dict))
		print('Sample: {'+get_dict_as_string(perf_sample_dict['sample'], ', ')+'}')

def print_header(event_name, cpu, secs, nsecs, pid, comm):
	print("%-20s %5u %05u.%09u %8u %-20s " % \
	(event_name, cpu, secs, nsecs, pid, comm), end="")

def get_dict_as_string(a_dict, delimiter=' '):
	return delimiter.join(['%s=%s'%(k,str(v))for k,v in sorted(a_dict.items())])
