import pandas as pd, numpy as np, json
p=pd.read_parquet('/mnt/user-data/uploads/panel.parquet').sort_values(['ticker','date'])
p=p[p.date>='2023-01-01']
g=p.groupby('ticker')
p['ret']=g.close.pct_change()
p['gap']=g.date.diff().dt.days
r=p[p.date>='2024-01-01']
# exchange inference from max |ret| in last 2 years (rough)
mx=r.groupby('ticker').ret.apply(lambda s:s.abs().quantile(0.999) if len(s)>50 else np.nan)
mxa=r.groupby('ticker').ret.apply(lambda s:s.abs().max())
print('dups',p.duplicated(['ticker','date']).sum())
print('zero/neg prices',(p[['open','high','low','close']]<=0).sum().to_dict())
print('high<low',(p.high<p.low).sum(), 'close outside',((p.close>p.high*1.001)|(p.close<p.low*0.999)).sum())
big=r[r.ret.abs()>0.155]
print('|ret|>15.5% rows since 2024:',len(big), big.ticker.nunique())
print(big.sort_values('ret').head(15)[['ticker','date','close','ret']])
# liquidity
p['val']=p.gt_khop
liq=r.groupby('ticker').gt_khop.median()
print('tickers median value>=5bn since 2024:',(liq>=5e9).sum())
print('gap>10 days rows (2025+):',(p[(p.date>='2025-01-01')].gap>10).sum())
d=p.groupby('date').ticker.count(); print(d.tail(10))
print('----- 3-letter stocks only')
s=r[r.ticker.str.fullmatch(r'[A-Z0-9]{3}')]
print('tickers',s.ticker.nunique())
b=s[s.ret.abs()>0.155]; print('|ret|>15.5%:',len(b),b.ticker.nunique())
# check UPCoM ±15% would allow these; flag >40% jumps as likely unadjusted corporate actions
b2=s[s.ret<-0.30]; print('ret<-30%:',len(b2)); print(b2[['ticker','date','close','ret']].head(20))
liq=s.groupby('ticker').gt_khop.median(); print('median value>=5bn:',(liq>=5e9).sum())
