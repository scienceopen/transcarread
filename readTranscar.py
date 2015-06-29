#!/usr/bin/env python3
from __future__ import division,print_function,absolute_import
from os.path import expanduser,join
from numpy import s_

from warnings import warn
#
try:
    from .readExcrates import ExcitationRates
    from .parseTranscar import readTranscarInput
except Exception:
    from readExcrates import ExcitationRates
    from parseTranscar import readTranscarInput
from pybashutils.findnearest import find_nearest
#
'''
getTranscar is the function called by "hist-feasibility" to get Transcar modeled VER/flux

outputs:
--------
Peigen: DataFrame, rows are altitudes [km], columns are beam energy [eV], at requested time
z: altitudes (redunant with Peigen row indices, for API compatibility) <-- to be removed future
Ek: energy of each beam (redundant with Peigen column indices, for API compatibility) <- to be removed future
EkPcolor: one extra energy step, saddles Ek for proper labeling of pcolor() plots.

We use pcolormesh instead of imshow to enable correct log-plot labeling/coloring

References include:
Zettergren, M. "Model-based optical and radar remote sensing of transport and composition in the auroral ionosphere" PhD Thesis, Boston Univ., 2009
Zettergren, M. et al "Optical estimation of auroral ion upflow: 2. A case study" JGR Vol 113 A7  2008 DOI:10.1029/2007JA012691
Zettergren, M. et al "Optical estimation of auroral ion upflow: Theory"          JGR Vol 112 A12 2007 DOI: 10.1029/2007JA012691

Tested with:
Matplotlib 1.4 (1.3.1 does NOT work for pcolormesh)

Plambda contains all the wavelengths generated for the reactions at a particular beam energy level
Plambda row: wavelength col: altitude
for each energy bin, we take Plambda through the EMCCD window and optional BG3 filter,
yielding Peigen, a ver eigenprofile p(z,E) for that particular energy
'''

def calcVERtc(infile,datadir,beamEnergy,tReq,sim,dbglvl):
#%% get beam directory
#    if beamEnergy % 1 == 0:
#        enerStr = enerStr[:-1] #discard trailing zero (not needed anymore)
    try:
        beamdir = expanduser(join(datadir,'beam{}'.format(beamEnergy)))
        if dbglvl>0: print(beamEnergy)
    except AttributeError as e:
        warn('you must specify the root path to the transcar output. {}'.format(e))
        raise
#%% read simulation parameters
    tctime = readTranscarInput(join(beamdir,'dir.input',sim.transcarconfig))
    if tctime is None: return None, None #leave here

    try:
      if not tctime['tstartPrecip'] < tReq < tctime['tendPrecip']:
        print('precip start/end: {} / {}'.format(tctime['tstartPrecip'],tctime['tendPrecip']) )
        warn('your requested time {} is outside the precipitation time'.format(tReq))
        tReq = tctime['tendPrecip']
        warn('falling back to using the end simulation time: {}'.format(tReq))
    except TypeError as e:
        tReq=None
        warn('problem with requested time : {} beam {}  {}'.format(tReq,beamEnergy,e))
#%% convert transcar output
    spec, tTC, dipangle = ExcitationRates(beamdir,infile,dbglvl)

    try:
        tReqInd = find_nearest(tTC,tReq)[0]
    except TypeError as e:
        warn('problem with requested time indexing. {}  {}'.format(beamEnergy,e))
        tReqInd = s_[-1]

    try:
        tUsed = tTC[tReqInd]
    except (TypeError,IndexError) as e:
        warn('using last time in place of requested time for beam {}  {}'.format(beamEnergy,e))
        try:
            tUsed = tTC[-1]
        except TypeError as e:
            warn('failed to find any usable time, simulation error likely.  {}'.format(e))
            tUsed=None

    return spec,tUsed,tReqInd
#%% plotting
def plotPeigen(Peigen):
    if Peigen is None: return

    fg = figure()
    ax = fg.gca()
    pcm = ax.pcolormesh(Peigen.columns.values,
                        Peigen.index.values,
                        Peigen.values)
    ax.autoscale(True,tight=True)
    ax.set_xscale('log')
    ax.set_xlabel('beam energy [eV]')
    ax.set_ylabel('altitude [km]')
    ax.set_title('Volume Emission Rate per unit diff num flux')
    fg.colorbar(pcm)
#%% for testing only
class SimpleSim():
    """
    simple input for debugging/self test
    """
    def __init__(self,filt,inpath=None):
        self.loadver = False
        self.loadverfn = 'precompute/01Mar2011_FA.h5'
        self.opticalfilter = filt
        self.minbeamev = 0
        #self.maxbeamev = #future
        self.transcarev = '~/code/transcar/dir.transcar.server/BT_E1E2prev.csv'
        self.transcarutc = ''
        self.excratesfn = 'emissions.dat'
        self.transcarpath = inpath
        self.transcarconfig = 'DATCAR'
        self.reacreq = ['metastable','atomic','n21ng','n2meinel','n22pg','n21pg']
        self.reactionfn = 'precompute/vjeinfc.h5'
        self.bg3fn = 'precompute/BG3transmittance.h5'
        self.windowfn = 'precompute/ixonWindowT.h5'
        self.qefn = 'precompute/emccdQE.h5'
        self.zenang = 12.5 #90-Bincl
        self.obsalt_km=0.3
#%% main (sanity test with hard coded values)
if __name__ == '__main__':
    from matplotlib.pyplot import figure, show
    from opticalmod import plotOptMod
    #
    from argparse import ArgumentParser
    p = ArgumentParser(description='analyzes HST data and makes simulations')
    p.add_argument('--profile',help='profile performance',action='store_true')
    p.add_argument('--filter',help='optical filter choices: bg3   none',default='bg3')
    p.add_argument('-v','--verbose',help='debug',action='count',default=0)
    p.add_argument('tcopath',help='set path from which to read transcar output files')
    p = p.parse_args()
#%% setup sim
    sim = SimpleSim(p.filter,p.tcopath)
#%% run sim
    if p.profile:
        import cProfile,pstats
        proffn = 'readTranscar.pstats'
        cProfile.run('getTranscar(sim, a.verbose)',proffn)
        pstats.Stats(proffn).sort_stats('time','cumulative').print_stats(50)
    else:
        Peigen, EKpcolor, Plambda=getTranscar(sim, p.verbose)
        plotPeigen(Peigen)
        plotOptMod(Plambda,Peigen)
        show()
