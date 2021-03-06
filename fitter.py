import os
import warnings
import numpy as np
from lmfit import Model
from tablpy import table
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from copy import deepcopy as copy
from scipy.optimize import curve_fit
from tablpy.extra_funcs import roll, extrem

table.showUncertain = False

if 'fitter_plots' not in os.listdir():
    os.mkdir('fitter_plots')

def lin(x, a, b):
    return a*x + b


def quad(x, a, b, c):
    return a*x**2 + b*x + c


class results(table):
    """
    results object based on tablpy's talbe

    https://github.com/AmdaUwU/tablpy

    (file) This is where you give the path of the file you want to import
        the data from (text files or .xlsx supported).

    (data) [optional] You can pass in an already generated data structure 
        (np.array or pd.DataFrame), the 'file' keyword will be ignored if 
        you choose to do so

    (AutoInsert) [optional] Uncertainties columns will be automatically
        generated if none are found

    (forceFormat) [optional] If True, data will be reformated even if passed
        with the data argument (reforamating explained below)

    It is assumed that the last columns of the table are :Frequency (GHz),
    re(S_12), im(S_12), in this order and colmuns will be renamed accordingly
    If that is not the case, you can change the names manually with the
    .renameCols method and the units with the .giveUnits method.txt

    The, real, imaginary, mangetude and agular componants are all sotred for
    each points at all times and kept consitant with each other using the
    appropriates methodes

    """
    __doc__ += table.__doc__

    def __init__(self, file, data=None, AutoInsert=True,
                 forceFormat=False, delimiter=',', skiprows=None, **kwargs):
        super().__init__(file, AutoInsert=AutoInsert, data=data,
                         delimiter=delimiter, skiprows=skiprows)

        # Columns are renamed and given the right units
        if data is None or forceFormat:
            print(data)
            noms = list(self.data)[:-6:2]
            self.renameCols(noms + ['f', 're', 'im'])
            self.giveUnits({'f': 'GHz'})
            self.newCol(r'\theta', 'atan(im/re)', units='rad')
            self.newCol(r'mag', 'sqrt(re**2 + im**2)', units='1')
            for i in kwargs:
                exec(f"self.{i} = kwargs[i]")
        self.IsSubLined = False
        self.IsIsolated = False
        self.IsRejected = False
        self.IsNormalized = False
        self.ContainsRes = True
        self.failed = False

    def updateCart(s):
        """Ensure cartesian coordinates are consistant with the polar ones"""
        s['re'], s['im'] = (a(s['\\theta'])*s['mag'] for a in (np.cos, np.sin))

    def updatePolar(self):
        """Ensure polar coordinates are consistant with the cartesian ones"""
        self['\\theta'] = np.arctan2(*self[['im', 're']].T)
        self['mag'] = np.sqrt(self['re']**2+self['im']**2)

    def subLin(self, show=False, p0=None):
        """ removes linear background from data """
        popt, pcov = curve_fit(lin, *self[['f', '\\theta']].T)
        if show:
            print(popt)
            plt.plot(self['f'],self['\\theta'])
            plt.plot(self['f'], lin(self['f'], *popt))
            plt.show()
        self['\\theta'] = self['\\theta'] - lin(self['f'], *popt[:2])
        #self['\\theta'] = (self['\\theta'] +np.pi/2)%np.pi - np.pi/2
        self.updateCart()
        self.IsSubLined = True

    def circleFit(self, x0=None, show=False, reject=True):
        '''
        return center_x, center_y, radius of circle

        (x0) guess for circle Parameters

        (show) plots data and fit, mainly for debuging

        (reject) If true, rejects points laying too far from the fitted circle
        '''
        # genere une copie sur les quels les transformations seront fait
        t = copy(self)
        # deplace l'origine a l'interieur du cercle
        xoff, yoff = np.average(t['re']), np.average(t['im'])
        t['re'] -= xoff
        t['im'] -= yoff
        t.updatePolar()

        if x0 is None:
            x0 = [(max(t['re'])+min(t['re']))/2, (max(t['im'])+min(t['im']))/2,
                  (max(t['im'])-min(t['im']))/2]

        # Defines a circle equation in polar coordinates
        def circle(theta, a, b, r):
            return a*np.cos(theta) + b*np.sin(theta)\
                   + np.sqrt((a*np.cos(theta)+b*np.sin(theta))**2-a*a-b*b+r*r)

        # first fit!
        Circle = Model(circle)
        params = Circle.make_params(a=x0[0], b=x0[1], r=x0[2])

        try:
            results = Circle.fit(t['mag'], params, theta=t['\\theta'], nan_policy='omit')
        except:
            self.failed = True
            return None, None, None
        vals = results.values.values()

        # rejection of outliers points
        diff = t['mag']-circle(t['\\theta'], *vals)
        std = np.std(diff)

        # somewhat arbitrairy amount of standard deviation allowed
        n = 1

        if reject and not self.IsRejected:
            t.data = t.data[diff < n*std]
            self.data = self.data[diff < n*std]
            self.IsRejected = True

        # second fit without rejected points
        results = Circle.fit(t['mag'], params, theta=t['\\theta'])
        vals2 = results.values.values()
        theta = np.linspace(-np.pi, np.pi, 1000)

        if show:
            re, im = (a(theta)*circle(theta, *vals2) for a in (np.cos, np.sin))
            plt.plot(re, im, label='fit')
            rem = np.cos(theta)*(circle(theta, *vals) + n*std)
            imm = np.sin(theta)*(circle(theta, *vals) + n*std)
            plt.plot(rem, imm, label='max deviation')

            t.plot('re', 'im')
            plt.gca().set_aspect(1)
            plt.legend()
            plt.show()
        return np.array(list(vals2)) + np.array([xoff, yoff, 0])

    def normalize(self, x0=None, x0c=None, show=False, isolate=True):
        """Modifiy the data by normalizing it"""
        # Ensures linear backgrond is removed and the spike is IsIsolated
        if not self.IsSubLined:
            self.subLin()
            self.IsSubLined = True
        if not self.IsIsolated and isolate:
            self.isolateSpike()
            self.IsIsolated = True
        # if failed to identify a spike, data will be ingored
        if not self.ContainsRes:
            warnings.warn("The resonant Frequency appeares not to be in the "
                          "frequency range")
            self.failed = True
            return None
        if show:
            plt.title('Determining center and radius')
        a, b, r = self.circleFit(x0=x0c, show=show)
        if a is None:
            print('Cricle fitting has failed!')
            return

        t = copy(self)

        # Centering the circle so that the function is not multivalued in polar
        t['re'] -= a
        t['im'] -= b
        t.updatePolar()
        # Guessing initials parameters
        if x0 is None:
            self.guess_theta_0 = np.average(t['\\theta'])
            self.guess_Q = self.guess_freq_res/self.guessWidth*5
            x0 = [self.guess_theta_0, self.guess_Q, self.guess_freq_res]

        # Definition of the model
        def theta2(x, theta0, Ql, fr):
            return roll((theta0 + np.arctan(2*Ql*(1-x/fr)))-np.pi/2,
                        -np.pi/2, np.pi/2)

        Theta = Model(theta2)
        params = Theta.make_params(
            theta0=self.guess_theta_0,
            Ql=self.guess_freq_res/self.guessWidth*5,
            fr=self.guess_freq_res)
        freq = t['f']

        # Somewhat arbitrairy weighing
        w = (10/(0.5+((t['f']-self.guess_freq_res)/self.guessWidth)**2))

        result = Theta.fit(t['\\theta'], params, x=freq, weights=w,
                           max_nfev=10000)
        self.guess_freq_res = result.values['fr']
        self.guess_Ql = result.values['Ql']

        # coordinates of the point
        x = a + r*np.cos(result.values['theta0'])
        y = b + r*np.sin(result.values['theta0'])
        if show:
            t.plot("f", "\\theta")
            f = np.linspace(*extrem(t['f']), 1000)
            # plt.plot(f, theta2(f, *popt), label="fit")
            plt.plot(f, theta2(f, *result.values.values()), label='fit2')
            plt.plot(f, theta2(f, *params.valuesdict().values()),
                     label='guess')
            plt.hlines(result.values['theta0'], *extrem(f))
            plt.legend()
            plt.show()
            self.plot('re', 'im')
            plt.gca().set_aspect(1)
            plt.scatter(x, y, s=200, c='orange', label='off-resonant point')
            plt.legend()
            plt.gca().spines['bottom'].set_position('zero')
            plt.show()
        rho = np.sqrt(x*x + y*y)
        theta = np.arctan2(y, x)
        self['mag'] /= rho
        self['\\theta'] -= theta
        self.updateCart()
        self.IsNormalized = True
        # new center
        R = np.array([[np.cos(-theta), -np.sin(-theta)],
                      [np.sin(-theta), np.cos(-theta)]])
        a, b = R@np.array((a, b))*1/rho
        r /= rho
        self.yc = b
        self.phi = np.arcsin(b/r)
        self.r = r
        if show:
            plt.hlines(self.yc, 0, 1)
            plt.gca().set_aspect(1)
            plt.gca().spines['bottom'].set_position('zero')
            self.plot('re', 'im')
            plt.show()

    def splitBy(self, col):
        """
        returns a list of result objects, splitting the intial one by the
        differents values in the specified column

        ex:
        >>> a = results("foo")
        >>> a
        ... foo bar baz
        ...   1   1   4
        ...   1   2   5
        ...   2   1   2
        ...   2   2   3

        >>> as = a.splitBy('foo')
        >>> as[0]
        ... bar baz
        ...   1   4
        ...   2   5

        >>> as[0].foo
        ... 1

        >>> as[1]
        ... bar baz
        ...   1   2
        ...   2   3
        """
        out = []
        for x in list(set(self[col])):
            sub_df = self.data.loc[self[col] == x]
            exec(r'r=results("", data=sub_df, {}={}, AutoInsert = False)'
                 .format(col, x), locals(), globals())
            exec(f'r.{col} = {x}')
            r.data.index = (np.arange(0, len(r)))
            out.append(r)
            shit = f"out[-1].delCol('{col}')"
            exec(shit)
        return out

    def isolateSpike(self, show=False):
        """Keeps only data close to the resonant frequency"""
        avg = np.average(self['mag'])
        std = np.std(self['mag'])
        # frequency at max and min, both roughfly the resonant frequency
        minmag = float(self.data[self['mag'] == min(self['mag'])]['f'])
        maxmag = float(self.data[self['mag'] == max(self['mag'])]['f'])
        self.guess_freq_res =\
            float(self.data[self['\\theta'] == min(self['\\theta'])]['f'])

        low_freq = self.data.loc[self['f'] < minmag]
        high_freq = self.data.loc[self['f'] > maxmag]
        if len(low_freq) == 0 or len(high_freq) == 0:
            self.ContainsRes = False
            self.failed = True
            return
        n = 2
        if show:
            plt.hlines(avg - n*std, *extrem(self['f']))
            plt.hlines(avg + n*std, *extrem(self['f']))
            plt.vlines(minmag, 0, 1)
        keep = low_freq[abs(low_freq['mag'] - avg) < n*std]
        keep2 = high_freq[abs(high_freq['mag'] - avg) < n*std]
        if len(keep) == 0 or len(keep2) == 0:
            self.ContainsRes = False
            self.failed = True
            return
        x0 = keep.index[-1]
        x1 = keep2.index[0]
        if show:
            plt.plot(*self[['f', 'mag']][keep.index].T, ".")
            plt.plot(*self[['f', 'mag']][keep2.index].T, ".")
            plt.vlines(self['f'][x0], 0, 0.5, linestyles='dashed', color='g')
            plt.vlines(self['f'][x1], 0, 0.5, linestyles='dashed', color='g')
            plt.show()
        index_width = x1-x0
        self.guessWidth = self['f'][x1] - self['f'][x0]
        self.data = self.data[x0-index_width: x1+index_width]
        self.IsIsolated = True

    def magFit(self, show=False):
        """Fit on magnetude of data, normalizes if not already done"""
        if self.ContainsRes:
            if not self.IsNormalized:
                self.normalize()
                if self.failed:
                    return
        else:
            self.failed = True
            print('Oups')
            return
        Mod_S12 = Model(S12_fit)
        params = Mod_S12.make_params(
            fr=self.guess_freq_res,
            Ql=self.guess_Ql,
            Qc=self.guess_Ql*2,
            phi=0,
            offset=0)

        weight = (100/(1+((self['f']-self.guess_freq_res)/self.guessWidth)**2))

        result = Mod_S12.fit(self['mag'], params, x=self['f'], weights=weight)
        p = result.params
        if show:
            result.plot()
        if not result.errorbars\
           or np.any([abs(p[a].stderr/p[a].value) > 1 for a in p.keys()]):
            self.failed = True
            print("failed")
            return

        self.freq_res = result.values['fr']
        self.Ql = result.values['Ql']
        self.offset = result.values['offset']
        self.Qc = self.Ql/(2*self.r*np.cos(self.phi))
        return result

    def Analyse(self, var, params=['fr', 'Ql', 'Qc', 'phi'], save=False, **kwargs):
        """
        finds correlation between specified variables and variables ouputed by
        the magnetude fit like the ressonant frequency and quality factors

        (var) independant variable of wich you want to see the effect

        (params) [optional] parameters given by the magnetude fit of which you
        want to see the correlation with **var**
        """
        SubDts = self.splitBy(var)
        data = []
        for sub in SubDts:
            sub.magFit()
            if not sub.failed:
                ldic=locals()
                exec(f"slice = [sub.{var}]", ldic)
                slice = ldic['slice']
                for i in [0]:
                    slice+= [sub.freq_res, sub.Ql, sub.Qc, sub.phi]
                data.append(slice)
            # results = sub.magFit()
            # if not sub.failed:
            #     results = results.params
            #     exec(f"slice = [sub.{var}, 0]", locals(), globals())
            #     for i in params:
            #         slice.extend([results[i].value, results[i].stderr])
            #     data.append(slice)
        dt = table("", data=data)
        dt.renameCols([var] + params)
        dt.giveUnits({'fr': sub.units['f']})
        for i in params:
            dt.plot(var, i, markersize=20)
            corr, p = pearsonr(*dt[[var, i]].T)
            plt.annotate('r = {:.3f}\np = {:.3g}'.format(corr, p),
                         xy=(0.05, 0.25), xycoords='axes fraction')
            if save:
                plt.savefig('fitter_plots/' + f"corr_{var}-{i}.png")
            plt.show()
        return dt

def S12_fit(x, fr, Ql, Qc, phi, offset):
    return np.abs(1-Ql/Qc*np.exp(-1j*phi)/(1+2j*Ql*(x-fr)/fr)) + offset
