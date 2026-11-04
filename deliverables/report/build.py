# -*- coding: utf-8 -*-
import html
def e(s): return html.escape(s, quote=True)
TBC = lambda t="to confirm": f'<span class="tbc">{t}</span>'

# ---------- Gantt ----------
G = [
 ("Design and comparison", False, [
  ("Feature comparison","Zhibek",6,8,"plan"),
  ("Architecture, sequences, state machine","Zhibek",6,7,"done"),
  ("Interface contracts","Zhibek",8,10,"plan"),
  ("Design reviews, system test scenarios","Zhibek",10,13,"plan"),
  ("Design chapter, demo script","Zhibek",13,14,"plan")]),
 ("Front end", False, [
  ("Wireframes and brand","Daniel",6,7,"done"),
  ("React scaffold, login, MFA screens","Magzhan, Daniel",8,10,"plan"),
  ("Listing, browse, search","Magzhan, Daniel",9,11,"plan"),
  ("Live auction page","Magzhan, Daniel",11,13,"plan"),
  ("Checkout screens","Magzhan, Daniel",12,13,"plan"),
  ("Usability test","Daniel, Magzhan",13,14,"plan")]),
 ("Database and backend: the critical path", True, [
  ("Schema","Ayan, Sultanbek",6,8,"plan"),
  ("Accounts, email verification, TOTP","Ayan, Sultanbek",8,10,"side"),
  ("Engine core and English strategy","Ayan, Sultanbek",8,11,"plan"),
  ("Locking, closing, sniping","Ayan, Sultanbek",10,12,"plan"),
  ("Real-time, transactions, step-up API","Ayan, Sultanbek",11,13,"plan"),
  ("Concurrency and load tests","Ayan, Sultanbek",12,14,"plan")]),
 ("Whole team", False, [
  ("MVP integration, final report, presentation","All five",13,14,"plan")]),
]
def gantt():
    out=['<div class="gantt" id="gantt" role="table" aria-label="Gantt chart, weeks 6 to 14">']
    out.append('<div class="g-head" role="row"><div class="g-name" role="columnheader">Task</div><div class="g-track weeks" role="columnheader">'+''.join(f'<span>W{w}</span>' for w in range(6,15))+'</div></div>')
    for gname,crit,rows in G:
        out.append(f'<div class="g-group{" crit" if crit else ""}" role="rowgroup"><div class="g-gtitle" role="row"><span role="cell">{e(gname)}</span></div>')
        for name,who,a,b,st in rows:
            word={"done":"done","plan":"planned","side":"planned, beside the critical path"}[st]
            out.append(f'<div class="g-row" role="row"><div class="g-name" role="cell"><b>{e(name)}</b><small>{e(who)} · weeks {a} to {b}</small></div>'
                       f'<div class="g-track" role="cell"><i class="bar {st}" style="grid-column:{a-5}/{b-4}" aria-label="{e(name)}, weeks {a} to {b}, {word}"></i></div></div>')
        out.append('</div>')
    out.append('</div>')
    return ''.join(out)

# ---------- PERT ----------
def node(n,w,d,cls=""):
    return f'<li class="node {cls}"><b>{e(n)}</b><span>{w}</span><em>{d}</em></li>'
BACK=[("Schema","W6 to W8","3 weeks"),("Engine core and English","W8 to W11","4 weeks"),("Locking, closing, sniping","W10 to W12","3 weeks"),("Real-time, transactions, step-up","W11 to W13","3 weeks"),("Concurrency and load tests","W12 to W14","3 weeks")]
FRONT=[("Wireframes and brand","W6 to W7","2 weeks","doneN"),("Contracts, React scaffold","W8 to W10","3 weeks",""),("Listing, browse, search","W9 to W11","3 weeks",""),("Live auction page","W11 to W13","3 weeks",""),("Checkout, usability test","W12 to W14","3 weeks","")]
def pert():
    b=''.join(node(*x) for x in BACK)
    f=''.join(node(x[0],x[1],x[2],x[3]) for x in FRONT)
    return f'''<div class="pert">
<div class="lane crit"><h3>Backend, critical path</h3><ol>{b}</ol><p class="lane-note">Accounts, email verification and TOTP (W8 to W10) run beside the engine and feed the login screens.</p></div>
<div class="lane"><h3>Front end and design, in parallel</h3><ol>{f}</ol><p class="lane-note">Interface contracts let this lane build against mocked responses until the API exists.</p></div>
<div class="join"><b>MVP integration, final report, presentation</b><span>W13 to W14</span><em>All five</em></div>
</div>'''

