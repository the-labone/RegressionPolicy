const demos = [...document.querySelectorAll('.demo video')];
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const visibleDemos = new Set();

function updatePlayback() {
  for (const video of demos) {
    if (visibleDemos.has(video) && !document.hidden && !reducedMotion.matches) {
      video.play().catch(() => {
        // Keep the poster visible if the browser blocks autoplay.
      });
    } else {
      video.pause();
    }
  }
}

if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting && entry.intersectionRatio >= 0.25) {
        visibleDemos.add(entry.target);
      } else {
        visibleDemos.delete(entry.target);
      }
    }
    updatePlayback();
  }, { threshold: [0, 0.25] });

  demos.forEach(video => observer.observe(video));
  document.addEventListener('visibilitychange', updatePlayback);
  reducedMotion.addEventListener('change', updatePlayback);
}
