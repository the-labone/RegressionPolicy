const figure = document.querySelector('[data-efficiency-figure]');

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function enhanceEfficiency() {
  if (!figure) return;
  const response = await fetch(new URL('./assets/data/efficiency.json', import.meta.url));
  if (!response.ok) return;
  const data = await response.json();
  const models = data.models.map(model => ({
    name: model.name,
    flow: Number(model.latency_ms.Flow),
    ht: Number(model.latency_ms.HT),
  }));
  if (!models.length || models.some(model => !Number.isFinite(model.flow)
      || !Number.isFinite(model.ht) || model.ht <= 0 || model.flow < model.ht)) return;

  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const number = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const chart = element('div', 'efficiency-live');
  const toolbar = element('div', 'efficiency-toolbar');
  const legend = element('div', 'efficiency-legend');
  legend.append(element('span', 'efficiency-key efficiency-key--flow', 'Flow-Policy'),
    element('span', 'efficiency-key efficiency-key--ht', 'HT-Policy (ours)'));
  toolbar.append(legend);

  const rows = models.map(model => {
    const row = element('div', 'efficiency-row');
    row.setAttribute('role', 'img');
    // Keep accessible results stable while decorative counters animate.
    row.setAttribute('aria-label', `${model.name}: Flow-Policy ${number.format(model.flow)} milliseconds, `
      + `HT-Policy ${number.format(model.ht)} milliseconds; ${(model.flow / model.ht).toFixed(2)} times faster.`);
    const name = element('div', 'efficiency-model', model.name);
    const track = element('div', 'efficiency-track');
    const guides = element('div', 'efficiency-guides');
    for (const percentage of [0, 25, 50, 75, 100]) {
      const guide = element('i', 'efficiency-guide');
      guide.style.left = `${percentage}%`;
      guides.append(guide);
    }
    const latency = element('span', 'efficiency-latency efficiency-latency--ht');
    track.append(guides, element('span', 'efficiency-rail'), element('span', 'efficiency-trail'),
      element('span', 'efficiency-dot efficiency-dot--flow'),
      element('span', 'efficiency-dot efficiency-dot--ht'),
      element('span', 'efficiency-latency efficiency-latency--flow', `${number.format(model.flow)} ms`), latency);
    const speed = element('div', 'efficiency-speed');
    const value = element('span', 'efficiency-speed-value');
    const digits = element('span', 'efficiency-speed-digits');
    value.append(digits, element('span', 'efficiency-speed-unit', '×'));
    speed.append(value, element('span', 'efficiency-speed-label', 'faster'));
    for (const child of [name, track, speed]) child.setAttribute('aria-hidden', 'true');
    row.append(name, track, speed);
    chart.append(row);
    return { ...model, row, digits, latency };
  });

  const axis = element('div', 'efficiency-axis');
  const ticks = element('div', 'efficiency-ticks');
  ticks.setAttribute('aria-hidden', 'true');
  for (const percentage of [0, 25, 50, 75, 100]) {
    const tick = element('span', '', `${percentage}%`);
    tick.style.left = `${percentage}%`;
    ticks.append(tick);
  }
  axis.append(ticks, element('p', 'efficiency-axis-label', 'Whole-model latency (% of Flow-Policy) · lower is better'));
  chart.append(axis);

  let frame = 0;
  let played = false;
  let visibleRatio = 0;
  const duration = 2600;
  const stagger = 150;

  function render(progress, index) {
    const { row, flow, ht, digits, latency } = rows[index];
    const currentLatency = progress === 1 ? ht : flow + (ht - flow) * progress;
    row.style.setProperty('--latency-position', `${100 * currentLatency / flow}%`);
    latency.textContent = `${number.format(currentLatency)} ms`;
    digits.textContent = (flow / currentLatency).toFixed(2);
  }

  function finish() {
    cancelAnimationFrame(frame);
    rows.forEach((item, index) => {
      render(1, index);
      item.row.classList.remove('is-moving');
    });
    chart.dataset.state = 'complete';
  }

  function play() {
    cancelAnimationFrame(frame);
    if (motion.matches || document.hidden) {
      finish();
      return;
    }
    chart.dataset.state = 'playing';
    rows.forEach((item, index) => {
      render(0, index);
      item.row.classList.add('is-moving');
    });
    const start = performance.now();
    function animate(now) {
      let complete = true;
      rows.forEach((item, index) => {
        const t = Math.min(1, Math.max(0, (now - start - index * stagger) / duration));
        // Easing moves the dot; the counter is always the reciprocal latency ratio.
        render(1 - (1 - t) ** 3, index);
        item.row.classList.toggle('is-moving', t > 0 && t < 1);
        if (t < 1) complete = false;
      });
      if (complete) finish();
      else frame = requestAnimationFrame(animate);
    }
    frame = requestAnimationFrame(animate);
  }

  function reset() {
    cancelAnimationFrame(frame);
    rows.forEach((item, index) => {
      render(0, index);
      item.row.classList.remove('is-moving');
    });
    chart.dataset.state = 'ready';
  }

  function playOnEntry() {
    if (!played && visibleRatio >= 0.4 && !document.hidden && !motion.matches) {
      played = true;
      play();
    }
  }

  // Show real final values when JavaScript or animation is unavailable.
  finish();
  const canObserve = 'IntersectionObserver' in window;
  if (canObserve && !motion.matches) reset();
  figure.replaceChildren(chart);
  figure.closest('.efficiency-block').querySelector('.efficiency-heading').append(toolbar);
  motion.addEventListener('change', () => {
    if (motion.matches) finish();
    else if (!played && canObserve) {
      reset();
      playOnEntry();
    }
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && chart.dataset.state === 'playing') finish();
    else if (!document.hidden) playOnEntry();
  });

  if (canObserve) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        visibleRatio = entry.isIntersecting ? entry.intersectionRatio : 0;
        // Play once per page visit; returning to the chart keeps final values.
        playOnEntry();
      }
    }, { threshold: [0, 0.4] });
    observer.observe(chart);
  }
}

// A failed enhancement leaves the static, fully labeled figure in place.
enhanceEfficiency().catch(() => {});
