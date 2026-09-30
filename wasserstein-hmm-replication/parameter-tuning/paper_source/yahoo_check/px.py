import numpy as np
from PIL import Image
im=np.array(Image.open('v1/PRD_weights.png').convert('RGB')).astype(int)
H,W,_=im.shape; print(H,W)
cols={'SPX':(31,119,180),'BOND':(255,127,14),'GOLD':(44,160,44),'OIL':(214,39,40),'USD':(148,103,189)}
# find y of 0 and 1 via gridlines: detect axis frame; approximate using color extents
mask={k:(np.abs(im-np.array(v)).sum(axis=2)<40) for k,v in cols.items()}
anyc=np.zeros((H,W),bool)
for m in mask.values(): anyc|=m
ys=np.where(anyc.any(axis=1))[0]; xs=np.where(anyc[200].nonzero()[0].size>0 and anyc.any(axis=0))[0]
colsx=np.where(anyc[100:400].sum(axis=0)>250)[0]
print('x range',colsx.min(),colsx.max())
# y extent in a column without legend
x0=colsx.max()-5; yy=np.where(anyc[:,x0])[0]; print('y extent at x0',yy.min(),yy.max())
top,bot=yy.min(),yy.max()+1; span=bot-top
res=[]
for x in range(colsx.min(),colsx.max()+1):
    w={k:mask[k][top:bot,x].sum()/span for k in cols}
    res.append(w)
import pandas as pd
d=pd.DataFrame(res); d['USD']=1-d[['SPX','BOND','GOLD','OIL']].sum(axis=1)
print(d.describe().round(3))
print('means',d.mean().round(3).to_dict())
print(d.quantile([0.9,0.95,0.98,0.99]).round(3))
s=d.sum(axis=1); print((d['USD']>0.5).sum())