# ---------- Storyboard ----------
SB=[
("Hook",20,"Cover board, then many bids in one second","Imagine a thousand people bidding in the same second. Who wins, and how would you know it was fair?","Daniel"),
("The team",20,"Names, roles, advisor","Five students, one advisor, one question: can an auction stay correct under pressure?","Zhibek"),
("Problem and solution",30,"Four formats, one engine, one winner","Most platforms offer one or two selling formats. Adal offers four on one engine, with one winner and one price every time.","Daniel"),
("Sector assessment",30,"Comparison with eBay and the FloraHolland clock","We compared functionality, usability and design against the two systems we know best.","Daniel"),
("Brand language",25,"Mark, color, type, website and app boards","Adal means fair. The mark is two equal weights on a level beam, and the whole system follows it.","Zhibek"),
("Architecture and choices",40,"Stack diagram: React, Django, Channels, PostgreSQL, Docker","The browser talks to Django over REST and WebSockets. PostgreSQL decides who wins, by locking.","Zhibek"),
("Correctness",30,"State machine, one bid step by step, test result","Every bid takes the lock, is checked against the server clock, and either wins a place or is refused.","Ayan"),
("Demo: register, MFA, listing",40,"Screen recording","A seller registers, sets up a second factor, and lists an item with a hidden reserve.","Magzhan"),
("Demo: live bidding",45,"Split screen, two browsers","Two browsers bid. The price moves on both within a second, and the loser is told in words.","Sultanbek"),
("Demo: close and checkout",35,"Screen recording","The auction closes by itself, one winner, one transaction, and a fresh code finalizes the purchase.","Daniel"),
("Evidence",25,"Real numbers from the concurrency and load tests","Here is what happened when many bids arrived at once.","Ayan"),
("Project management",40,"Board, Gantt, PERT, roles","Tasks have one owner and one reviewer. The critical path is the backend chain, and we watch it weekly.","Sultanbek"),
("Rollout",30,"Fall MVP and spring phases","Fall delivers the English auction end to end. Spring adds three more formats and the admin side.","Zhibek"),
("Close",20,"Mark, thanks, next step","Fair is a property we can test. Thank you.","All five"),
]
def fmt(s): return f"{s//60}:{s%60:02d}"
def storyboard():
    tot=sum(x[1] for x in SB)
    t=0
    segs=[];rows=[]
    for i,(n,sec,scr,say,who) in enumerate(SB,1):
        segs.append(f'<a href="#ch{i}" class="seg s{i%2}" style="flex:{sec}" title="{e(n)}, {sec} seconds" aria-label="Chapter {i}: {e(n)}, {sec} seconds"></a>')
        rows.append(f'<li id="ch{i}" class="ch"><div class="ch-t"><b>{fmt(t)}</b><span>{sec} s</span></div><div class="ch-b"><h3>{e(n)}</h3><p class="scr">{e(scr)}</p><p class="say">{e(say)}</p></div><div class="ch-w">{e(who)}</div></li>')
        t+=sec
    ticks=''.join(f'<span style="left:{m*60/tot*100:.2f}%">{m}:00</span>' for m in range(0,7))
    return f'''<div class="ruler" aria-label="Video timeline, {fmt(tot)} in total"><div class="segs">{''.join(segs)}</div><div class="ticks">{ticks}<span style="left:100%">{fmt(tot)}</span></div></div>
<ol class="chs">{''.join(rows)}</ol>
<p class="sub">{len(SB)} chapters, {fmt(tot)} in total. The instructor said about 6 to 7 minutes: {TBC("confirm the exact length")}. To land on 6:00, merge the two project-management and rollout chapters and trim the demo by 30 seconds.</p>'''

ICON_CHECK='<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3.2 3L13 4.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ICON_Q='<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-dasharray="2.4 2"/></svg>'
ICON_DOWN='<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v9M4 8.5L8 12.5l4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ICON_DOT='<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="3.4" fill="currentColor"/></svg>'
ICON_CLOCK='<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 4.6V8l2.3 1.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
MARK=lambda ring,size=34:f'<svg width="{size}" height="{size}" viewBox="0 0 48 48" role="img" aria-label="Adal mark"><g class="beam"><path d="M6 28 H42" stroke="currentColor" stroke-width="4.2" stroke-linecap="round" fill="none"/><circle cx="13" cy="19.2" r="6.8" fill="currentColor"/><circle cx="35" cy="19.2" r="6.8" fill="currentColor"/></g><path d="M24 31 L18 43 H30 Z" fill="currentColor"/><circle cx="24" cy="28" r="3.9" fill="{ring}"/></svg>'

def done(): return f'<span class="st ok">{ICON_CHECK}Done</span>'
def tbc(): return f'<span class="st tbc-st">{ICON_Q}To confirm</span>'

CSS = open('style.css').read()
JS = open('script.js').read()
BODY = open('body.html').read()
BODY = (BODY.replace('{{GANTT}}',gantt()).replace('{{PERT}}',pert()).replace('{{STORY}}',storyboard())
        .replace('{{MARK_DARK}}',MARK('#DDBB70',44)).replace('{{MARK_LIGHT}}',MARK('#85601C',64)).replace('{{MARK_SM}}',MARK('#85601C',26))
        .replace('{{DONE}}',done()).replace('{{TBC}}',tbc()).replace('{{T}}',TBC())
        .replace('{{CHECK}}',ICON_CHECK).replace('{{DOWN}}',ICON_DOWN).replace('{{DOT}}',ICON_DOT).replace('{{CLOCK}}',ICON_CLOCK))
page=f'''<title>Adal Final Report</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,300;12..96,400;12..96,500;12..96,600&family=Instrument+Sans:wght@400;500;600;700&family=Outfit:wght@500&display=swap">
<style>
{CSS}
</style>
{BODY}
<script>
{JS}
</script>
'''
open('index.html','w').write(page)
print(len(page))
