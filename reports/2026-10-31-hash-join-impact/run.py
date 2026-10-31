import sys, runpy
sys.path.insert(0, __import__('os').path.dirname(__file__))
if sys.argv[1] == 'hash':
    import hashjoin; hashjoin.patch()
if sys.argv[1] == 'hash+frame':
    import hashjoin; hashjoin.patch(); hashjoin.patch_frame()
sys.argv = ['cmca_analysis'] + sys.argv[2:]
runpy.run_module('cmca_analysis', run_name='__main__')
