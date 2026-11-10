"""Carrusel IG (ES + EN) S&P 500 vs Nasdaq 2011-2025. Run: python3 build.py"""
import os, base64, io
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import subprocess, tempfile
OUT=os.path.dirname(os.path.abspath(__file__))
NAVY,GOLD,GOLDL,INK2,GRID="#1c2b3f","#9a7127","#c9a45c","#3f4a58","#e5e7eb"
yrs=list(range(2011,2026))
sp=[2.11,16.00,32.39,13.69,1.38,11.96,21.83,-4.38,31.49,18.40,28.71,-18.11,26.29,25.02,17.88]
nq=[-1.80,15.91,38.32,13.40,5.73,7.50,28.24,-3.88,35.23,43.64,21.39,-33.10,43.42,28.64,20.36]
def grow(r):
    v=[10000]
    for x in r: v.append(v[-1]*(1+x/100))
    return v
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":17,"xtick.color":INK2,"ytick.color":INK2})
def ax_style(a):
    for s in ("top","right","left"): a.spines[s].set_visible(False)
    a.spines["bottom"].set_color(GRID); a.grid(axis="y",color=GRID,lw=1.2); a.set_axisbelow(True); a.tick_params(length=0)
def png(fig):
    b=io.BytesIO(); fig.savefig(b,format="png",dpi=100,transparent=True); plt.close(fig)
    return "data:image/png;base64,"+base64.b64encode(b.getvalue()).decode()
# growth line
fig,a=plt.subplots(figsize=(9.4,6.2)); ax_style(a)
x=list(range(2010,2026)); gs,gn=grow(sp),grow(nq)
a.plot(x,gn,color=GOLD,lw=4); a.plot(x,gs,color=NAVY,lw=4)
for g,c,n in ((gn,GOLD,"Nasdaq"),(gs,NAVY,"S&P 500")):
    a.scatter([2025],[g[-1]],s=140,color=c,edgecolor="white",lw=3,zorder=3)
    a.annotate(f"{n}\n${g[-1]/1000:,.0f}k",(2025,g[-1]),xytext=(12,0),textcoords="offset points",va="center",fontsize=17,fontweight="bold",color=c)
a.set_xlim(2010,2028.6); a.set_xticks([2011,2015,2020,2025]); a.set_ylim(0,95000)
a.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f"${v/1000:.0f}k"))
fig.tight_layout(); LINE=png(fig)
# bars
fig,a=plt.subplots(figsize=(9.4,4.9)); ax_style(a); w=0.4
a.bar([y-w/2-.02 for y in yrs],sp,w-.06,color=NAVY); a.bar([y+w/2+.02 for y in yrs],nq,w-.06,color=GOLDL)
a.axhline(0,color=INK2,lw=1.2); a.set_xticks(yrs[::2]); a.set_xticklabels([f"'{str(y)[2:]}" for y in yrs[::2]])
a.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f"{v:.0f}%")); a.set_ylim(-38,50)
a.annotate("2022",(2022,-35),ha="center",va="top",fontsize=14,fontweight="bold",color=INK2)
fig.tight_layout(); BARS=png(fig)

