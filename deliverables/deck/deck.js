(function(){
  var deck=document.getElementById('deck'),stage=document.getElementById('stage'),notes=document.getElementById('notes');
  var frames=[].slice.call(stage.querySelectorAll('.frame'));
  var veil=document.getElementById('veil'),edge=document.getElementById('edge');
  var hud={logo:document.getElementById('hudLogo'),fl:document.getElementById('hudFl'),fr:document.getElementById('hudFr'),prog:document.getElementById('prog')};
  var cntEl=document.getElementById('cnt'),progB=document.getElementById('progB');
  var N=frames.length,cur=0,step=0,reading=false,scale=1,anim=null;
  var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  var OVER={architecture:3,demoA:2,demoB:3,demoC:4};
  var DEMO={demoA:1,demoB:1,demoC:1};
  var cum=[];(function(){var t=0;frames.forEach(function(f,i){cum[i]=t;t+=+f.dataset.sec})})();
  function fmt(s){return Math.floor(s/60)+':'+('0'+(s%60)).slice(-2)}
  function $(id){return document.getElementById(id)}
  document.documentElement.classList.add('js');deck.classList.add('js');

  /* headings: words rise out of a level mask */
  [].forEach.call(stage.querySelectorAll('.h1,.h2,.close .q'),function(h){
    var n=0;
    (function walk(node){
      [].slice.call(node.childNodes).forEach(function(c){
        if(c.nodeType===3){
          var parts=c.textContent.split(/(\s+)/),frag=document.createDocumentFragment();
          parts.forEach(function(p){
            if(!p)return;
            if(/^\s+$/.test(p)){frag.appendChild(document.createTextNode(' '));return}
            var w=document.createElement('span');w.className='w';
            var i=document.createElement('span');i.className='wi';i.style.setProperty('--i',n++);i.textContent=p;
            w.appendChild(i);frag.appendChild(w);
          });
          node.replaceChild(frag,c);
        }else if(c.nodeType===1){walk(c)}
      });
    })(h);
  });

  function maxStep(i){
    var f=frames[i],m=OVER[f.dataset.id]||0;
    [].forEach.call(f.querySelectorAll('[data-s]'),function(el){m=Math.max(m,+el.dataset.s)});
    return m;
  }
  function setPrice(v,bump){[1,2].forEach(function(n){var el=$('pr'+n);if(!el)return;el.textContent=v;if(bump){el.classList.remove('bump');void el.offsetWidth;el.classList.add('bump')}})}
  var IC={check:'<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3.2 3L13 4.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
          down:'<svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v9M4 8.5L8 12.5l4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'};
  function pill(n,win){var p=$('pill'+n);if(!p)return;p.className='pill '+(win?'live':'out');p.innerHTML=(win?IC.check+'Winning':IC.down+'Outbid')}
  var hooks={
    architecture:function(s,f){
      var m={e1:s>=1&&s<2,bxA:s===1||s===2,e2:s===2,bxD:s===2,e3:s===3,bxB:s===3||s===1};
      Object.keys(m).forEach(function(k){var el=$(k);if(el)el.classList.toggle('hot',!!m[k])});
      [].forEach.call(f.querySelectorAll('[data-cap]'),function(el){el.classList.toggle('on',+el.dataset.cap===s)});
    },
    demoA:function(s){[].forEach.call(document.querySelectorAll('#codesA span'),function(el){el.classList.toggle('f',s>=1)})},
    demoB:function(s){
      var b=$('btn2');if(b)b.classList.toggle('press',s===1);
      if(s>=2){setPrice('250.00',s===2&&!reading);pill(1,false);pill(2,true)}
      else{setPrice('245.00',false);pill(1,true);pill(2,false)}
    },
    demoC:function(s){
      var c=$('cdn');if(c)c.textContent=s>=2?'00:00:00':'00:00:04';
      [].forEach.call(document.querySelectorAll('#codesC span'),function(el,i){el.textContent=s>=4?'731946'[i]:'';el.classList.toggle('f',s>=4)});
    }
  };
  function applyTo(i){
    var f=frames[i];
    [].forEach.call(f.querySelectorAll('[data-s]'),function(el){el.classList.toggle('on',+el.dataset.s<=step)});
    var h=hooks[f.dataset.id];if(h)h(step,f);
  }
  function syncInert(){
    frames.forEach(function(f,i){
      var off=!reading&&i!==cur;
      if(off){f.setAttribute('inert','');f.setAttribute('aria-hidden','true')}
      else{f.removeAttribute('inert');f.removeAttribute('aria-hidden')}
    });
  }
  function updateNotes(){
    var f=frames[cur];
    $('nTitle').textContent=(cur+1)+' of '+N+' · '+f.dataset.title;
    $('nTime').textContent=f.dataset.sec+' s · by '+fmt(cum[cur]+(+f.dataset.sec));
    $('nSay').textContent=f.dataset.note;
  }

  /* HUD follows the content: each piece changes colour as the edge passes it */
  function hudCfg(i){
    var f=frames[i],d=f.classList.contains('dark')?'dk':'lt';
    var c={logo:d,fl:d,fr:d};
    (f.dataset.hud||'').split(';').forEach(function(p){var kv=p.split(':');if(kv.length===2&&kv[0])c[kv[0]]=kv[1]});
    return c;
  }
  function setHud(k,v){var el=hud[k];if(!el)return;el.classList.toggle('dk',v==='dk');if(k==='logo')el.classList.toggle('gone',v==='none');if(k==='fl'){hud.prog.classList.toggle('dk',v==='dk')}}
  function setHudAll(c){['logo','fl','fr'].forEach(function(k){setHud(k,c[k])})}
  function setCounter(i){cntEl.textContent=('0'+(i+1)).slice(-2)+'/'+('0'+N).slice(-2);progB.style.width=((i+1)/N*100)+'%'}

  /* the beam rises, and settles level */
  function ease(p){return p<.5?8*p*p*p*p:1-Math.pow(-2*p+2,4)/2}
  function smooth(a,b,x){x=Math.max(0,Math.min(1,(x-a)/(b-a)));return x*x*(3-2*x)}
  function reset(f){f.style.clipPath='';f.style.opacity='';f.style.zIndex='';var s=f.querySelector('.slide');s.style.transform='';s.style.opacity=''}
  function go(to,dir){
    if(reading||to<0||to>=N||to===cur)return;
    if(anim)anim.finish();
    if(to===cur)return;
    var from=cur,A=frames[from],B=frames[to];
    var kind=(reduce||A.classList.contains('dark')||B.classList.contains('dark')||(DEMO[A.dataset.id]&&DEMO[B.dataset.id]))?'dissolve':'rise';
    var dur=reduce?260:(kind==='rise'?1300:1050);
    step=dir<0?maxStep(to):0;
    cur=to;syncInert();applyTo(to);
    var cA=hudCfg(from),cB=hudCfg(to);
    frames.forEach(function(f){f.classList.remove('cur')});
    A.classList.add('show');B.classList.add('show');
    A.style.zIndex=1;B.style.zIndex=3;
    B.classList.remove('rev');
    var raf,t0=null,revealed=false,counted=false;
    var yEl={logo:70,fl:1010,fr:1010};
    function render(e){
      var up=dir>0;
      if(kind==='rise'){
        var y0=up?1160-1240*e:-80+1240*e;
        var th=(up?-1:1)*3.4*Math.pow(1-e,2);
        var k=Math.tan(th*Math.PI/180)*960;
        B.style.clipPath=up
          ?'polygon(0px '+(y0-k)+'px,1920px '+(y0+k)+'px,1920px 1200px,0px 1200px)'
          :'polygon(0px -120px,1920px -120px,1920px '+(y0+k)+'px,0px '+(y0-k)+'px)';
        B.querySelector('.slide').style.transform='translateY('+((up?1:-1)*90*(1-e))+'px)';
        A.querySelector('.slide').style.transform='translateY('+((up?-1:1)*70*e)+'px)';
        veil.style.opacity=.32*e;
        edge.style.transform='translateY('+y0+'px) rotate('+th+'deg)';
        edge.style.opacity=Math.min(1,e*16)*(1-smooth(.86,1,e));
        ['logo','fl','fr'].forEach(function(key){
          var passed=up?y0<yEl[key]:y0>yEl[key];
          setHud(key,passed?cB[key]:cA[key]);
        });
      }else{
        B.style.opacity=e;
        B.querySelector('.slide').style.transform='scale('+(1.035-.035*e)+')';
        A.style.opacity=1-smooth(.25,1,e);
        ['logo','fl','fr'].forEach(function(key){setHud(key,e>.5?cB[key]:cA[key])});
      }
      if(!revealed&&e>(kind==='rise'?.5:.35)){revealed=true;B.classList.add('rev','cur')}
      if(!counted&&e>.5){counted=true;setCounter(to)}
    }
    function finish(){
      cancelAnimationFrame(raf);
      render(1);
      A.classList.remove('show','rev');
      reset(A);reset(B);
      B.classList.add('show','rev','cur');
      veil.style.opacity=0;edge.style.opacity=0;
      setHudAll(cB);setCounter(to);
      anim=null;
      updateNotes();
      try{history.replaceState(null,'','#slide-'+(to+1))}catch(x){}
    }
    anim={finish:finish};
    render(0);
    function tick(ts){
      if(t0===null)t0=ts;
      var p=Math.min(1,(ts-t0)/dur);
      render(kind==='rise'?ease(p):smooth(0,1,p));
      if(p<1)raf=requestAnimationFrame(tick);else finish();
    }
    raf=requestAnimationFrame(tick);
    updateNotes();
  }
  function jump(i){
    frames.forEach(function(f){f.classList.remove('show','cur','rev');reset(f)});
    cur=i;step=0;syncInert();applyTo(i);
    var f=frames[i];f.classList.add('show','cur');
    requestAnimationFrame(function(){f.classList.add('rev')});
    setHudAll(hudCfg(i));setCounter(i);updateNotes();
    try{history.replaceState(null,'','#slide-'+(i+1))}catch(x){}
  }
  function next(){if(anim){anim.finish()}if(step<maxStep(cur)){step++;applyTo(cur)}else if(cur<N-1)go(cur+1,1)}
  function prev(){if(anim){anim.finish()}if(step>0){step--;applyTo(cur)}else if(cur>0)go(cur-1,-1)}
  document.addEventListener('keydown',function(e){
    if(reading||e.metaKey||e.ctrlKey||e.altKey)return;
    var k=e.key;
    if(k==='ArrowRight'||k==='ArrowDown'||k==='PageDown'||k===' '||k==='Enter'){e.preventDefault();next()}
    else if(k==='ArrowLeft'||k==='ArrowUp'||k==='PageUp'||k==='Backspace'){e.preventDefault();prev()}
    else if(k==='Home'){if(anim)anim.finish();go(0,-1)}else if(k==='End'){if(anim)anim.finish();go(N-1,1)}
    else if(k==='n'||k==='N'){notes.classList.toggle('on')}
    else if(k==='f'||k==='F'){try{(deck.requestFullscreen||function(){}).call(deck)}catch(x){}}
  });
  stage.addEventListener('click',function(e){
    if(reading)return;
    var b=e.target.closest('[data-nav]');
    if(b){e.stopPropagation();(b.dataset.nav==='next'?next:prev)();return}
    next();
  });
  var tx=null;
  stage.addEventListener('touchstart',function(e){tx=e.touches[0].clientX},{passive:true});
  stage.addEventListener('touchend',function(e){if(tx===null||reading)return;var dx=e.changedTouches[0].clientX-tx;tx=null;if(Math.abs(dx)>60){e.preventDefault();dx<0?next():prev()}});
  function fit(){
    var cs=getComputedStyle(deck);
    var W=deck.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight);
    var H=deck.clientHeight;
    var was=reading;
    reading=W<820;
    deck.classList.toggle('read',reading);
    stage.classList.toggle('static',reading);
    syncInert();
    if(reading){
      scale=W/1920;
      frames.forEach(function(f,i){f.classList.add('show','cur','rev');f.style.width=W+'px';f.style.position='relative';var rn=f.querySelector('.rnote');if(!rn){rn=document.createElement('div');rn.className='rnote';var h=document.createElement('b');h.textContent=f.dataset.title;var p=document.createElement('p');p.textContent=f.dataset.note;rn.appendChild(h);rn.appendChild(p);f.appendChild(rn)}rn.style.top=(1080*scale)+'px';f.style.height=(1080*scale+rn.offsetHeight)+'px';f.querySelector('.slide').style.transform='scale('+scale+')';f.querySelector('.slide').style.transformOrigin='0 0';step=maxStep(i);applyTo(i)});
      stage.style.transform='';
    }else{
      scale=Math.min(W/1920,H/1080);
      stage.style.transform='scale('+scale+')';
      frames.forEach(function(f){var rn=f.querySelector('.rnote');if(rn)rn.remove();f.style.height='';f.style.width='';f.style.position='';var s=f.querySelector('.slide');s.style.transform='';s.style.transformOrigin=''});
      if(was)jump(cur);
    }
  }
  window.addEventListener('resize',fit);
  if(window.ResizeObserver)new ResizeObserver(fit).observe(deck);
  var m=/^#slide-(\d+)$/.exec(location.hash);
  var start=m?Math.max(0,Math.min(N-1,+m[1]-1)):0;
  window.addEventListener('hashchange',function(){var mm=/^#slide-(\d+)$/.exec(location.hash);if(mm&&!reading){var i=+mm[1]-1;if(i!==cur&&i>=0&&i<N)go(i,i>cur?1:-1)}});
  jump(start);
  fit();
})();
