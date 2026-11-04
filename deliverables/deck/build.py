# -*- coding: utf-8 -*-
import html
def e(s): return html.escape(s, quote=True)
T = lambda t="to confirm": f'<span class="tbc">{t}</span>'

def mark(color="currentColor", ring="#85601C", size=56, beam=False):
    cls = ' class="beam"' if beam else ''
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 48 48" role="img" aria-label="Adal mark"><g{cls}>'
            f'<path d="M6 28 H42" stroke="{color}" stroke-width="4.2" stroke-linecap="round" fill="none"/>'
            f'<circle cx="13" cy="19.2" r="6.8" fill="{color}"/><circle cx="35" cy="19.2" r="6.8" fill="{color}"/></g>'
            f'<path d="M24 31 L18 43 H30 Z" fill="{color}"/><circle cx="24" cy="28" r="3.9" fill="{ring}"/></svg>')
LOGO_OLD = f'<div class="logo" style="position:absolute;left:120px;top:48px;display:flex;align-items:center;gap:14px;font-family:var(--serif);font-size:40px;color:var(--ink);z-index:4">{mark("#0F1512","#85601C",44)}<span>Adal</span></div>'

LOGO = ''
ICON = {
 'check':'<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3.2 3L13 4.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
 'down':'<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v9M4 8.5L8 12.5l4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
 'dot':'<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="3.4" fill="currentColor"/></svg>',
 'q':'<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-dasharray="2.4 2"/></svg>',
 'lock':'<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="10" width="16" height="11" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8 10V7a4 4 0 018 0v3" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
 'arrow':'<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
 'back':'<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M11 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
}

slides = []  # (id, title, seconds, say, cls, html)
def S(id, title, sec, say, body, cls=""):
    slides.append(dict(id=id, title=title, sec=sec, say=say, cls=cls, body=body))

# 1 intro
S("intro","Adal",5,"Adal. It means fair and honest, and we built an auction around that word.",
  f'<div class="lock">{mark("#F4F6F3","#DDBB70",230,True)}<span>Adal</span></div>', "dark intro")

# 2 cover
S("cover","Cover",10,"We are five students and one advisor, and we built an online auction that stays correct when many people bid at once.",
 f'''{LOGO}
<div class="pad"><h1 class="h1">An auction where every bid weighs the <i>same.</i></h1>
<p class="sub">An online auction service with four selling formats on one engine, correct under simultaneous bids.</p>
<div class="names"><span><b>Magzhan · Daniel · Sultanbek · Ayan · Zhibek</b></span><span>Advisor: Prof. Michel Lewis</span></div>
<div class="meta">SENIOR PROJECT · FALL 2026</div></div>
<div class="ph"><img src="./img/auction-room.jpg" alt="Hand-coloured print of Christie's Auction Room, London, 1808: a crowd in a skylit hall facing the auctioneer's rostrum" width="2000" height="1604"></div>''', "dark cover")

