// Add an animated trend to the original correlation figure.
const residualMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const svgNamespace = 'http://www.w3.org/2000/svg';

function svgElement(tag, attributes) {
  const element = document.createElementNS(svgNamespace, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  return element;
}

function namespaceFigure(svg, prefix) {
  // The PDF-derived SVGs reuse glyph and clipping IDs. Keep their
  // references local when embedding the figures in the same document.
  const ids = new Map();
  for (const element of svg.querySelectorAll('[id]')) {
    const id = element.id;
    ids.set(id, `${prefix}-${id}`);
    element.id = ids.get(id);
  }
  for (const element of svg.querySelectorAll('*')) {
    for (const attribute of [...element.attributes]) {
      let value = attribute.value.replace(/url\(#([^)]+)\)/g,
        (match, id) => ids.has(id) ? `url(#${ids.get(id)})` : match);
      if (value.startsWith('#') && ids.has(value.slice(1))) value = `#${ids.get(value.slice(1))}`;
      if (value !== attribute.value) element.setAttributeNS(attribute.namespaceURI, attribute.name, value);
    }
  }
}

async function loadFigure(image) {
  const response = await fetch(image.currentSrc || image.src);
  if (!response.ok) throw new Error('Figure unavailable');
  const source = new DOMParser().parseFromString(await response.text(), 'image/svg+xml');
  if (source.querySelector('parsererror')) throw new Error('Invalid figure');
  const svg = document.importNode(source.documentElement, true);
  svg.setAttribute('class', 'analysis-plot');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', image.alt);
  svg.dataset.residualPlot = image.dataset.residualPlot;
  return svg;
}

function prepareCorrelationTrend(svg) {
  // The horizontal error bars locate the eight plotted means. Fit in SVG
  // coordinates; both axes are linear, so this preserves the regression.
  const errorBars = [...svg.querySelectorAll('path[fill="none"][stroke-width="1.4"]')];
  if (errorBars.length !== 8) throw new Error('Correlation points changed');
  const points = errorBars.map(path => path.getPointAtLength(path.getTotalLength() / 2)
    .matrixTransform(path.transform.baseVal.consolidate().matrix));
  const meanX = points.reduce((sum, point) => sum + point.x, 0) / points.length;
  const meanY = points.reduce((sum, point) => sum + point.y, 0) / points.length;
  const slope = points.reduce((sum, point) => sum + (point.x - meanX) * (point.y - meanY), 0)
    / points.reduce((sum, point) => sum + (point.x - meanX) ** 2, 0);
  const left = Math.min(...points.map(point => point.x));
  const right = Math.max(...points.map(point => point.x));
  const fittedY = x => meanY + slope * (x - meanX);
  const clip = svgElement('clipPath', {
    id: 'residual-correlation-trend-reveal', clipPathUnits: 'userSpaceOnUse',
  });
  const rect = svgElement('rect', { x: left - 3, y: 0, width: 0, height: svg.viewBox.baseVal.height });
  clip.append(rect);
  svg.querySelector('defs').append(clip);
  const group = svgElement('g', { 'clip-path': `url(#${clip.id})` });
  const line = svgElement('path', {
    d: `M ${left} ${fittedY(left)} L ${right} ${fittedY(right)}`,
    fill: 'none', stroke: '#2b679a', 'stroke-width': '2.8',
    'stroke-dasharray': '7 5', 'stroke-linecap': 'round', 'stroke-opacity': '0.8',
    'data-correlation-trend': 'true',
  });
  const title = svgElement('title', {});
  title.textContent = 'Linear fit across the eight training objectives';
  line.append(title);
  group.append(line);
  errorBars[0].before(group);
  svg.setAttribute('aria-label', `${svg.getAttribute('aria-label')} A dashed line shows a linear fit.`);
  return { clip, rect, group, width: right - left + 6 };
}

async function enhanceResidualFigures() {
  // Keep the empirical correlation figure beneath the scale story unchanged; animate only its trend.
  const correlationImage = document.querySelector('img[data-residual-plot="correlation"]');
  if (!correlationImage || residualMotion.matches || !('IntersectionObserver' in window)) return;
  let correlationSVG;

  try {
    correlationSVG = await loadFigure(correlationImage);
    if (residualMotion.matches) return;
    namespaceFigure(correlationSVG, 'residual-correlation');
    correlationImage.replaceWith(correlationSVG);
    const correlationTrend = prepareCorrelationTrend(correlationSVG);
    let correlationStarted = false;
    let correlationVisible = false;
    let correlationReady = false;
    let correlationFrame = 0;
    correlationSVG.dataset.state = 'waiting';

    function finishCorrelation() {
      cancelAnimationFrame(correlationFrame);
      correlationStarted = true;
      correlationTrend.group.removeAttribute('clip-path');
      correlationTrend.clip.remove();
      correlationSVG.dataset.state = 'complete';
    }

    function playCorrelationWhenReady() {
      if (correlationStarted || !correlationVisible || !correlationReady
          || document.hidden || residualMotion.matches) return;
      correlationStarted = true;
      correlationSVG.dataset.state = 'playing';
      const start = performance.now();
      function render(now) {
        const t = Math.max(0, Math.min(1, (now - start - 200) / 1400));
        const progress = t * t * (3 - 2 * t);
        correlationTrend.rect.setAttribute('width', correlationTrend.width * progress);
        if (t >= 1) finishCorrelation();
        else correlationFrame = requestAnimationFrame(render);
      }
      correlationFrame = requestAnimationFrame(render);
    }

    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        correlationVisible = entry.isIntersecting && entry.intersectionRatio >= 0.5;
      }
      if (correlationStarted && correlationSVG.dataset.state !== 'complete' && !correlationVisible) finishCorrelation();
      playCorrelationWhenReady();
    }, { threshold: [0, 0.5] });
    observer.observe(correlationSVG);

    // Start when the plot's center reaches 65% of the viewport height.
    // Keep this separate from visibility so leaving the trigger zone does
    // not cut an animation short. Pixel margins track height, not width.
    let startObserver;
    function observeStartPosition() {
      startObserver?.disconnect();
      if (correlationReady) return;
      startObserver = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting || entry.intersectionRatio < 0.5) continue;
          correlationReady = true;
          startObserver.unobserve(entry.target);
        }
        playCorrelationWhenReady();
      }, {
        rootMargin: `0px 0px -${Math.round(window.innerHeight * 0.35)}px 0px`,
        threshold: [0, 0.5],
      });
      startObserver.observe(correlationSVG);
    }
    observeStartPosition();
    window.addEventListener('resize', observeStartPosition, { passive: true });
    residualMotion.addEventListener('change', () => {
      if (residualMotion.matches) finishCorrelation();
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        if (correlationStarted) finishCorrelation();
      } else {
        playCorrelationWhenReady();
      }
    });
  } catch {
    // A loading or source-layout failure retains the complete static figure.
    if (correlationSVG?.isConnected) correlationSVG.replaceWith(correlationImage);
  }
}

enhanceResidualFigures();
