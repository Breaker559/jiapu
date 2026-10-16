import os
import tempfile
os.environ['QINPU_DATA']=tempfile.mkdtemp(prefix='qinpu-tests-')
os.environ.pop('DATABASE_URL',None)