# 3 problem
S("problem","The problem",20,"Imagine two people bid at the same instant. If the system reads the price twice, both bids look valid, and there are two winners for one lot. An auction has to prevent that, every time.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">When two people bid in the same instant, who <i>wins?</i></h2>
<div class="two">
<div class="log" aria-label="Illustration of two simultaneous bids">
  <div class="top"><span>Auction closes <b>18:00:00</b></span><span>Current price <b>245.00</b></span></div>
  <div class="lr" data-s="1"><span class="tm">18:00:00.412</span><span><b>Bidder A</b> bids 250.00</span><span class="pill live">{ICON['check']}Accepted</span></div>
  <div class="lr" data-s="2"><span class="tm">18:00:00.412</span><span><b>Bidder B</b> bids 250.00</span><span class="pill q">{ICON['q']}Accepted?</span></div>
  <div class="clash" data-s="3">Two winners for one lot.</div>
  <div class="sm" style="margin-top:6px">Illustration. Times and amounts are examples.</div>
</div>
<div class="pts">
  <div data-s="4"><b>One winner, one price</b><span class="t">Every time, even under load.</span></div>
  <div data-s="5"><b>One clock</b><span class="t">The server decides what arrived in time, not the browser.</span></div>
  <div data-s="6"><b>Everyone sees it at once</b><span class="t">95% of watchers see a new bid within 1 second.</span></div>
</div></div></div>''')

# 4 formats
S("formats","Four formats, one engine",20,"Most platforms sell one way or two. Adal lets the seller pick: English, Dutch, sealed first-price or Vickrey. All four run on one engine, with one state machine, one lock and one clock. The fall MVP delivers English end to end.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">Four ways to sell, on <i>one</i> engine.</h2>
<div class="fm">
<div class="list">
  <div class="it" data-s="1"><b>English</b><span class="d">The price rises. The highest bid wins.</span><span class="tag">Fall MVP</span></div>
  <div class="it" data-s="2"><b>Dutch</b><span class="d">The price falls. The first to accept wins.</span><span class="tag sp">Spring 2027</span></div>
  <div class="it" data-s="3"><b>Sealed first-price</b><span class="d">One hidden bid each. The highest wins and pays it.</span><span class="tag sp">Spring 2027</span></div>
  <div class="it" data-s="4"><b>Vickrey</b><span class="d">One hidden bid each. The highest wins and pays the second price.</span><span class="tag sp">Spring 2027</span></div>
</div>
<div class="join" data-s="5"><svg viewBox="0 0 120 100" preserveAspectRatio="none" aria-hidden="true"><g fill="none" stroke="#98A39B" stroke-width="3"><path d="M0 12 C60 12 60 50 120 50"/><path d="M0 37 C60 37 60 50 120 50"/><path d="M0 63 C60 63 60 50 120 50"/><path d="M0 88 C60 88 60 50 120 50"/></g></svg></div>
<div class="engine" data-s="5"><h3>One auction engine</h3><p>One state machine, one lock, one server clock. Each format only decides what a valid bid is and who wins.</p><span class="win" data-s="6">{ICON['check']}One winner, one price</span></div>
</div></div>''')

# 5 sector
S("sector","Sector assessment",25,"We compared Adal with two systems that define the field for us: eBay, with ascending bids and automatic bidding, and the Royal FloraHolland clock, where the price falls. We scored functionality, usability and design on the same pages.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">How Adal compares with the <i>sector.</i></h2>
<div class="tb" role="table" aria-label="Comparison with eBay and the FloraHolland clock">
<div class="r" role="row"><div class="h" role="columnheader" aria-label="Criterion"></div><div class="h" role="columnheader">eBay</div><div class="h" role="columnheader">FloraHolland clock</div><div class="h usb" role="columnheader">Adal</div></div>
<div class="r" role="row"><div role="rowheader" class="k" data-s="1">Selling format</div><div role="cell" data-s="1">Ascending bids, automatic bidding</div><div role="cell" data-s="1">Falling-price clock</div><div role="cell" class="us usb" data-s="1">Four formats, chosen per listing</div></div>
<div class="r" role="row"><div role="rowheader" class="k" data-s="2">Simultaneous bids</div><div role="cell" data-s="2">Highest bid wins; proxy raises it up to your maximum</div><div role="cell" data-s="2">First buyer to stop the clock takes the lot</div><div role="cell" class="us usb" data-s="2">Row locking, one winner, tested</div></div>
<div class="r" role="row"><div role="rowheader" class="k" data-s="3">Live updates</div><div role="cell" data-s="3">Price and bids refresh on the listing page</div><div role="cell" data-s="3">Live clock, buy remotely or in the hall</div><div role="cell" class="us usb" data-s="3">95% within 1 second</div></div>
<div class="r" role="row"><div role="rowheader" class="k" data-s="4">Security</div><div role="cell" data-s="4">Account login; two-step optional</div><div role="cell" data-s="4">Buyer account; to check</div><div role="cell" class="us usb" data-s="4">MFA at login and at purchase</div></div>
<div class="r" role="row"><div role="rowheader" class="k" data-s="5">Usability, 1 to 5</div><div role="cell" data-s="5">{T("score")}</div><div role="cell" data-s="5">{T("score")}</div><div role="cell" class="us usb" data-s="5">{T("score")}</div></div>
<div class="r" role="row"><div role="rowheader" class="k" data-s="6">Design, 1 to 5</div><div role="cell" data-s="6">{T("score")}</div><div role="cell" data-s="6">{T("score")}</div><div role="cell" class="us usb" data-s="6">{T("score")}</div></div>
</div>
<p class="sm">Sources: eBay and Royal FloraHolland help pages, 4 Nov 2026. Security cells and scores: {T("team to confirm")}.</p></div>''')

# 6 different
S("different","Where Adal is different",15,"Three things set Adal apart: four formats on one engine, correctness we can test, and a second code at the moment of purchase. And we are clear about what we do not do.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">Where Adal is <i>different.</i></h2>
<div class="big3 narrow">
<div data-s="1"><b>Four formats on <i>one</i> engine</b><p>A seller picks the right way to sell each item, and the rules never change underneath.</p></div>
<div data-s="2"><b>Correctness we can <i>test</i></b><p>Simultaneous bids are a test case, with a number to show, not a promise.</p></div>
<div data-s="3"><b>A second code at the <i>purchase</i></b><p>Logging in is not enough. Finalizing a purchase asks for a fresh code.</p></div>
</div>
<p class="sm" data-s="4">Out of scope by design: real payments, identity checks (KYC), fraud scoring, native mobile apps.</p></div>
<div class="bigph"><img decoding="async" src="./img/balance.jpg" alt="A gilt brass balance on a marble base, its two empty pans level" width="1500" height="1125"></div>''')

