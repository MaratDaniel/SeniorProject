(function(){
  function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
  function set(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  var g=document.getElementById('gantt'),sel=document.getElementById('nowsel');
  function setNow(w){
    if(w){g.setAttribute('data-now','1');g.style.setProperty('--now',(+w-6+1))}
    else{g.removeAttribute('data-now')}
  }
  if(g&&sel){
    var s=get('adal-now');if(s){sel.value=s;setNow(s)}
    sel.addEventListener('change',function(){set('adal-now',sel.value);setNow(sel.value)});
  }
  document.querySelectorAll('#todo input').forEach(function(i){
    var k='adal-todo-'+i.dataset.k;i.checked=get(k)==='1';
    i.addEventListener('change',function(){set(k,i.checked?'1':'0')});
  });
  var links=[].slice.call(document.querySelectorAll('.rail a'));
  if('IntersectionObserver' in window&&links.length){
    var map={};links.forEach(function(a){map[a.getAttribute('href').slice(1)]=a});
    var io=new IntersectionObserver(function(es){
      es.forEach(function(en){if(en.isIntersecting){links.forEach(function(a){a.classList.remove('on')});map[en.target.id].classList.add('on')}});
    },{rootMargin:'-20% 0px -70% 0px'});
    Object.keys(map).forEach(function(id){var el=document.getElementById(id);if(el)io.observe(el)});
  }
})();
