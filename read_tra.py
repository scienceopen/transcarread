#!/usr/bin/env python
from __future__ import division
from numpy import fromfile,float32, empty
from pandas import DataFrame, Panel
from os.path import getsize,expanduser, split, join
#
from readionoinit import compplasmaparam, parseionoheader, readionoheader
#from dateutil.relativedelta import relativedelta
#from pytz import UTC
"""
reads binary "transcar_output" file
many more quantities exist in the binary file, these are the ones we use so far.
requires: Matplotlib >= 1.4

examples:
./read_tra.py ~/transcar/at2/beam3915.4/dir.output/transcar_output
./read_tra.py ~/transcar/2014-04branch/matt2013local/beam3279.5/dir.output/transcar_output

 Michael Hirsch

variables:
n_t: number of time steps in file
n_alt: number of altitudes in simulation
d_bytes: number of bytes per data element
size_record: number of data bytes per time step

Note: header length = 2*ncol
"""
nhead = 126 #a priori from transconvec_13
d_bytes = 4 # a priori

def read_tra(tcoutput):
    tcoutput = expanduser(tcoutput)

    head0 = readionoheader(tcoutput, nhead)[0]
    ncol = head0['ncol']; n_alt = head0['nx']

    size_head = 2*ncol #+2 by defn of transconvec_13
    size_data_record = n_alt*ncol #data without header
    size_record = size_head + size_data_record

    assert size_head == nhead


#%% read data based on header
    iono,chi,pp = loopread(tcoutput,size_record,ncol,n_alt,size_head,size_data_record)

    return iono,chi, pp

def loopread(tcoutput,size_record,ncol,n_alt,size_head,size_data_record):
    n_t = getsize(tcoutput)//size_record//d_bytes

    chi  = empty(n_t,dtype=float)

    # to use a panel, we must fill it with a dict of DataFrames--at least one dataframe to initialize
    ppd = {}; ionod = {}
    with open(tcoutput,'rb') as f: #reset to beginning
        for i in range(n_t):
            ionoi, chi[i], time, ppi = data_tra(f, size_record,ncol,n_alt,
                                                   size_head, size_data_record)
            tind = time.strftime('%Y-%m-%dT%H:%M:%S')
            ionod[tind] = ionoi; ppd[tind] = ppi

    pp = Panel(ppd).transpose(2,1,0) # isr parameter x altitude x time
    iono = Panel(ionod).transpose(2,1,0)

    return iono,chi,pp

def data_tra(f, size_record, ncol, n_alt, nhead, size_data_record):
#%% parse header
    h = fromfile(f, float32, nhead)
    head = parseionoheader(h)
#%% read and index data
    data = fromfile(f,float32,size_data_record).reshape((n_alt,ncol),order='C')

    dextind = tuple(range(1,7)) + (49,) + tuple(range(7,13))
    if head['approx']>=13:
        dextind += tuple(range(13,22))
    else:
        dextind += (12,13,13,14,14,15,15,16,16)
    #n7=49 if ncol>49 else None

    iono = DataFrame(data[:,dextind],
                     index=data[:,0],
                     columns=('n1','n2','n3','n4','n5','n6','n7',
                        'v1','v2','v3','vm','ve',
                        't1p','t1t','t2p','t2t','t3p','t3t','tmp','tmt','tep','tet'))
#%% four ISR parameters
    """
    ion velocity from read_fluidmod.m
    data_tra.m does not consider n7 for ne or vi computation,
    BUT read_fluidmod.m does consider n7!
    """
    pp = compplasmaparam(iono,head['approx'])

    return iono, head['chi'],head['htime'], pp

def timelbl(time,ax,tctime):
    if time.size<200:
        ax.xaxis.set_minor_locator(SecondLocator(interval=10))
        ax.xaxis.set_minor_locator(SecondLocator(interval=2))
    elif time.size<500:
        ax.xaxis.set_minor_locator(MinuteLocator(interval=10))
        ax.xaxis.set_minor_locator(MinuteLocator(interval=2))

    #ax.axvline(tTC[tReqInd], color='white', linestyle='--',label='Req. Time')
    ax.axvline(tctime['tstartPrecip'], color='red', linestyle='--', label='Precip. Start')
    ax.axvline(tctime['tendPrecip'], color='red', linestyle='--',label='Precip. End')