# 6b name
S("name","The name and the mark",15,"Adal is a Kazakh word. It means fair and honest, and that is the one promise an auction cannot break. The mark is the idea drawn: two equal weights, one level beam, one pivot. Everything else in the brand follows from that.",
 f'''<div class="pad"><p class="wm">Adal</p>
<div class="def"><b>Fair, honest. <i>Adal.</i></b><span>A Kazakh word, and the one promise an auction cannot break.</span></div>
<div class="nhow"><span data-s="1"><b>Two equal weights</b>Every bidder is the same size.</span><span data-s="2"><b>One level beam</b>The same facts reach everyone.</span><span data-s="3"><b>One pivot</b>The server, never the browser, decides.</span></div></div>
<div class="plate"><img decoding="async" src="./img/beam.jpg" alt="A 16th-century beam balance: an iron beam with a hook at each end, hanging level from a central ring" width="1460" height="1800"><div class="cp">A beam balance, 16th century. The Metropolitan Museum of Art, public domain.</div></div>''', "dark name")

# 7 brand
S("brand","Brand language",20,"The brand follows the name. Two equal weights on a level beam. Cool white and deep moss, one brass accent used only for what needs attention. A light grotesque for statements, a clear text face for everything read, and one bidding desk that gives every bidder the same facts.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">A brand that looks <i>fair.</i></h2>
<div class="br">
<div class="l">
  <div class="mk2" data-s="1"><div class="a">{mark("#0F1512","#85601C",96)}<span>Adal</span></div><div class="b">{mark("#F4F6F3","#DDBB70",96)}<span>Adal</span></div></div>
  <div class="sw" data-s="2" role="img" aria-label="Palette: paper, moss, ink, brass"><div style="flex:4;background:#F4F6F3;color:#0F1512"><b>Paper</b>#F4F6F3</div><div style="flex:3;background:#3B5F4F;color:#F4F6F3"><b>Moss</b>#3B5F4F</div><div style="flex:2;background:#0F1512;color:#F4F6F3"><b>Ink</b>#0F1512</div><div style="flex:1.2;background:#85601C;color:#F4F6F3"><b>Brass</b>#85601C</div></div>
  <div class="spec" data-s="3"><div class="a">Bricolage<small>Light, for statements</small></div><div class="b">245.00<small>Instrument Sans, tabular figures</small></div></div>
</div>
<div data-s="4"><div class="desk" aria-label="The bidding desk, an illustration">
  <div class="top"><span>Current price</span><span class="pill live">{ICON['dot']}Live</span></div>
  <div class="pr">245.00</div>
  <div class="wh"><b>Ends in 02:14:09</b> · Closes Thursday 12 November, 18:00</div>
  <div class="pre"><span class="sel">250.00</span><span>255.00</span><span>265.00</span></div>
  <div class="lg">A bid is a binding commitment to buy.</div>
  <div class="btn">Place bid · 250.00</div></div></div>
</div></div>''')

# 8 architecture
S("architecture","Architecture and implementation choices",30,"Three layers in Docker. The browser, built in React, sends actions over REST and listens over a WebSocket. Django applies the rules in one auction engine. PostgreSQL decides who won, by locking the auction row, so the browser can never be the authority.",
 f'''{LOGO}
<div class="pad" style="bottom:210px"><h2 class="h2">Three layers, one source of <i>truth.</i></h2>
<div class="dock"><span class="cap">Docker: the same stack on every machine</span>
<div class="bx" id="bxB"><h3>Browser</h3><div class="chips"><span class="k">React</span><span>Responsive app</span><span>Live price</span></div></div>
<div class="ed"><div class="ln r" id="e1"><span>REST</span><i></i></div><div class="ln l" id="e3"><i></i><span>WebSocket</span></div></div>
<div class="bx" id="bxA"><h3>Application</h3><div class="chips"><span class="k">Django REST</span><span class="k">Channels</span><span>Auction engine</span><span>Four strategies</span></div></div>
<div class="ed"><div class="ln r" id="e2"><span>one transaction</span><i></i></div></div>
<div class="bx" id="bxD"><h3>Data</h3><div class="chips"><span class="k">PostgreSQL</span><span>Row locks</span><span>Audit log</span></div></div>
</div></div>
<div class="cap2"><span data-cap="1">The browser sends the bid over REST. Its clock plays no part.</span><span data-cap="2">The auction row is locked, the bid checked, the price written.</span><span data-cap="3">Channels broadcasts the new price to every watcher.</span></div>''')

# 9 correctness
S("correctness","Correctness",25,"One bid, step by step. The auction row is locked, so a second bid waits its turn. Three checks decide: is the auction active, is it before the close on the server clock, and does the amount beat the price. Then the bid is written, the closing time may extend, and the lock is released. An auction only moves forward through its states.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">One bid, one <i>lock.</i></h2>
<div class="ob">
<div class="sl">
 <div data-s="1"><p style="margin:0"><b>The row is locked</b><span>Any other bid on this auction waits its turn.</span></p></div>
 <div data-s="2"><p style="margin:0"><b>Three checks</b><span>Active. Before the close on the server clock. Amount beats the price by the minimum increment ({T("value")}).</span></p></div>
 <div data-s="3"><p style="margin:0"><b>Write and extend</b><span>The bid and price are stored. A bid near the end extends the close ({T("length")}).</span></p></div>
 <div data-s="4"><p style="margin:0"><b>Commit, release, broadcast</b><span>The next bid is checked against the new price. Watchers are updated.</span></p></div>
</div>
<div class="st" data-s="5"><h3>Life of an auction</h3>
 <span class="node">Scheduled</span><span class="dn"></span><span class="node">Active</span><span class="dn"></span>
 <div class="cap3">Ends in one of three outcomes</div>
 <div class="br2"><span class="node end">Closed, one winner</span><span class="node">No sale</span><span class="node bad">Cancelled</span></div>
</div></div></div>''')

