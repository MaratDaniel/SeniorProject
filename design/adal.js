/* Adal motion helpers. Vanilla, no dependencies. Patterns follow Animate UI (animate-ui.com).
   Everything degrades to the static screen without JS and is calm under prefers-reduced-motion. */
(function(){
  var root=document.documentElement; root.classList.add('js');
  var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* sliding highlight: glide(container, {hover:true}) */
  function glide(el,o){
    o=o||{};
    if(el._glide){var e=el._glide; if(!e.g.parentNode) el.insertBefore(e.g,el.firstChild); e.snap(); return e;}
    var g=document.createElement('span'); g.className='glide snap'; g.setAttribute('aria-hidden','true');
    el.classList.add('has-glide'); el.insertBefore(g,el.firstChild);
    function kids(){return Array.prototype.filter.call(el.children,function(c){return c!==g})}
    function active(){return kids().filter(function(c){
      return c.getAttribute('aria-pressed')==='true'||c.getAttribute('aria-current')||(c.querySelector&&c.querySelector('input:checked'))})[0]||null}
    function place(c){
      if(!c){g.style.opacity='0';return}
      g.style.opacity='1';g.style.width=c.offsetWidth+'px';g.style.height=c.offsetHeight+'px';
      g.style.transform='translate('+c.offsetLeft+'px,'+c.offsetTop+'px)';
    }
    function sync(){place(active())}
    function snap(){g.classList.add('snap');sync();requestAnimationFrame(function(){requestAnimationFrame(function(){g.classList.remove('snap')})})}
    function top(t){while(t&&t.parentNode!==el)t=t.parentNode;return t&&t!==g?t:null}
    if(o.hover){
      el.addEventListener('mouseover',function(e){var c=top(e.target);if(c)place(c)});
      el.addEventListener('focusin',function(e){var c=top(e.target);if(c)place(c)});
      el.addEventListener('mouseleave',sync);
      el.addEventListener('focusout',function(){setTimeout(sync,0)});
    }
    el.addEventListener('click',function(){setTimeout(sync,0)});
    el.addEventListener('change',sync);
    new MutationObserver(sync).observe(el,{attributes:true,subtree:true,attributeFilter:['aria-pressed','aria-current']});
    window.addEventListener('resize',snap);
    if(document.fonts&&document.fonts.ready) document.fonts.ready.then(snap);
    el._glide={g:g,sync:sync,snap:snap}; snap(); return el._glide;
  }

  /* sliding number: num(el, "245.00") rolls each digit like a reel */
  function num(el,text){
    text=String(text);
    if(el._txt!==text){
      var rebuild=!el._built||el._txt.length!==text.length;
      if(rebuild){
        el.classList.add('snum','snap'); el.innerHTML='';
        var vh=document.createElement('span'); vh.className='vh'; el.appendChild(vh);
        text.split('').forEach(function(ch){
          var s=document.createElement('span'); s.setAttribute('aria-hidden','true');
          if(/\d/.test(ch)){s.className='d';var r=document.createElement('span');
            for(var i=0;i<10;i++){var b=document.createElement('b');b.textContent=i;r.appendChild(b)}
            s.appendChild(r)}
          else{s.className='c';s.textContent=ch}
          el.appendChild(s);
        });
        el._built=true;
        requestAnimationFrame(function(){requestAnimationFrame(function(){el.classList.remove('snap')})});
      }
      el.firstChild.textContent=text;
      var ch=text.split(''),reels=el.querySelectorAll('.d>span'),k=0;
      ch.forEach(function(c){if(/\d/.test(c)){reels[k++].style.transform='translateY(-'+(+c*1.1)+'em)'}});
      el._txt=text;
    }
  }

  /* toast: toast("Bid placed", "250.00") */
  function toast(title,body){
    var host=document.getElementById('toasts');
    if(!host){host=document.createElement('div');host.id='toasts';host.className='toasts';host.setAttribute('aria-live','polite');document.body.appendChild(host)}
    var t=document.createElement('div'); t.className='toast';
    t.innerHTML='<span class="t-ic"><svg class="icon" aria-hidden="true"><use href="#i-check"/></svg></span><div><b></b>'+(body?'<span></span>':'')+'</div>';
    t.querySelector('b').textContent=title; if(body) t.querySelector('span:not(.t-ic)').textContent=body;
    host.appendChild(t);
    setTimeout(function(){t.classList.add('out');setTimeout(function(){t.remove()},320)},4600);
  }

  window.Adal={glide:glide,num:num,toast:toast,reduce:reduce};

  document.addEventListener('DOMContentLoaded',function(){
    document.querySelectorAll('[data-glide]').forEach(function(el){glide(el,{hover:el.hasAttribute('data-glide-hover')})});

    /* accordion: one open at a time */
    document.querySelectorAll('.acc').forEach(function(acc){
      acc.addEventListener('click',function(e){
        var b=e.target.closest('.acc-btn'); if(!b)return;
        var item=b.closest('.acc-item'),open=!item.classList.contains('open');
        acc.querySelectorAll('.acc-item.open').forEach(function(i){i.classList.remove('open');i.querySelector('.acc-btn').setAttribute('aria-expanded','false')});
        if(open){item.classList.add('open');b.setAttribute('aria-expanded','true')}
      });
    });

    /* reveal once on scroll */
    var rv=[].slice.call(document.querySelectorAll('.reveal'));
    if('IntersectionObserver' in window&&!reduce){
      var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:.1,rootMargin:'0px 0px -5% 0px'});
      rv.forEach(function(el){io.observe(el)});
    } else rv.forEach(function(el){el.classList.add('in')});
  });
})();

/* resore-inspired: word-by-word headline, stepwise highlight of numbered steps */
(function(){
  if(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  function ready(f){document.readyState!=='loading'?f():document.addEventListener('DOMContentLoaded',f)}
  ready(function(){
    var h=document.querySelector('[data-words]'); if(h){
      var n=0;(function walk(el){Array.prototype.slice.call(el.childNodes).forEach(function(c){
        if(c.nodeType===3){var f=document.createDocumentFragment();c.nodeValue.split(/(\s+)/).forEach(function(t){
          if(!t)return; if(/^\s+$/.test(t)){f.appendChild(document.createTextNode(' '));return}
          var w=document.createElement('span');w.className='w';var s=document.createElement('span');s.textContent=t;s.style.setProperty('--i',n++);w.appendChild(s);f.appendChild(w)});
          el.replaceChild(f,c)}
        else if(c.nodeType===1) walk(c)})})(h);
    }
    var steps=document.querySelectorAll('.how .ruled>li'); if(steps.length&&'IntersectionObserver' in window){
      var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){
        Array.prototype.forEach.call(steps,function(s,i){setTimeout(function(){s.classList.add('on')},i*450)});io.disconnect()}})},{threshold:.4});
      io.observe(steps[0].parentNode);
    } else Array.prototype.forEach.call(steps,function(s){s.classList.add('on')});
  });
})();
