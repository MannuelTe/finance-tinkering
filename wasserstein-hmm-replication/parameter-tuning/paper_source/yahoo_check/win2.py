exec(open('yahoo_check/win.py').read().split("idx=lr.index")[0])
i=lr.index.get_loc(pd.Timestamp('2023-06-05')); new=lr.iloc[i:i+680]; old=lr.iloc[i:i+677]
for b in ['TLT','IEF','LQD','TIP','GOVT','SHY','HYG','AGG','BND','IEI']:
    c=['GSPC',b,'GLD','USO','UUP']
    cum=new[c].mean(axis=1).cumsum()
    print(b,'new',st(new[c].mean(axis=1)),'old',st(old[c].mean(axis=1)),'EW cumlog',round(cum.iloc[-1],3),'mdd(exp)',round((np.exp(cum)/np.exp(cum).cummax()-1).min(),4))
c=['SPY','IEF','GLD','USO','UUP']; print('EW with SPY instead of GSPC + IEF new',st(new[c].mean(axis=1)),'old',st(old[c].mean(axis=1)))