# 10 demo A
S("demoA","Demo: account and listing",20,"The demo starts with a seller. Registration needs email verification and a second factor, mandatory for sellers. Then the seller lists an item: the format, the start, the end, and a reserve that bidders never see.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">A seller is secured, then <i>lists.</i></h2>
<div class="demo" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
<div class="win2" data-s="1"><div class="bar"><i></i><i></i><i></i><span>adal.example / account / security</span></div><div class="bd">
  <h4>Confirm your second factor</h4><p class="note">Enter the 6-digit code from your authenticator app.</p>
  <div class="codes" id="codesA"><span>4</span><span>8</span><span>2</span><span>9</span><span>0</span><span>1</span></div>
  <div class="btn" style="margin-top:auto">Confirm</div></div></div>
<div class="win2" data-s="2"><div class="bar"><i></i><i></i><i></i><span>adal.example / sell / new</span></div><div class="bd">
  <h4>List an item</h4>
  <div class="fld"><label>Selling format</label><div>English auction<span class="sm">Fall MVP</span></div></div>
  <div class="fld"><label>Closes</label><div>Thursday 12 November, 18:00</div></div>
  <div class="fld"><label>Reserve price</label><div>Hidden from bidders</div><small>Bidders only see whether the reserve is met.</small></div></div></div>
</div></div>''')

# 11 demo B
def buyer(n, lab, pill, pr, sel="250.00"):
    return f'''<div class="win2"><div class="bar"><i></i><i></i><i></i><span>{lab}</span></div><div class="bd" style="gap:16px">
  <div class="lot"><div class="ph2"><img decoding="async" src="./img/scales.jpg" alt="A wooden box of brass weights beside a small pair of balance scales, the demo lot" width="1535" height="1800"></div>
  <div class="mini">
    <div class="top" style="display:flex;justify-content:space-between;align-items:center"><span class="lbl">Current price</span><span class="pill live" id="pill{n}">{pill}</span></div>
    <div class="pr2" id="pr{n}">{pr}</div>
    <div class="timer"><b style="color:var(--ink)">Ends in 00:12:40</b> · Closes 18:00</div>
    <div class="pre"><span class="sel">250.00</span><span>255.00</span><span>265.00</span></div>
    <div class="btn" id="btn{n}">Place bid · 250.00</div></div></div></div></div>'''
S("demoB","Demo: live bidding",30,"Now two buyers in two browsers. Buyer one is winning at 245. Buyer two bids 250. The price changes on both screens within a second, and buyer one is told in words that they were outbid. The server decided the order, not either browser.",
 f'''{LOGO}
<div class="pad" style="gap:28px"><h2 class="h2">Two browsers, one <i>price.</i></h2>
<div class="demo" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
{buyer(1,"Buyer one",ICON['check']+"Winning","245.00")}
{buyer(2,"Buyer two",ICON['down']+"Outbid","245.00")}
</div>
<div class="strip" data-s="3" id="stripB">{ICON['check']}Same price on every screen. The server decided the order.</div></div>''')

# 12 demo C
S("demoC","Demo: close and checkout",25,"The clock runs down. A late bid would extend it, sniping protection. Then the auction closes by itself with one winner. To finish, the winner enters a fresh code, and exactly one transaction and one audit entry are written.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">The auction closes. The winner <i>pays.</i></h2>
<div class="demo" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
<div class="win2"><div class="bar"><i></i><i></i><i></i><span>adal.example / auction / closing</span></div><div class="bd">
  <span class="lbl">Closes Thursday 12 November, 18:00</span>
  <div class="cdn" id="cdn">00:00:04</div>
  <div class="strip" data-s="1" style="background:var(--clay-tint);color:var(--clay)">{ICON['q']}A bid in the last minute extends the close</div>
  <div class="strip" data-s="2" id="closedStrip">{ICON['check']}Closed · one winner · 250.00</div></div></div>
<div class="win2" data-s="3"><div class="bar"><i></i><i></i><i></i><span>adal.example / checkout</span></div><div class="bd">
  <h4>Confirm your purchase</h4><p class="note">Enter a new code from your authenticator app.</p>
  <div class="codes" id="codesC"><span></span><span></span><span></span><span></span><span></span><span></span></div>
  <div class="strip" data-s="4" style="margin-top:auto">{ICON['check']}One transaction · one audit entry</div></div></div>
</div></div>''')

