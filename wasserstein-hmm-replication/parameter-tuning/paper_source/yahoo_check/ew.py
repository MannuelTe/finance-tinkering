exec(open('yahoo_check/check2.py').read().split("def mdds")[0])
for b in ['TLT','IEF','TIP','LQD','GOVT']:
    w=lr.loc[:'2026-02-20'].iloc[-680:]
    print(b, round(w[['GSPC',b,'GLD','USO','UUP']].mean(axis=1).sum(),3))
