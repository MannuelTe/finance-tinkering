import json, numpy as np, pandas as pd
def load(t):
    r=json.load(open(f'yahoo_check/{t}.json'))['chart']['result'][0]
    idx=pd.to_datetime(r['timestamp'],unit='s').normalize()
    q=r['indicators']
    return pd.Series(q['adjclose'][0]['adjclose'] if 'adjclose' in q else q['quote'][0]['close'],index=idx)
p=pd.read_csv('../../paper-replication/data/prices.csv',index_col=0,parse_dates=True)
df=p.copy(); df['GSPC']=load('%5EGSPC')
bonds=['TLT','IEF','LQD','TIP','GOVT','SHY','HYG','AGG','BND','IEI']
for b in bonds[1:]: df[b]=load(b)
df=df.dropna(); lr=np.log(df).diff().dropna(); sr=df.pct_change().dropna()
def mdds(x):
    c=x.cumsum(); a=(np.exp(c)/np.exp(c).cummax()-1).min(); b=((1+c)/(1+c).cummax()-1).min(); d=(c-c.cummax()).min()
    return round(a,4),round(b,4),round(d,4)
def st(x):
    m=x.mean()*252;v=x.std()*np.sqrt(252);s=x[x<0].std()*np.sqrt(252)
    return round(m/v,3),round(m/s,3),mdds(x)
for end,n in [('2026-02-20',680),('2026-02-19',680),('2026-02-20',682),('2026-02-20',677)]:
    w=lr.loc[:end].iloc[-n:]; ws=sr.loc[:end].iloc[-n:]
    print(end,n,w.index[0].date(),'GSPC',st(w.GSPC))
    for b in bonds:
        cols=['GSPC',b,'GLD','USO','UUP']
        ew=w[cols].mean(axis=1); ews=np.log1p(ws[cols].mean(axis=1))
        print('   EW',b,'loglin',st(ew),'simple',st(ews), 'bond alone',st(w[b])[:2])