# 13 evidence
S("evidence","Evidence",10,"Tested, not claimed. Here is what happened when many bids arrived at once, what share of watchers saw the price within a second, and how first-time bidders did.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">Tested, not <i>claimed.</i></h2>
<div class="ev">
<div data-s="1"><b>Simultaneous bids</b><p>{T("N")} bids at the same instant: <strong>1</strong> winner, {T("0")} duplicate transactions<small>Concurrency test. Replace with the real result.</small></p></div>
<div data-s="2"><b>Live updates</b><p>{T("X")}% of watchers saw the new price within 1 second<small>Target: 95%.</small></p></div>
<div data-s="3"><b>Usability</b><p>{T("n")} of {T("n")} first-time bidders placed a bid without help<small>Usability test, week 13 to 14.</small></p></div>
</div></div>''')

# 14 team
S("team","Team and method",30,"Who does what. Ayan and Sultanbek own the backend and database. Magzhan builds the React front end. Daniel owns design and this presentation. Zhibek owns architecture, interface contracts and the feature comparison. We work from one board, one owner and one reviewer per task, short weekly iterations, and concurrency tests that start beside the locking work.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">Who does what, and how we <i>work.</i></h2>
<div class="tm">
<div class="who">
 <div data-s="1"><b>Ayan</b><span>Database, engine, locking, tests</span></div>
 <div data-s="1"><b>Sultanbek</b><span>Backend, real-time, transactions, step-up API</span></div>
 <div data-s="2"><b>Daniel</b><span>Design system, brand, wireframes, this presentation, usability test</span></div>
 <div data-s="2"><b>Magzhan</b><span>React front end: login, listings, live auction page, checkout</span></div>
 <div data-s="3"><b>Zhibek</b><span>Architecture, interface contracts, feature comparison, reviews, demo script</span></div>
</div>
<div class="how">
 <div data-s="4"><b>Method</b><span>Requirements first, then weekly iterations. {T("method name")}</span></div>
 <div data-s="5"><b>Tools</b><span>GitHub Projects board, branches and pull requests, one reviewer per merge. Chat: {T("tool")}</span></div>
 <div data-s="6"><b>Rhythm</b><span>Weekly sync {T("day and time")}, advisor meetings with Prof. Lewis. Lead: {T("name")}</span></div>
</div></div></div>''')

