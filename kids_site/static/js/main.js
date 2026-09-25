(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // header soyasi
  const header = $('#header');
  const onScroll = () => header && header.classList.toggle('scrolled', scrollY > 10);
  addEventListener('scroll', onScroll, { passive: true }); onScroll();

  // mobil menyu
  const mnav = $('#mnav');
  $$('[data-menu]').forEach(b => b.addEventListener('click', () => mnav.classList.add('open')));
  $$('[data-menu-close]').forEach(b => b.addEventListener('click', () => mnav.classList.remove('open')));
  mnav && mnav.addEventListener('click', e => { if (e.target === mnav) mnav.classList.remove('open'); });

  // qidiruv
  const ov = $('#searchOv');
  $$('[data-search]').forEach(b => b.addEventListener('click', () => {
    ov.classList.add('open'); setTimeout(() => $('input', ov).focus(), 50);
  }));
  ov && ov.addEventListener('click', e => { if (e.target === ov) ov.classList.remove('open'); });
  addEventListener('keydown', e => { if (e.key === 'Escape') { ov && ov.classList.remove('open'); mnav && mnav.classList.remove('open'); } });

  // yuqoriga
  $$('[data-top]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); scrollTo({ top: 0, behavior: 'smooth' }); }));

  // do'kon tanlanganda xaritani markazlash
  const frame = $('#mapFrame');
  $$('[data-store]').forEach(el => el.addEventListener('click', e => {
    if (e.target.closest('a')) return;
    $$('[data-store]').forEach(x => x.classList.remove('on'));
    el.classList.add('on');
    if (frame) {
      const u = new URL(frame.src);
      u.searchParams.set('ll', `${el.dataset.lon},${el.dataset.lat}`);
      u.searchParams.set('z', '16');
      frame.src = u.toString();
    }
  }));

  // vakansiyaga ariza — lavozimni formaga qo'yish
  $$('[data-apply]').forEach(a => a.addEventListener('click', () => {
    const inp = $('#subjectInput'); if (inp) inp.value = a.dataset.apply;
  }));

  // animatsiya
  const els = $$('.rv');
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(es => es.forEach(en => {
      if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
    }), { threshold: .12 });
    els.forEach((el, i) => { el.style.transitionDelay = (i % 4) * 80 + 'ms'; io.observe(el); });
  } else els.forEach(el => el.classList.add('in'));
})();
