exec(open('yahoo_check/check2.py').read().split("def mdds")[0])
def st(x):
    m=x.mean()*252;v=x.std()*np.sqrt(252);s=x[x<0].std()*np.sqrt(252); return f"{m/v:.3f}/{m/s:.3f}"
idx=lr.index
for s0 in ['2023-05-31','2023-06-01','2023-06-02','2023-06-05','2023-06-06','2023-06-07']:
    i=idx.get_loc(pd.Timestamp(s0))
    new=lr.iloc[i:i+680]; old=lr.iloc[i:i+677]
    out=f"start {s0} newEnd {new.index[-1].date()} oldEnd {old.index[-1].date()} | new GSPC {st(new.GSPC)} | old GLD {st(old.GLD)}"
    for b in ['TLT','IEF','TIP']:
        c=['GSPC',b,'GLD','USO','UUP']
        out+=f" | EW {b} new {st(new[c].mean(axis=1))} old {st(old[c].mean(axis=1))}"
    print(out)
