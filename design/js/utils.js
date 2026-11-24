const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const LS={g:(k,d)=>{try{return JSON.parse(localStorage.getItem(k))??d}catch{return d}},s:(k,v)=>localStorage.setItem(k,JSON.stringify(v))};
const K={sess:"turalot_demo_session",sav:"turalot_saved_lots",fs:"turalot_followed_searches",fh:"turalot_followed_houses",bids:"turalot_demo_bids",reg:"turalot_registered"};
const P=new URLSearchParams(location.search),T$=n=>"₸"+Math.round(n).toLocaleString("ru-RU").replace(/\u00a0/g," ");
const lot=id=>LOTS.find(l=>l.id===id),auc=id=>AUCTIONS.find(a=>a.id===id),house=id=>HOUSES.find(h=>h.id===id),cat=id=>(CATS.find(c=>c[0]===id)||[0,id])[1];
const status=a=>Date.now()>a.endDate?"Completed":Date.now()>=a.startDate?"Live":"Upcoming";
const fmt=t=>new Date(t).toLocaleString("en-GB",{dateStyle:"medium",timeStyle:"short"});
const img=(l,i=0)=>l.images&&l.images[i]?l.images[i]:"data:image/svg+xml,"+encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 300'><rect width='300' height='300' fill='hsl(${(l.hue+i*20)%360},18%,${90-i*3}%)'/><text x='150' y='175' font-size='${100-i*8}' text-anchor='middle'>${l.icon}</text></svg>`);
const left=t=>{let s=Math.max(0,(t-Date.now())/1e3|0);return s?`${s/86400|0}d ${s%86400/3600|0}h ${s%3600/60|0}m ${s%60}s`:"Ended"};
function toast(m){let t=$("#toast");t.textContent=m;t.style.display="block";clearTimeout(t._t);t._t=setTimeout(()=>t.style.display="none",2600)}
const sess=()=>LS.g(K.sess,null);
function toggle(key,id){let a=LS.g(key,[]);a=a.includes(id)?a.filter(x=>x!==id):[...a,id];LS.s(key,a);return a.includes(id)}
const PAGE=document.body.dataset.page;const M=$("main");
const PAGES={};
setInterval(()=>$$("[data-cd]").forEach(e=>e.textContent=left(+e.dataset.cd)),1000);
function filterLots(ls,q,c,sort){q=(q||"").toLowerCase();ls=ls.filter(l=>(!q||(l.title+l.description+cat(l.category)+house(auc(l.auctionId).houseId).name).toLowerCase().includes(q))&&(!c||l.category==c));const S={lo:(a,b)=>a.currentBid-b.currentBid,hi:(a,b)=>b.currentBid-a.currentBid,end:(a,b)=>a.endDate-b.endDate,num:(a,b)=>a.lotNumber-b.lotNumber};return sort&&S[sort]?ls.sort(S[sort]):ls}
const sortSel=`<select id="sort" aria-label="Sort"><option value="num">Lot number</option><option value="lo">Price: low to high</option><option value="hi">Price: high to low</option><option value="end">Ending soon</option></select>`;
function followBtn(sel,key,id){const b=$(sel);if(b)b.onclick=()=>{const on=toggle(key,id);b.textContent=on?"Following":"Follow";toast(on?"Followed":"Unfollowed")}}
const ICON={heart:'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-4.6-9.5-9C.8 8.8 2.6 5 6.2 5c2 0 3.4 1.1 5.8 3.4C14.4 6.1 15.8 5 17.8 5c3.6 0 5.4 3.8 3.7 7-2.5 4.4-9.5 9-9.5 9z"/></svg>',search:'<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>'};
const PH="data:image/svg+xml,"+encodeURIComponent("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 300'><rect width='300' height='300' fill='#F2F4EE'/><text x='150' y='165' font-size='60' text-anchor='middle'>◻</text></svg>");
document.addEventListener("error",e=>{const i=e.target;if(i.tagName=="IMG"&&!i.dataset.fb){i.dataset.fb=1;i.src=PH}},true);
