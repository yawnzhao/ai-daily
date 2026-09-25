'use strict';
const sectionLinks = [...document.querySelectorAll('.reading-sidebar nav a')];
const sections = sectionLinks.map(link => document.querySelector(link.getAttribute('href'))).filter(Boolean);
let scheduled = false;
function updateReadingPosition() {
  const total = document.documentElement.scrollHeight - window.innerHeight;
  const progress = total > 0 ? Math.min(100, Math.max(0, window.scrollY / total * 100)) : 0;
  document.documentElement.style.setProperty('--progress', progress + '%');
  let current = sections[0];
  for (const section of sections) {
    if (section.getBoundingClientRect().top <= 140) current = section;
  }
  for (const link of sectionLinks) {
    if (current && link.hash === '#' + current.id) link.setAttribute('aria-current', 'true');
    else link.removeAttribute('aria-current');
  }
  scheduled = false;
}
function scheduleUpdate() {
  if (!scheduled) { scheduled = true; window.requestAnimationFrame(updateReadingPosition); }
}
window.addEventListener('scroll', scheduleUpdate, {passive:true});
window.addEventListener('resize', scheduleUpdate);
document.addEventListener('toggle', scheduleUpdate, true);
updateReadingPosition();
