import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
yrs=list(range(2011,2026))
sp=[2.11,16.00,32.39,13.69,1.38,11.96,21.83,-4.38,31.49,18.40,28.71,-18.11,26.29,25.02,17.88]
nq=[-1.80,15.91,38.32,13.40,5.73,7.50,28.24,-3.88,35.23,43.64,21.39,-33.10,43.42,28.64,20.36]
def grow(r):
    v=[10000];[v.append(v[-1]*(1+x/100)) for x in r];return v
B,O="#2a78d6","#eb6834"; T1,T2,G,S="#0b0b0b","#52514e","#e4e3df","#fcfcfb"
plt.rcParams.update({"font.family":"DejaVu Sans","axes.edgecolor":G,"xtick.color":T2,"ytick.color":T2,"axes.labelcolor":T2})
fig,(a1,a2)=plt.subplots(1,2,figsize=(14,6.2),facecolor=S,gridspec_kw={"width_ratios":[1,1.15]})
fig.suptitle("S&P 500 vs Nasdaq: los últimos 15 años (2011–2025)",x=0.04,ha="left",fontsize=18,fontweight="bold",color=T1,y=0.98)
fig.text(0.04,0.895,"S&P 500: ~14.1% anual compuesto  ·  Nasdaq Composite: ~15.6% anual compuesto",fontsize=12,color=T2)
for a in (a1,a2):
    a.set_facecolor(S); [a.spines[s].set_visible(False) for s in ("top","right","left")]
    a.grid(axis="y",color=G,lw=1); a.set_axisbelow(True); a.tick_params(length=0,labelsize=10)
x=list(range(2010,2026)); gs,gn=grow(sp),grow(nq)
a1.plot(x,gs,color=B,lw=2.5); a1.plot(x,gn,color=O,lw=2.5)
for g,c,n in ((gs,B,"S&P 500"),(gn,O,"Nasdaq")):
    a1.scatter([2025],[g[-1]],s=60,color=c,edgecolor=S,lw=2,zorder=3)
    a1.annotate(f"{n}\n${g[-1]:,.0f}",(2025,g[-1]),xytext=(8,0),textcoords="offset points",va="center",fontsize=11,color=T1,fontweight="bold")
a1.set_xlim(2010,2028.3); a1.set_xticks([2010,2015,2020,2025])
a1.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f"${v/1000:.0f}k"))
a1.set_title("Cuánto valdrían $10,000 invertidos a inicios de 2011",loc="left",fontsize=12.5,color=T1,pad=10)
w=0.4
a2.bar([y-w/2-0.01 for y in yrs],sp,w-0.04,color=B,label="S&P 500")
a2.bar([y+w/2+0.01 for y in yrs],nq,w-0.04,color=O,label="Nasdaq Composite")
a2.axhline(0,color=T2,lw=1)
a2.set_xticks(yrs); a2.set_xticklabels([f"'{str(y)[2:]}" for y in yrs])
a2.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f"{v:.0f}%"))
a2.annotate("2022: −18% / −33%",(2022,-33.1),xytext=(2018.2,-30),fontsize=10,color=T2,arrowprops=dict(arrowstyle="-",color=T2,lw=0.8))
a2.set_title("Rentabilidad de cada año",loc="left",fontsize=12.5,color=T1,pad=10)
a2.legend(frameon=False,loc="upper left",fontsize=10,ncol=2,labelcolor=T1)
a2.set_ylim(-38,52)
fig.text(0.04,0.02,"S&P 500 con dividendos reinvertidos; Nasdaq Composite solo precio. 2025 aproximado. Rendimientos pasados no garantizan resultados futuros.",fontsize=9,color=T2)
plt.tight_layout(rect=(0.02,0.05,1,0.88))
plt.savefig("/home/user/ramon-social-assets/charts/sp500-vs-nasdaq-15-anios.png",dpi=200,facecolor=S)
