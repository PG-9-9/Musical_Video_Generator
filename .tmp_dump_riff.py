import importlib
m = importlib.import_module('riffusion')
print('module file', getattr(m,'__file__',None))
for name in dir(m):
    print(name)