# 15 gantt
GR = [
 ("Design and comparison",None),
 ("Feature comparison","Zhibek",6,8,"plan"),("Architecture, state machine","Zhibek",6,7,"done"),("Interface contracts, design reviews","Zhibek",8,13,"plan"),
 ("Front end",None),
 ("Wireframes and brand","Daniel",6,7,"done"),("Scaffold, login, MFA screens","Magzhan, Daniel",8,10,"plan"),("Listing, browse, search","Magzhan, Daniel",9,11,"plan"),("Live auction page, checkout","Magzhan, Daniel",11,13,"plan"),("Usability test","Daniel, Magzhan",13,14,"plan"),
 ("Backend: the critical path",None),
 ("Schema","Ayan, Sultanbek",6,8,"crit"),("Accounts, email, TOTP","Ayan, Sultanbek",8,10,"side"),("Engine core, English strategy","Ayan, Sultanbek",8,11,"crit"),("Locking, closing, sniping","Ayan, Sultanbek",10,12,"crit"),("Real-time, transactions, step-up","Ayan, Sultanbek",11,13,"crit"),("Concurrency and load tests","Ayan, Sultanbek",12,14,"crit"),
 ("Whole team",None),
 ("MVP integration, report, presentation","All five",13,14,"crit"),
]
def gantt():
    o=['<div class="gt" role="table" aria-label="Gantt chart, weeks 6 to 14"><div class="r" role="row"><div class="h n" role="columnheader">Task</div>'+''.join(f'<div class="h" role="columnheader">W{w}</div>' for w in range(6,15))+'</div>']
    for r in GR:
        if r[1] is None:
            o.append(f'<div class="r" role="row"><div class="g" role="rowheader">{e(r[0])}</div></div>'); continue
        name,who,a,b,st=r
        o.append(f'<div class="r" role="row"><div class="n" role="rowheader"><span>{e(name)}</span><small>{e(who.split(",")[0] if "," in who else who)}{"" if "," not in who else " +"}</small></div>')
        for w in range(6,15):
            if a<=w<=b:
                if w==a: o.append(f'<div class="c" style="grid-column:{w-4}/{b-4+1}"><i class="bar {st}" aria-label="{e(name)}, weeks {a} to {b}"></i></div>')
            else: o.append(f'<div class="c" style="grid-column:{w-4}"></div>')
    o.append('</div>')
    return ''.join(o)
