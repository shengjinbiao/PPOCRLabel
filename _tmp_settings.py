import pickle, os, pprint
path = os.path.expanduser('~/.autoOCRSettings.pkl')
print('path:', path)
if os.path.exists(path):
    with open(path, 'rb') as f:
        data = pickle.load(f)
    pprint.pprint(data)
else:
    print('settings file missing')