N=8
def slide(i,body,cover=False):
    return f"""<div class="s{' cover' if cover else ''}"><div class="main">{body}</div>
<div class="foot"><div class="logo">RG</div><div><div class="h">@ramonhouses</div><div class="u">ramonhouses.com</div></div><div class="pg">{i} / {N}</div></div></div>"""
LEG='<div class="leg"><span><i style="background:%s"></i>S&amp;P 500</span><span><i style="background:%s"></i>Nasdaq</span></div>'
S_ES=[
slide(1,'''<div class="tag">INVERSIÓN</div><h1 class="big">¿Cuánto ha rendido la bolsa en 15 años?</h1><div class="rule"></div>
<p>S&amp;P 500 vs Nasdaq, de 2011 a 2025. Los números reales, sin promesas.</p><div class="swipe">Desliza →</div>''',True),
slide(2,'''<div class="num">1</div><h2>S&amp;P 500</h2><div class="rule"></div><div class="stat">~14%<small> al año</small></div>
<p>Las 500 empresas más grandes de Estados Unidos. Rentabilidad anual compuesta de 2011 a 2025, con dividendos reinvertidos.</p>'''),
slide(3,'''<div class="num">2</div><h2>Nasdaq</h2><div class="rule"></div><div class="stat gold">~15.6%<small> al año</small></div>
<p>El índice de las tecnológicas: Apple, Microsoft, Nvidia, Amazon, Google. Rindió más que el S&amp;P 500 en el mismo periodo.</p>'''),
slide(4,f'''<div class="num">3</div><h2>$10,000 en 2011</h2><div class="rule"></div><p class="lead">Hoy serían unos <b>$72,000</b> en el S&amp;P 500 y <b>$87,600</b> en el Nasdaq.</p>
<img class="chart" src="{LINE}">'''),
slide(5,f'''<div class="num">4</div><h2>No todos los años suben</h2><div class="rule"></div><p class="lead">En 2022 el S&amp;P 500 cayó <b>18%</b> y el Nasdaq <b>33%</b>. Quien vendió con miedo se perdió la recuperación.</p>
{LEG % (NAVY,GOLDL)}<img class="chart" src="{BARS}">'''),
slide(6,'''<div class="num">5</div><h2>Más rendimiento, más sustos</h2><div class="rule"></div>
<p>El Nasdaq ganó ~1.5 puntos más al año, pero cayó el doble en su peor año. La pregunta no es cuál gana más, sino cuál puedes aguantar sin vender.</p>'''),
slide(7,'''<div class="num">6</div><h2>Ojo: esto no es lo normal</h2><div class="rule"></div>
<p>El promedio histórico del S&amp;P 500 desde 1926 es de ~10% al año. Estos 15 años fueron excepcionales. Planea con números conservadores.</p>'''),
slide(8,'''<h1 class="gold">El tiempo en el mercado le gana a adivinar el momento</h1><div class="rule"></div>
<p>Igual que en bienes raíces: el patrimonio se construye con años, no con meses. Guarda este post y mándaselo a quien está empezando a invertir.</p>
<p class="fine">Fuente: S&amp;P 500 rentabilidad total; Nasdaq Composite solo precio. 2025 aproximado. Rendimientos pasados no garantizan resultados futuros. Contenido educativo, no es asesoría financiera.</p>'''),
]
S_EN=[
slide(1,'''<div class="tag">INVESTING</div><h1 class="big">What has the stock market returned in 15 years?</h1><div class="rule"></div>
<p>S&amp;P 500 vs Nasdaq, 2011 to 2025. The real numbers, no promises.</p><div class="swipe">Swipe →</div>''',True),
slide(2,'''<div class="num">1</div><h2>S&amp;P 500</h2><div class="rule"></div><div class="stat">~14%<small> a year</small></div>
<p>The 500 largest companies in the U.S. Compound annual return from 2011 to 2025, with dividends reinvested.</p>'''),
slide(3,'''<div class="num">2</div><h2>Nasdaq</h2><div class="rule"></div><div class="stat gold">~15.6%<small> a year</small></div>
<p>The tech-heavy index: Apple, Microsoft, Nvidia, Amazon, Google. It beat the S&amp;P 500 over the same period.</p>'''),
slide(4,f'''<div class="num">3</div><h2>$10,000 in 2011</h2><div class="rule"></div><p class="lead">Today it would be about <b>$72,000</b> in the S&amp;P 500 and <b>$87,600</b> in the Nasdaq.</p>
<img class="chart" src="{LINE}">'''),
slide(5,f'''<div class="num">4</div><h2>Not every year goes up</h2><div class="rule"></div><p class="lead">In 2022 the S&amp;P 500 fell <b>18%</b> and the Nasdaq <b>33%</b>. Anyone who sold in fear missed the recovery.</p>
{LEG % (NAVY,GOLDL)}<img class="chart" src="{BARS}">'''),
slide(6,'''<div class="num">5</div><h2>More return, more scares</h2><div class="rule"></div>
<p>The Nasdaq earned ~1.5 points more a year, but fell almost twice as hard in its worst year. The question isn't which one earns more. It's which one you can hold without selling.</p>'''),
slide(7,'''<div class="num">6</div><h2>Heads up: this isn't normal</h2><div class="rule"></div>
<p>The S&amp;P 500's long-run average since 1926 is ~10% a year. These 15 years were exceptional. Plan with conservative numbers.</p>'''),
slide(8,'''<h1 class="gold">Time in the market beats timing the market</h1><div class="rule"></div>
<p>Same as real estate: wealth is built over years, not months. Save this post and send it to someone who's just starting to invest.</p>
<p class="fine">Source: S&amp;P 500 total return; Nasdaq Composite price only. 2025 approximate. Past performance does not guarantee future results. Educational content, not financial advice.</p>'''),
]
CSS=f"""@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@600;700&family=Barlow+Semi+Condensed:wght@400;600&display=block');
*{{margin:0;box-sizing:border-box}} body{{width:1080px}}
.s{{width:1080px;height:1350px;background:#fff;position:relative;border-left:14px solid {GOLDL};display:flex;flex-direction:column}}
.s.cover{{border-left:none;background:linear-gradient(180deg,#fff 0%,#fff 70%,#f7f2e8 100%)}}
.main{{flex:1;min-height:0;overflow:hidden;padding:110px 90px 40px 86px;display:flex;flex-direction:column}}
.cover .main{{justify-content:center;padding-left:100px}}
.tag{{align-self:flex-start;border:3px solid {GOLD};color:{GOLD};font:700 30px Oswald;letter-spacing:4px;padding:6px 16px;margin-bottom:48px}}
h1,h2{{font-family:Oswald;font-weight:700;text-transform:uppercase;color:{NAVY};line-height:1.08}}
h1{{font-size:96px}} h1.big{{font-size:118px}} h2{{font-size:80px}} .gold{{color:{GOLD}}}
.num{{font:700 120px/1 Oswald;color:{GOLD};margin-bottom:30px}}
.rule{{width:110px;height:5px;background:{GOLDL};margin:34px 0 44px}}
p{{font:400 44px/1.45 'Barlow Semi Condensed';color:{INK2}}} p b{{color:{NAVY};font-weight:600}}
p.lead{{margin-bottom:20px}}
.stat{{font:700 210px/1 Oswald;color:{NAVY};margin-bottom:50px}} .stat small{{font-size:60px;color:{INK2};font-weight:600}}
.chart{{width:100%;flex:1;min-height:0;object-fit:contain;object-position:bottom;margin-top:20px}}
.leg{{display:flex;gap:40px;font:600 34px 'Barlow Semi Condensed';color:{NAVY};margin-top:10px}} .leg i{{display:inline-block;width:28px;height:28px;border-radius:4px;margin-right:12px;vertical-align:-3px}}
.swipe{{position:absolute;bottom:200px;left:100px;font:600 40px 'Barlow Semi Condensed';color:{GOLD}}}
.fine{{font-size:27px;line-height:1.4;margin-top:auto;color:#6b7280}}
.foot{{height:150px;flex-shrink:0;background:#f3f4f6;display:flex;align-items:center;padding:0 70px;gap:24px}}
.cover .foot{{padding-left:84px}}
.logo{{width:84px;height:84px;border-radius:50%;border:3px solid {GOLDL};color:{GOLD};font:700 36px Georgia,serif;display:flex;align-items:center;justify-content:center}}
.h{{font:400 34px 'Barlow Semi Condensed';color:{NAVY}}} .u{{font:400 28px 'Barlow Semi Condensed';color:{GOLD}}}
.pg{{margin-left:auto;font:400 30px 'Barlow Semi Condensed';color:#6b7280}}"""
JS=r"""const {chromium}=require('playwright');(async()=>{const [h,o]=process.argv.slice(1);
const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1350}});
await p.goto('file://'+h,{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);
const els=await p.$$('.s');for(let i=0;i<els.length;i++)await els[i].screenshot({path:o+'/'+String(i+1).padStart(2,'0')+'.png'});
await b.close();})();"""
# Spanish slides go in this folder, English in en/. Rendered with Node Playwright (preinstalled Chromium).
for lang,S,out in (("es",S_ES,OUT),("en",S_EN,os.path.join(OUT,"en"))):
    os.makedirs(out,exist_ok=True)
    html=f"<!doctype html><html lang={lang}><head><meta charset=utf-8><style>{CSS}</style></head><body>{''.join(S)}</body></html>"
    tmp=os.path.join(tempfile.gettempdir(),f"carrusel-sp500-nasdaq-{lang}.html")
    with open(tmp,"w") as f: f.write(html)
    subprocess.run(["node","-e",JS,tmp,out],check=True)
print("ok")
