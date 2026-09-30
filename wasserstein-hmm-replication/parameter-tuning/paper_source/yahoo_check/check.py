import json, numpy as np, pandas as pd
def load(f):
    r=json.load(open(f))['chart']['result'][0]
    idx=pd.to_datetime(r['timestamp'],unit='s').normalize()
    q=r['indicators']
    s=pd.Series(q['quote'][0]['close'],index=idx)
    a=pd.Series(q['adjclose'][0]['adjclose'],index=idx) if 'adjclose' in q else s
    return s,a
gspc,_=load('yahoo_check/%5EGSPC.json'); voo_c,voo_a=load('yahoo_check/VOO.json')
p=pd.read_csv('../../paper-replication/data/prices.csv',index_col=0,parse_dates=True)
df=p.copy(); df['GSPC']=gspc; df['VOO']=voo_a
df=df.dropna()
lr=np.log(df).diff().dropna()
def stats(x):
    m=x.mean()*252; v=x.std()*np.sqrt(252)
    dd1=np.sqrt((np.minimum(x,0)**2).mean())*np.sqrt(252)
    dd2=x[x<0].std()*np.sqrt(252)
    cum=x.cumsum(); mdd_simple=(np.exp(cum)/np.exp(cum).cummax()-1).min(); mdd_log=(cum-cum.cummax()).min()
    return dict(sh=round(m/v,3),sortA=round(m/dd1,3),sortB=round(m/dd2,3),mddS=round(mdd_simple,4),mddL=round(mdd_log,4),cumlog=round(cum.iloc[-1],3),n=len(x))
for end in ['2026-02-20','2026-02-19']:
  for n in [680,682,677,679]:
    w=lr.loc[:end].iloc[-n:]
    print(end,n,w.index[0].date())
    ew=w[['SPY','TLT','GLD','USO','UUP']].mean(axis=1)
    for name,x in [('GSPC',w.GSPC),('VOO',w.VOO),('SPY',w.SPY),('GLD',w.GLD),('EW_TLT',ew)]:
        print('  ',name,stats(x))
