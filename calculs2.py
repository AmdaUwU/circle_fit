# Document servant à traiter les données provenants de mesures

# %%

import matplotlib
import numpy as np
import fitter as xd
from importlib import reload
import matplotlib.pyplot as plt
from extra_funcs import *
from tablpy import table
import pandas as pd
import os
from fitter import results

# %%
path = '../mesures/transmission-chaud/'
for i in os.listdir(path)[:-1]:
    a = table(path + i, delimiter='\t')
    a.renameCols(['f', 'mag'])
    a.giveUnits({'f':'Hz', 'mag':'dB'})
    a.changeUnits({'f': 'GHz'})
    a.plot('f', 'mag')
    plt.savefig('data_graph/chaud_'+i.replace('csv','png'))
    plt.show()

# %%
path = '../mesures/transmission-froid/'
for i in os.listdir(path):
    a = table(path + i)
    a.renameCols(['f', 'mag'])
    a.giveUnits({'f':'Hz', 'mag':'dB'})
    a.changeUnits({'f': 'GHz'})
    a.plot('f', 'mag')
    plt.savefig('data_graph/froid_'+i.replace('csv','png'))
    plt.show()

#%%
path = '../mesures/transmission_froid_complex/'
for i in os.listdir(path):
    a = results(path + i, skiprows=26, delimiter='\t')
    #a.renameCols(['f', 'mag'])
    a.giveUnits({'f':'Hz', 'mag':'dB'})
    a.changeUnits({'f': 'GHz'})
    a.plot('f', 'mag')
    plt.savefig('data_graph/froid_'+i.replace('txt','png'))
    plt.show()

#%%
noms = ['-10 dB', '-1 dB', '-3 dB', '-4 dB', '-7 dB']

path = '../mesures/transmission_froid_complex/'
for i in enumerate(filter(lambda i: 'res1' in i, os.listdir(path))):
    a = results(path + i[1], skiprows=26, delimiter='\t')
    a.giveUnits({'f':'Hz'})
    a.changeUnits({'f': 'GHz'})
    plt.xlim(8.3525,8.355)
    a.plot('f', 'mag', label = noms[i[0]])
plt.legend()
plt.savefig('data_graph/res1-comp.png')
plt.show()

# %%
a = xd.results('../mesures/transmission_froid_complex/res1-10db20210414-160527.txt',
               delimiter='\t', forceFormat=True, skiprows=25)

# %%
a.data['mag']/= max(a.data['mag'])

a.plot('f', 'mag')
plt.show()

a.guess_freq_res = 8.43e9
a.guess_Ql = 1e4
a.guessWidth= 1e6
a.IsNormalized = True
a.r = 0.0003
a.phi =0
a.magFit(show=True)
# %%
print(a)
a.plot('re', 'im')
plt.show()
#a.data = a.data.iloc[470: -450]
a.data = a.data.reset_index(drop=True)
a.data['\\theta'] = np.unwrap(2*a['\\theta'])
a.plot('f', '\\theta')
plt.show()
a.subLin(show=True, p0=[-6.4e-07,  5.4e+03, 1000000, 8.429e9])
a.plot('re', 'im')
plt.gca().set_aspect(1)
plt.show()
a.plot('f', '\\theta')
plt.show()
##a.IsSubLined = True
#a.IsIsolated = True
#a.guess_freq_res = 8.3540e9
#a.guessWidth = 100e6
plt.plot(a['f'], a['mag'])
plt.show()

a.normalize(show=True)
# %%