# fix: empty cells before and after bar need correct placement; rebuild with explicit placement
def gantt2():
    o=['<div class="gt" role="table" aria-label="Gantt chart, weeks 6 to 14"><div class="r" role="row"><div class="h n" role="columnheader">Task</div>'+''.join(f'<div class="h" role="columnheader">W{w}</div>' for w in range(6,15))+'</div>']
    for r in GR:
        if r[1] is None:
            o.append(f'<div class="r" role="row"><div class="g" role="rowheader">{e(r[0])}</div></div>'); continue
        name,who,a,b,st=r
        first=who.split(",")[0]
        o.append(f'<div class="r" role="row"><div class="n" role="rowheader"><span>{e(name)}</span><small>{e(first)}{" +" if "," in who else ""}</small></div>')
        if a>6: o.append(f'<div class="c" role="cell" style="grid-column:2/{a-4}"></div>')
        o.append(f'<div class="c" role="cell" style="grid-column:{a-4}/{b-3}"><i role="img" class="bar {st}" aria-label="{e(name)}, weeks {a} to {b}"></i></div>')
        if b<14: o.append(f'<div class="c" role="cell" style="grid-column:{b-3}/11"></div>')
        o.append('</div>')
    o.append('<div class="now" style="left:calc(600px + (100% - 600px) * 5 / 9)" aria-hidden="true"><b>Start of W11</b></div></div>')
    return ''.join(o)
S("gantt","Gantt chart",20,"This is the schedule, weeks six to fourteen. Filled bars are done: the design and the brand. The line marks where we are, the start of week eleven. The backend chain, outlined in black, is the critical path. Everything converges on integration, the report and the presentation in weeks thirteen and fourteen.",
 f'''{LOGO}
<div class="pad" style="gap:14px;top:120px;bottom:128px"><div style="display:flex;justify-content:space-between;align-items:flex-end;gap:40px"><h2 class="h2" style="font-size:52px;white-space:nowrap">Schedule, weeks 6 to <i>14.</i></h2>
<div class="gl"><span><i class="bar done"></i>Done</span><span><i class="bar plan" style="width:44px"></i>Planned</span><span><i class="bar crit" style="width:44px"></i>Critical path</span></div></div>
{gantt2()}<p class="sm" style="margin-top:-4px">Week windows come from the work packages. Weeks to dates: {T("course calendar")}</p></div>''')

# 16 pert
BACK=[("Schema","W6 to W8","3 weeks","e","Planned before W11"),("Engine and English","W8 to W11","4 weeks","n","Running now"),("Locking, closing, sniping","W10 to W12","3 weeks","n","Running now"),("Real-time, transactions","W11 to W13","3 weeks","n","Starts now"),("Concurrency, load tests","W12 to W14","3 weeks","l","Later")]
FRONT=[("Wireframes, brand","W6 to W7","2 weeks","e","Done"),("Contracts, scaffold","W8 to W10","3 weeks","e","Planned before W11"),("Listing, browse, search","W9 to W11","3 weeks","n","Running now"),("Live page","W11 to W13","3 weeks","n","Starts now"),("Checkout, usability test","W12 to W14","3 weeks","l","Later")]
def lane(items,cls,title):
    li=''.join(f'<li class="{s}"><b>{e(a)}</b><span>{b}</span><em>{c}</em><i class="tg">{t}</i></li>' for a,b,c,s,t in items)
    return f'<div class="ln2 {cls}"><h3>{title}</h3><ol>{li}</ol></div>'
S("pert","PERT network",15,"The same plan as a dependency network. The backend chain has no slack: a slip anywhere on it moves the MVP. The front end runs in parallel against mocked responses, so it can keep moving while the API is built.",
 f'''{LOGO}
<div class="pad" style="top:130px;gap:26px"><h2 class="h2" style="font-size:60px">Critical path: the backend <i>chain.</i></h2>
<div class="pn"><span>Where we stand at the start of week 11, by the plan:</span><span><i class="e"></i>Window passed</span><span><i class="n"></i>Running now</span><span><i></i>Later</span></div>
<div class="pt">
<div data-s="1">{lane(BACK,"crit","Backend, no slack")}</div>
<div data-s="2">{lane(FRONT,"","Front end and design, in parallel")}</div>
<div class="jn" data-s="3"><b>MVP integration, report, presentation</b><span>W13 to W14 · all five</span></div>
</div></div>''')

