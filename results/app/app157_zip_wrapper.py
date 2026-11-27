"""Background wrapper: record own PID for the lease, then build the v1.2.1 zip."""
import os
import runpy
import sys

PIDFILE = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app157_zip_pid.txt'
SCRIPT = r'C:\Users\Trekker-PTL\confucius4-openvino\.tmp_recover_app\v121_make_zip.py'
with open(PIDFILE, 'w', encoding='ascii') as f:
    f.write(str(os.getpid()))
sys.argv = [SCRIPT]
runpy.run_path(SCRIPT, run_name='__main__')