def doPlot(t,iono, pp, infile,cmap,tctime,sfmt):
    alt = iono.major_axis.values
#%% ISR plasma parameters
    for ind,cn in zip(('ne','vi','Ti','Te'),(LogNorm(),None,None,None)):
        fg =  figure(); ax = fg.gca()
        pcm = ax.pcolormesh(t, alt, pp[ind].values, cmap = cmap, norm=cn)
        tplot(fg,ax,pcm,sfmt,ind,infile)
#%% ionosphere state parameters
    for ind in ('n1','n2','n3','n4','n5','n6'):
        fg = figure(); ax=fg.gca()
        pcm = ax.pcolormesh(t,alt,iono[ind].values, cmap= cmap,norm=LogNorm(),
                            vmin=0.1,vmax=1e12)
        tplot(fg,ax,pcm,sfmt,str(ind),infile)

def tplot(fg,ax,pcm,sfmt,ttxt,infile):
    ax.autoscale(True,tight=True)
    ax.set_xlabel('time [UTC]')
    ax.set_ylabel('altitude [km]')
    ax.set_title(ttxt + '\n ' + infile,fontsize=12)
    fg.colorbar(pcm,format=sfmt)
    timelbl(t,ax,tctime)
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
    ax.tick_params(axis='both', which='both', direction='out', labelsize=12)

def doPlot1d(time,chi,sfmt,infile,tctime):
    ax = figure().gca()
    ax.plot(time,chi)
    ax.set_xlabel('time')
    ax.set_ylabel('$\chi$')
    ax.set_title('solar zenith angle \n ' + infile,fontsize=12)
    ax.grid(True)
    ax.yaxis.set_major_formatter(sfmt)
    timelbl(time,ax,tctime)
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
    ax.autoscale(True)

if __name__=='__main__':
    from argparse import ArgumentParser
    from parseTranscar import readTranscarInput

    p = ArgumentParser(description='reads dir.output/transcar_output')
    p.add_argument('tofn',help='dir.output/transcar_output file to use',type=str)
    p.add_argument('--profile',help='profile performance',action='store_true')
    p.add_argument('--noplot',help='disable plotting',action="store_true")
    a = p.parse_args()
    doplot = not a.noplot
    #tcoutput = '~/transcar/AT1/beam11335./dir.output/transcar_output'
    doplot = not a.noplot


    if a.profile:
        import cProfile
        from pstats import Stats
        profFN = 'read_tra.pstats'
        print('saving profile results to ' + profFN)
        cProfile.run('read_tra(a.tofn)',profFN)
        Stats(profFN).sort_stats('time','cumulative').print_stats(50)
    else:
        iono,chi,pp = read_tra(a.tofn)

        if doplot:
            from matplotlib.pyplot import figure, show
            from matplotlib.ticker import ScalarFormatter,LogFormatter,LogFormatterMathtext #for 1e4 -> 1 x 10^4, applied DIRECTLY in format=
            #from matplotlib.ticker import MultipleLocator
            from matplotlib.dates import MinuteLocator, SecondLocator, DateFormatter
            from matplotlib.colors import LogNorm

            datfn = join(split(split(a.tofn)[0])[0],'dir.input/DATCAR')
            tctime = readTranscarInput(datfn)

            #sfmt = LogFormatter()
            sfmt=ScalarFormatter()
            #sfmt.set_scientific(True)
           # sfmt.set_useOffset(False)
           # sfmt.set_powerlimits((-2, 2))

    #%% do plot
            t = pp.minor_axis.to_datetime().to_pydatetime()
            doPlot(t,iono,pp, a.tofn, 'jet',tctime,sfmt)

            doPlot1d(t,chi,sfmt,a.tofn, tctime)

            show()