# 17 rollout
S("rollout","Rollout timeline",20,"The rollout runs in an order that lets every step be shown on its own: foundation, identity, the auction core, live and paid, and proof. Spring 2027 adds the other three formats, notifications, the admin dashboard and the full evaluation.",
 f'''{LOGO}
<div class="pad"><h2 class="h2">From foundation to proof, then three more <i>formats.</i></h2>
<div class="rd">
<div class="p dn" data-s="1"><span class="w">Weeks 6 to 8</span><span class="dot"></span><h3>Foundation</h3><p>Schema, architecture, wireframes, brand</p></div>
<div class="p" data-s="2"><span class="w">Weeks 8 to 10</span><span class="dot"></span><h3>Identity</h3><p>Accounts, email, TOTP, login screens</p></div>
<div class="p" data-s="3"><span class="w">Weeks 8 to 12</span><span class="dot"></span><h3>Auction core</h3><p>Engine, English, locking, closing, listings</p></div>
<div class="p" data-s="4"><span class="w">Weeks 11 to 13</span><span class="dot"></span><h3>Live and paid</h3><p>Real-time, transactions, step-up MFA, checkout</p></div>
<div class="p" data-s="5"><span class="w">Weeks 12 to 14</span><span class="dot"></span><h3>Proof</h3><p>Concurrency and load tests, usability, report</p></div>
<div class="p sp" data-s="6"><span class="w">Spring 2027</span><span class="dot"></span><h3>Beyond the MVP</h3><p>Dutch, sealed, Vickrey, notifications, admin, evaluation</p></div>
</div></div>''')

# 18 close
S("close","Close",10,"Fair is a property we can test. Thank you.",
 f'''<div class="bgp"><img decoding="async" src="./img/rowlandson.jpg" alt="" width="2000" height="1412"></div><div class="c"><div style="color:#F4F6F3">{mark("#F4F6F3","#DDBB70",120)}</div>
<div class="q">Fair is a property we can <i>test.</i></div>
<div class="nm"><span>Magzhan · Daniel · Sultanbek · Ayan · Zhibek</span><span>Advisor: Prof. Michel Lewis</span></div></div>''', "dark close")

N = len(slides)
KEEP={'cover','problem','brand','close'}
import re as _re
for s in slides:
    if s['id'] not in KEEP:
        s['body']=_re.sub(r'(<h2 class="h2"[^>]*>)(.*?)(</h2>)',lambda m:m.group(1)+m.group(2).replace('<i>','').replace('</i>','')+m.group(3),s['body'],flags=_re.S)
        if s['id']=='different':
            s['body']=s['body'].replace('<i>','').replace('</i>','')
HUDFLAGS={'intro':'logo:none','close':'logo:none'}

out=[]
for i,s in enumerate(slides):
    note=f'data-note="{e(s["say"])}" data-sec="{s["sec"]}" data-title="{e(s["title"])}" data-id="{s["id"]}" data-hud="{HUDFLAGS.get(s["id"],"")}"'
    dark=' dark' if 'dark' in s['cls'] else ''
    out.append(f'<div class="frame{dark}" {note}><section class="slide {s["cls"]}" aria-label="{e(s["title"])}">{s["body"]}</section></div>')

tot=sum(s['sec'] for s in slides)
BODY = f'''<div class="deck" id="deck"><div class="stage" id="stage"><div class="layers">{''.join(out)}</div>
<div class="veil" id="veil"></div><div class="edge" id="edge"></div>
<div class="hud" id="hud"><div class="logo" id="hudLogo">{mark("currentColor","var(--ring)",44)}<span>Adal</span></div>
<div class="fl" id="hudFl">ADAL · SENIOR PROJECT · FALL 2026</div>
<div class="fr" id="hudFr"><span id="cnt">01/{N:02d}</span><span class="nav"><button type="button" data-nav="prev" aria-label="Previous">{ICON['back']}</button><button type="button" data-nav="next" aria-label="Next">{ICON['arrow']}</button></span></div>
<div class="prog" id="prog"><b id="progB"></b></div></div><div class="notes" id="notes"><div class="m"><span id="nTitle"></span><b id="nTime"></b></div><div class="say" id="nSay"></div></div></div></div>
<noscript><p style="color:#F4F6F3;padding:24px">This deck needs JavaScript to show slides.</p></noscript>'''

CSS=open('deck.css').read().replace('.pad{position:absolute;left:120px;right:120px;top:96px;bottom:150px','.pad{position:absolute;left:120px;right:120px;top:150px;bottom:140px')
JS=open('deck.js').read().replace('__TOTAL__',str(tot))
page=f'''<title>Adal Final Presentation</title>
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
print(N,'slides',tot,'seconds',len(page))
