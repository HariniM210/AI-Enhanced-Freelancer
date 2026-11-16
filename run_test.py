import subprocess, sys
ret = subprocess.call([sys.executable, '-m', 'pytest', '-q'])
sys.exit(ret)
