import numpy as np
new=[(222,0.101301,0.053593),(29,0.322967,0.079310),(211,0.153335,0.061174),(204,0.096263,0.057581),(14,0.227562,0.070000)]
old=[(209,0.132748,0.052735),(32,0.285234,0.078569),(212,0.148035,0.061536),(211,0.073687,0.057434),(13,0.106090,0.065074)]
for nm,t in [('new',new),('old',old)]:
    n=sum(d for d,_,_ in t); m=sum(d*a for d,a,_ in t)/n
    # daily
    md=[a/252 for _,a,_ in t]; sd=[v/np.sqrt(252) for _,_,v in t]
    ex2=sum(d*((s**2)*(d-1)/d + mu**2) for (d,_,_),mu,s in zip(t,md,sd))/n
    var=(ex2-(m/252)**2)*n/(n-1)
    vol=np.sqrt(var*252)
    print(nm,'days',n,'annmean',round(m,4),'annvol',round(vol,4),'sharpe',round(m/vol,3),'cum log',round(m/252*n,3))
