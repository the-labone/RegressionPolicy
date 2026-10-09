// One clock connects an example Bridge episode, measured task-average RMS,
// and an illustrative Gaussian scale mixture. No per-frame RMS is inferred.
(() => {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';
  const C = {
    ink: '#303633', muted: '#72766f', blue: '#2b679a', orange: '#b88c5e',
    green: '#479b82', rule: '#e4e7e4', paper: '#fdfdfa', tail: '#eee7db',
  };
  const MIXTURE_SLOWDOWN = 2.2;
  const MIXTURE_GROWTH_START = 68;
  const MIXTURE_GROWTH_FRAMES = 59;
  const MIXTURE_GROWTH_SPEED = 1.5;
  const MIXTURE_SAVED_FRAMES = MIXTURE_GROWTH_FRAMES * (1 - 1 / MIXTURE_GROWTH_SPEED);
  const CORRELATION_START = 10 + (6.2 - MIXTURE_SAVED_FRAMES / 30) * MIXTURE_SLOWDOWN;
  const TOTAL = CORRELATION_START + 6.2;
  const STEP_TIMES = [0, 10 + 24 / 30 * MIXTURE_SLOWDOWN, 10 + 68 / 30 * MIXTURE_SLOWDOWN, CORRELATION_START];
  // Keep the axis title below the tick labels in both full and compact plots.
  const PROGRESS_AXIS_FOOTER = 70;
  const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const fade = (t, start, length) => clamp((t - start) / length);
  const ease = t => 1 - (1 - clamp(t)) ** 3;
  const ramp = (t, start, length) => ease(fade(t, start, length));
  const number = x => Number(x.toFixed(3));
  const line = points => points.map(([x, y], i) => `${i ? 'L' : 'M'}${number(x)} ${number(y)}`).join(' ');
  const area = (zs, x, top, bottom) => `${line(zs.map(z => [x(z), top(z)]))} ${
    line([...zs].reverse().map(z => [x(z), bottom(z)])).replace(/^M/, 'L')} Z`;
  const normal = (z, sigma = 1) => Math.exp(-z * z / (2 * sigma * sigma)) / (sigma * Math.sqrt(2 * Math.PI));
  let instance = 0;

  function svg(tag, attributes = {}, text) {
    const node = document.createElementNS(NS, tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function plot(width, height, label) {
    const node = svg('svg', {
      width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': label,
      style: 'display:block;width:100%;height:auto;overflow:visible;font-family:inherit',
    });
    return node;
  }

  function textNode(x, y, text, options = {}) {
    return svg('text', { x, y, fill: C.muted, 'font-size': 19, ...options }, text);
  }

  function responsiveCorrelation(figure) {
    // Reflow the source figure's y-axis instead of stretching its glyphs.
    // The source plot spans y=100..400 in a 640×472 viewBox.
    const rules = [...figure.querySelectorAll(':scope > line')].map(node => ({ node, y: +node.getAttribute('y1') }));
    const labels = [...figure.querySelectorAll(':scope > text')].map(node => ({ node, y: +node.getAttribute('y') }));
    const objectives = [...figure.querySelectorAll('[data-objective]')].map(node => ({ node, y: +node.querySelector('circle').getAttribute('cy') }));
    const trend = figure.querySelector('[data-correlation-trend]');
    const endpoints = trend.getAttribute('d').match(/-?\d*\.?\d+/g).map(Number);
    const clip = figure.querySelector('[data-correlation-trend-clip]');
    const metadata = labels.find(label => label.y === 25);
    const metadataAscent = 25 - metadata.node.getBBox().y;
    const sourceGridTop = Math.min(...rules.map(rule => rule.y));
    return (geometry) => {
      const height = geometry?.height ?? 472;
      const bottom = height - 72;
      const gridFraction = (sourceGridTop - 100) / 300;
      const top = geometry ? (geometry.gridTop - gridFraction * bottom) / (1 - gridFraction) : 100;
      const y = value => top + (value - 100) / 300 * (bottom - top);
      figure.setAttribute('viewBox', `0 0 640 ${height}`);
      figure.setAttribute('height', height);
      clip.setAttribute('height', height);
      rules.forEach(rule => {
        rule.node.setAttribute('y1', y(rule.y));
        rule.node.setAttribute('y2', y(rule.y));
      });
      labels.forEach(label => {
        const next = label.y === 25 ? (geometry ? geometry.metadataTop + metadataAscent : 25)
          : label.y === 75 ? y(sourceGridTop) - (sourceGridTop - 75)
          : label.y >= 429 ? height - (472 - label.y)
          : y(label.y - 6) + 6;
        label.node.setAttribute('y', next);
      });
      objectives.forEach(point => point.node.setAttribute('transform', `translate(0 ${y(point.y) - point.y})`));
      trend.setAttribute('d', `M ${endpoints[0]} ${y(endpoints[1])} L ${endpoints[2]} ${y(endpoints[3])}`);
    };
  }

  async function init(root) {
    const video = root.querySelector('[data-scale-video]');
    const progressMount = root.querySelector('[data-scale-progress]');
    const mixtureMount = root.querySelector('[data-scale-mixture]');
    const actionsMount = root.querySelector('[data-scale-actions]');
    const stage = root.querySelector('[data-scale-stage]');
    const layout = root.querySelector('.scale-story-layout');
    const episode = root.querySelector('.scale-story-episode');
    const correlation = root.querySelector('[data-scale-correlation]');
    const correlationTitle = correlation?.querySelector('h3');
    const steps = [...root.querySelectorAll('[data-scale-step]')].map(node => ({
      node, button: node.querySelector('button'),
    }));
    if (!video || !progressMount || !mixtureMount || !actionsMount || !stage || !layout || !episode || !correlation) return;

    root.dataset.scaleState = 'loading';
    try {
      const response = await fetch('assets/data/residual-scale-story.json');
      if (!response.ok) throw new Error('Task data unavailable');
      const data = await response.json();
      const points = data.points;
      if (!Array.isArray(points) || points.length < 2 || !points.every((p, i) =>
        p.length === 2 && p.every(Number.isFinite) && (!i || p[0] > points[i - 1][0]))) {
        throw new Error('Invalid task curve');
      }
      const keyframes = data.timing.keyframes;
      const low = data.low;
      const high = data.high;
      const prefix = `residual-scale-story-${++instance}`;
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

      // The progress plot always uses the original vertices. The compact view
      // changes only screen coordinates, not data or the vertical axis range.
      const progressSVG = plot(640, 340,
        'Sweep into Pile: measured task-average residual RMS versus episode progress. The synchronized video is a separate example episode.');
      const defs = svg('defs');
      const clip = svg('clipPath', { id: `${prefix}-reveal` });
      const clipRect = svg('rect', { x: 58, y: 0, width: 0, height: 340 });
      clip.append(clipRect);
      defs.append(clip);
      progressSVG.append(defs);
      const grid = [0, .1, .2, .3, .4].map(value => {
        const rule = svg('line', { x1: 58, x2: 610, stroke: C.rule, 'stroke-width': 1 });
        const label = textNode(44, 0, value.toFixed(1), { 'text-anchor': 'end', 'font-size': 18 });
        progressSVG.append(rule, label);
        return { value, rule, label };
      });
      const xTicks = [0, 25, 50, 75, 100].map(value => {
        const label = textNode(58 + value / 100 * 552, 0, `${value}%`, {
          'text-anchor': 'middle', 'font-size': 18,
        });
        progressSVG.append(label);
        return label;
      });
      const axisLabel = textNode(334, 332, 'Episode progress', { 'text-anchor': 'middle', 'font-size': 19 });
      const baseCurve = svg('path', {
        fill: 'none', stroke: '#d9ddd7', 'stroke-width': 3.2, 'stroke-linejoin': 'round',
      });
      const revealedCurve = svg('path', {
        fill: 'none', stroke: C.orange, 'stroke-width': 3.2, 'stroke-linejoin': 'round',
        'clip-path': `url(#${prefix}-reveal)`,
      });
      progressSVG.append(baseCurve, revealedCurve);
      const dataDots = points.map(() => {
        const dot = svg('circle', { r: 4.1, fill: '#d9ddd7' });
        progressSVG.append(dot);
        return dot;
      });
      const cursor = svg('g', { 'aria-hidden': 'true' });
      const cursorLine = svg('line', { stroke: C.green, 'stroke-width': 1.5, 'stroke-dasharray': '4 5' });
      const cursorDot = svg('circle', { r: 6, fill: C.paper, stroke: C.green, 'stroke-width': 2.8 });
      const cursorPulse = svg('circle', { fill: 'none', stroke: C.green, 'stroke-width': 1.8 });
      const valueLabel = textNode(0, 0, '', { 'font-size': 20, 'font-weight': 600 });
      const progressLabel = textNode(0, 22, '', { 'font-size': 19, 'text-anchor': 'middle' });
      cursor.append(cursorLine, cursorPulse, cursorDot, valueLabel, progressLabel);
      progressSVG.append(cursor, axisLabel);
      progressMount.replaceChildren(progressSVG);

      // Candidate-action annotations are copied from the source illustration,
      // in the native 256×256 video coordinate system; they are not predictions.
      const actionSVG = plot(256, 256, 'Illustrative candidate actions, not tracked predictions');
      actionSVG.style.height = '100%';
      actionSVG.style.position = 'absolute';
      actionSVG.style.inset = '0';
      actionSVG.style.pointerEvents = 'none';
      const actionDefs = svg('defs');
      const actionMarker = svg('marker', {
        id: `${prefix}-action-arrow`, markerWidth: 5, markerHeight: 5, refX: 4, refY: 2.5, orient: 'auto',
      });
      const arrowHead = svg('path', { d: 'M0 0L4 2.5L0 5', fill: 'none', stroke: C.green, 'stroke-width': 1.3 });
      actionMarker.append(arrowHead);
      actionDefs.append(actionMarker);
      actionSVG.append(actionDefs);
      const actionLines = [0, 1, 2].map(() => {
        const group = svg('g');
        const backing = svg('line', { stroke: C.paper, 'stroke-width': 4.5, 'stroke-linecap': 'round' });
        const arrow = svg('line', {
          stroke: C.green, 'stroke-width': 1.8, 'stroke-linecap': 'round',
          'marker-end': `url(#${prefix}-action-arrow)`,
        });
        group.append(backing, arrow);
        actionSVG.append(group);
        return { group, backing, arrow };
      });
      const actionRing = svg('circle', { fill: 'none', stroke: C.paper, 'stroke-width': 1.7 });
      const actionOrigin = svg('circle', { r: 3, stroke: C.paper, 'stroke-width': 1 });
      const actionCaption = svg('g', { transform: 'translate(12 209)' });
      actionCaption.append(svg('rect', { width: 232, height: 34, rx: 3, fill: C.paper, 'fill-opacity': .96 }));
      const actionTitle = textNode(9, 14, '', { 'font-size': 10.5, 'font-weight': 600 });
      actionCaption.append(actionTitle, textNode(9, 26, 'Illustrated candidate actions', { 'font-size': 8.5 }));
      actionSVG.append(actionRing, actionOrigin, actionCaption);
      actionsMount.replaceChildren(actionSVG);

      // Equal weights and zero means: sum(w_i sigma_i²)=1. The Gaussian
      // reference has the same variance. This finite mixture is not power-law.
      const sigmas = [1, 2, 4].map(s => s / Math.sqrt(7));
      const components = sigmas.map(s => z => normal(z, s) / 3);
      const partial = (z, count) => components.slice(0, count).reduce((sum, fn) => sum + fn(z), 0);
      const density = z => partial(z, 3);
      const zs = Array.from({ length: 201 }, (_, i) => -5 + i / 20);
      const colors = [C.green, '#8ea7b8', C.orange];
      const charts = progressMount.parentElement;
      const connections = svg('svg', { class: 'scale-story-connectors', 'aria-hidden': 'true', opacity: 0 });
      const connectionDefs = svg('defs');
      connections.append(connectionDefs);
      const connectionMask = svg('mask', { id: `${prefix}-scale-link-mask`, maskUnits: 'userSpaceOnUse' });
      const maskBackground = svg('rect', { fill: 'white' });
      const textClearance = svg('g', { fill: 'black' });
      connectionMask.append(maskBackground, textClearance);
      connectionDefs.append(connectionMask);
      const scaleLinks = [C.green, C.orange].map((color, i) => {
        const marker = svg('marker', {
          id: `${prefix}-scale-link-${i}`, markerWidth: 7, markerHeight: 7,
          refX: 6, refY: 3.5, orient: 'auto', markerUnits: 'userSpaceOnUse',
        });
        marker.append(svg('path', { d: 'M1 1L6 3.5L1 6', fill: 'none', stroke: color,
          'stroke-width': 1.3, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
        connectionDefs.append(marker);
        const group = svg('g');
        const path = svg('path', { fill: 'none', stroke: color, 'stroke-width': 1.35,
          mask: `url(#${prefix}-scale-link-mask)`,
          'stroke-dasharray': '4 5', 'stroke-linecap': 'round', 'marker-end': `url(#${prefix}-scale-link-${i})` });
        const origin = svg('circle', { r: 3.7, fill: C.paper, stroke: color, 'stroke-width': 1.6 });
        group.append(path, origin);
        connections.append(group);
        return { group, path, origin };
      });
      charts.append(connections);
      const takeaway = document.createElement('p');
      takeaway.className = 'scale-story-takeaway';
      const emphasis = document.createElement('strong');
      emphasis.textContent = 'Heavy tails';
      const takeawayText = document.createElement('span');
      takeawayText.textContent = 'arise naturally in robot data';
      takeaway.append(emphasis, document.createTextNode(' '), takeawayText);
      layout.append(takeaway);
      let correlationTrend;
      let resizeCorrelation;
      try {
        const correlationImage = correlation.querySelector('img');
        const correlationSVG = await loadFigure(correlationImage);
        namespaceFigure(correlationSVG, `${prefix}-correlation`);
        correlationSVG.removeAttribute('data-residual-plot');
        correlationSVG.removeAttribute('aria-labelledby');
        correlationSVG.setAttribute('preserveAspectRatio', 'xMidYMin meet');
        correlationSVG.setAttribute('class', 'scale-story-correlation-plot');
        correlationImage.replaceWith(correlationSVG);
        resizeCorrelation = responsiveCorrelation(correlationSVG);
        const rect = correlationSVG.querySelector('[data-correlation-trend-clip]');
        if (rect) correlationTrend = { rect, width: Number(rect.dataset.fullWidth) };
      } catch {
        // The original image remains a usable fallback if enhancement fails.
      }
      root.dataset.scaleReady = '';
      let connectionTargets;
      let connectionGeometryDirty = true;

      function buildMixtureScene(narrow) {
        const width = narrow ? 600 : 900;
        const height = narrow ? 380 : 278;
        const left = narrow ? 18 : 81.5625;
        const right = narrow ? 358 : 555.8125;
        const bottom = narrow ? 192 : 208;
        const xl = z => left + (z + 5) * (narrow ? 22.2 : 30.2);
        const xr = z => right + (z + 5) * (narrow ? 22.4 : 30.2);
        const ym = value => bottom - value / .68 * (narrow ? 112 : 136);
        const yl = value => bottom - value / 1.1 * (narrow ? 106 : 130);
        connectionTargets = {
          width, narrow,
          low: [xl(-.25), yl(normal(-.25, sigmas[0]))],
          high: [xl(1.3), yl(normal(1.3, sigmas[2]))],
        };
        connectionGeometryDirty = true;
        const small = narrow ? 22 : 20;
        const mixtureSVG = plot(width, height,
          'Illustration: equally mixing zero-mean Gaussians with different scales gives a distribution with heavier tails than a Gaussian of the same variance. The right curve builds by adding each weighted component in place.');
        mixtureSVG.append(
          textNode(left, 28, narrow ? 'Different scales' : 'State-dependent scales', { 'font-size': 25, fill: C.ink }),
          textNode(right, 28, narrow ? 'Mixture' : 'Gaussian mixture', { 'font-size': 25, fill: C.ink }),
        );
        const leftLabels = svg('g');
        ['Narrow', 'Medium', 'Wide'].forEach((label, i) => {
          const group = svg('g');
          if (!narrow) group.append(
            svg('line', { x1: left + i * 116, x2: left + 22 + i * 116, y1: 57, y2: 57, stroke: colors[i], 'stroke-width': 3 }),
            textNode(left + 29 + i * 116, 63, label, { 'font-size': 18 }),
          );
          leftLabels.append(group);
        });
        mixtureSVG.append(leftLabels);
        [xl, xr].forEach(x => {
          mixtureSVG.append(svg('line', { x1: x(-5), x2: x(5), y1: bottom, y2: bottom, stroke: '#bdc3bc', 'stroke-width': 1 }));
          [-4, 0, 4].forEach(z => mixtureSVG.append(
            svg('line', { x1: x(z), x2: x(z), y1: bottom, y2: bottom + 5, stroke: '#bdc3bc', 'stroke-width': 1 }),
            textNode(x(z), bottom + 26, z === -4 ? '−4' : z, { 'font-size': small, 'text-anchor': 'middle' }),
          ));
        });
        const leftPaths = sigmas.map((sigma, i) => {
          const group = svg('g');
          group.append(
            svg('path', { d: area(zs, xl, z => yl(normal(z, sigma)), () => bottom), fill: colors[i], 'fill-opacity': .055 }),
            svg('path', { d: line(zs.map(z => [xl(z), yl(normal(z, sigma))])), fill: 'none', stroke: colors[i], 'stroke-width': 3.1, 'stroke-linecap': 'round' }),
          );
          mixtureSVG.append(group);
          return group;
        });
        const poolArrow = svg('g');
        poolArrow.append(svg('path', {
          d: narrow ? 'M260 141H337M329 134L337 141L329 148' : 'M411 153H528M520 146L528 153L520 160',
          fill: 'none', stroke: '#a4a89e', 'stroke-width': 1.8,
        }), textNode(narrow ? 299 : 469.5, narrow ? 116 : 128, 'Mix', { 'font-size': small, 'text-anchor': 'middle' }));
        mixtureSVG.append(poolArrow);
        const mixtureFill = svg('path', { fill: C.green, 'fill-opacity': .08 });
        const mixturePath = svg('path', { fill: 'none', stroke: C.green, 'stroke-width': 3.8, 'stroke-linejoin': 'round' });
        const gaussian = svg('path', {
          d: line(zs.map(z => [xr(z), ym(normal(z))])), fill: 'none', stroke: C.orange,
          'stroke-width': 2.8, 'stroke-dasharray': '7 6', 'stroke-linecap': 'round',
        });
        const tails = svg('g');
        [-1, 1].forEach(side => {
          const values = zs.filter(z => side < 0 ? z <= -2.8 : z >= 2.8);
          tails.append(svg('path', { d: area(values, xr, z => ym(density(z)), () => bottom), fill: C.orange, 'fill-opacity': .55 }));
        });
        mixtureSVG.append(mixtureFill, tails, gaussian, mixturePath);

        // Keep the magnified tail in clear space, outside the central peak.
        // Both panels use the exact densities; only the inset's vertical scale changes.
        const inset = svg('g');
        const zoomZ = Array.from({ length: 111 }, (_, i) => 2.8 + i / 50);
        const zoom = narrow ? { x: 405, y: 251, w: 170, h: 83 } : { x: 755.8125, y: 68, w: 102, h: 69 };
        const zx = z => zoom.x + (z - 2.8) / 2.2 * zoom.w;
        const zy = value => zoom.y + zoom.h - value / .019 * zoom.h;
        inset.append(
          textNode(zoom.x, zoom.y - 12, 'Tail (zoomed)', { 'font-size': narrow ? 22 : 18 }),
          svg('path', { d: area(zoomZ, zx, z => zy(density(z)), () => zoom.y + zoom.h), fill: C.green, 'fill-opacity': .07 }),
          svg('line', { x1: zoom.x, x2: zoom.x + zoom.w, y1: zoom.y + zoom.h, y2: zoom.y + zoom.h, stroke: '#c6c9c0', 'stroke-width': 1 }),
          svg('path', { d: line(zoomZ.map(z => [zx(z), zy(normal(z))])), fill: 'none', stroke: C.orange, 'stroke-width': 2.2, 'stroke-dasharray': '5 5' }),
          svg('path', { d: line(zoomZ.map(z => [zx(z), zy(density(z))])), fill: 'none', stroke: C.green, 'stroke-width': 2.8 }),
          svg('path', { d: narrow ? `M575 241L${xr(3.5)} ${ym(density(3.5)) + 5}` : `M820 145L${xr(3.5)} ${ym(density(3.5)) - 5}`,
            fill: 'none', stroke: '#b7beb2', 'stroke-width': 1, 'stroke-dasharray': '3 4' }),
        );
        mixtureSVG.append(inset);
        mixtureSVG.append(textNode(left, narrow ? 268 : 264, 'Illustration · equal weights', { 'font-size': small }));
        if (narrow) mixtureSVG.append(textNode(left, 298, 'Same mean', { 'font-size': small }));
        const legend = svg('g');
        const legendY = narrow ? 362 : 258;
        legend.append(
          svg('line', { x1: narrow ? 18 : right, x2: narrow ? 45 : right + 26, y1: legendY, y2: legendY, stroke: C.green, 'stroke-width': 3.4 }),
          textNode(narrow ? 56 : right + 36, legendY + 6, 'Mixture', { 'font-size': small, fill: C.ink }),
          svg('line', { x1: narrow ? 164 : right + 104, x2: narrow ? 195 : right + 128, y1: legendY, y2: legendY, stroke: C.orange, 'stroke-width': 2.6, 'stroke-dasharray': '5 5' }),
          textNode(narrow ? 208 : right + 137, legendY + 6, 'Gaussian · same variance', { 'font-size': narrow ? 22 : 17 }),
        );
        mixtureSVG.append(legend);
        mixtureMount.replaceChildren(mixtureSVG);
        return f => {
          const smooth = (start, duration) => {
            const p = fade(f, start, duration);
            return p * p * (3 - 2 * p);
          };
          leftPaths.forEach((node, i) => {
            node.setAttribute('opacity', smooth(24 + i * 12, 18));
            leftLabels.children[i].setAttribute('opacity', smooth(24 + i * 12, 18));
          });
          poolArrow.setAttribute('opacity', smooth(59, 18));
          const amounts = components.map((_, i) => smooth(68 + i * 17, 25));
          const currentDensity = z => components.reduce((sum, fn, i) => sum + fn(z) * amounts[i], 0);
          mixturePath.setAttribute('d', line(zs.map(z => [xr(z), ym(currentDensity(z))])));
          mixtureFill.setAttribute('d', area(zs, xr, z => ym(currentDensity(z)), () => bottom));
          mixturePath.setAttribute('opacity', smooth(68, 12));
          const comparison = smooth(126, 18);
          gaussian.setAttribute('opacity', comparison);
          legend.setAttribute('opacity', comparison);
          tails.setAttribute('opacity', smooth(143, 19));
          inset.setAttribute('opacity', smooth(143, 19));
        };
      }
      function needsCompactMixture() {
        const mobile = window.matchMedia('(max-width: 760px)').matches;
        const columnGap = parseFloat(getComputedStyle(root).getPropertyValue('--story-column-gap'));
        const finalWidth = mobile ? charts.offsetWidth : (layout.clientWidth - columnGap) / 2;
        // Choose one artwork layout for the whole sequence, including the
        // smaller panel after the correlation figure moves alongside it.
        return Math.min(progressMount.offsetWidth, finalWidth) < 440;
      }
      let narrowLayout = progressMount.offsetWidth < 400;
      let compactMixture = needsCompactMixture();
      // Compact artwork has larger SVG labels, so it needs a little more room.
      const progressHeight = bottom => bottom + PROGRESS_AXIS_FOOTER + (compactMixture ? 10 : 0);
      let drawMixture = buildMixtureScene(compactMixture);
      let initialBottom = narrowLayout ? 270 : video.offsetHeight /
        Math.max(1, progressMount.offsetWidth) * 640;
      let mixtureFullHeight = 0;
      let reservedChartHeight = -1;
      let stageGeometry = { x: 0, y: 0, scale: 1, mobile: false };

      function reserveChartHeight() {
        const width = progressMount.offsetWidth;
        const headerHeight = progressMount.offsetTop;
        // The hidden mixture still contributes its margin during the first phase.
        const initialHeight = progressHeight(initialBottom) * width / 640 + 12;
        mixtureFullHeight = (compactMixture ? 380 / 600 : 278 / 900) * width;
        const finalHeight = progressHeight(145) * width / 640 + 12 + mixtureFullHeight;
        // Desktop phases share one footprint. The stacked mobile layout
        // follows the visible plots instead of reserving space for hidden ones.
        const mobile = window.matchMedia('(max-width: 760px)').matches;
        const nextHeight = mobile ? 0 : Math.ceil(headerHeight + Math.max(initialHeight, finalHeight));
        if (nextHeight !== reservedChartHeight) {
          reservedChartHeight = nextHeight;
          charts.style.setProperty('--scale-chart-height', `${nextHeight}px`);
        }
      }

      function measureStage() {
        const mobile = window.matchMedia('(max-width: 760px)').matches;
        // Measure untransformed content. Both final panels share a headline
        // baseline and the same body height on desktop.
        const columnGap = parseFloat(getComputedStyle(root).getPropertyValue('--story-column-gap'));
        const headlineTop = parseFloat(getComputedStyle(root).getPropertyValue('--story-headline-top'));
        const bodyTop = 60;
        const width = mobile ? charts.offsetWidth : (layout.clientWidth - columnGap) / 2;
        const scale = width / charts.offsetWidth;
        const x = mobile ? (layout.clientWidth - width) / 2 : 0;
        const bodyHeight = (progressMount.offsetTop + progressHeight(145) * charts.offsetWidth / 640 + 12 + mixtureFullHeight) * scale;
        if (resizeCorrelation) {
          // Match visible content: the metadata line, first gridline, and
          // bottom label. Equal outer boxes alone leave the SVG too short.
          const heading = charts.querySelector('.scale-story-chart-heading');
          const headingText = document.createRange();
          headingText.selectNode(heading.firstChild);
          const chartBounds = charts.getBoundingClientRect();
          const currentScale = chartBounds.width / charts.offsetWidth;
          const metadataTop = (headingText.getBoundingClientRect().top - chartBounds.top) / currentScale;
          resizeCorrelation(mobile ? null : {
            height: bodyHeight * 640 / width,
            gridTop: progressMount.offsetTop * 640 / charts.offsetWidth + 41,
            metadataTop: metadataTop * 640 / charts.offsetWidth,
          });
        }
        // A small optical offset balances the dense scatterplot against the
        // two lighter plots on the left; keep the headline baseline fixed.
        const evidenceOffset = mobile ? 0 : 6;
        const evidenceTop = mobile ? bodyTop + bodyHeight + 76 : bodyTop + evidenceOffset;
        layout.style.setProperty('--story-evidence-width', `${width}px`);
        layout.style.setProperty('--story-headline-size', `${Math.min(22, width * .053)}px`);
        layout.style.setProperty('--story-evidence-top', `${evidenceTop}px`);
        layout.style.setProperty('--story-evidence-heading-offset', `${headlineTop - bodyTop - evidenceOffset}px`);
        layout.style.setProperty('--story-evidence-right', `${mobile ? x : 0}px`);
        layout.style.setProperty('--story-evidence-height', `${mobile ? width * 472 / 640 : bodyHeight}px`);
        stageGeometry = {
          x: x - charts.offsetLeft, y: bodyTop - charts.offsetTop, scale, mobile,
          headlineX: x, headlineWidth: width,
        };
        const firstHeight = Math.max(episode.offsetTop + episode.offsetHeight, charts.offsetTop + charts.offsetHeight);
        const lastHeight = evidenceTop + (mobile ? width * 472 / 640 : bodyHeight);
        stageGeometry.height = lastHeight;
        layout.style.minHeight = mobile ? '0px' : `${Math.ceil(Math.max(firstHeight, lastHeight))}px`;
        if (!mobile) layout.style.height = '';
      }
      reserveChartHeight();
      measureStage();

      let elapsed = 0;
      let started = false;
      let desiredRunning = false;
      let completed = false;
      let manualMotion = false;
      let visible = true;
      let frameId = 0;
      let previousTime;
      let lastStage = '';
      let desiredVideoTime = 0;
      let lastVideoFrame = -1;
      let videoFailed = false;
      let videoReady = video.readyState >= 2;
      let drawnMixtureTime = -1;
      let shownStep = -1;

      video.muted = true;
      video.playsInline = true;
      video.pause();
      video.preload = 'auto';

      function progressAt(t) {
        if (t <= keyframes[0].time) return keyframes[0].progress;
        for (let i = 1; i < keyframes.length; i++) {
          const left = keyframes[i - 1];
          const right = keyframes[i];
          if (t <= right.time) return lerp(left.progress, right.progress, (t - left.time) / (right.time - left.time));
        }
        return keyframes.at(-1).progress;
      }

      function curveAt(p) {
        if (p < points[0][0] || p > points.at(-1)[0]) return null;
        for (let i = 1; i < points.length; i++) {
          if (p <= points[i][0]) return lerp(points[i - 1][1], points[i][1],
            (p - points[i - 1][0]) / (points[i][0] - points[i - 1][0]));
        }
        return null;
      }

      function seekVideo() {
        if (videoFailed || video.readyState < 1 || video.seeking) return;
        const target = Math.min(desiredVideoTime, Math.max(0, video.duration - .001));
        if (Number.isFinite(target) && Math.abs(video.currentTime - target) > .025) video.currentTime = target;
      }

      function setStage(text) {
        if (text !== lastStage) { stage.textContent = text; lastStage = text; }
      }

      function renderMixture(t) {
        // Accelerate only the curve's growth window, then resume the original pace.
        // Later cues follow immediately rather than waiting out the saved time.
        const baseFrame = t / MIXTURE_SLOWDOWN * 30;
        const growthElapsed = clamp(baseFrame - MIXTURE_GROWTH_START, 0, MIXTURE_GROWTH_FRAMES / MIXTURE_GROWTH_SPEED);
        const f = baseFrame + growthElapsed * (MIXTURE_GROWTH_SPEED - 1);
        const sceneTime = f / 30;
        const alpha = ramp(f, 19, 14);
        const compact = ramp(t, 0, .8);
        mixtureMount.style.opacity = String(alpha);
        mixtureMount.style.maxHeight = `${compact * mixtureFullHeight}px`;
        mixtureMount.style.transform = `translateY(${(1 - alpha) * 10}px)`;
        mixtureMount.setAttribute('aria-hidden', alpha === 0 ? 'true' : 'false');
        const takeawayAlpha = ramp(sceneTime, 5.5, .45);
        takeaway.style.opacity = String(takeawayAlpha);
        takeaway.setAttribute('aria-hidden', takeawayAlpha === 0 ? 'true' : 'false');
        // Connect the measured low/high scales to illustrative narrow/wide
        // components only after the progress plot has finished compacting.
        const linksVisible = sceneTime > 1.35;
        connections.setAttribute('opacity', linksVisible ? 1 : 0);
        if (!linksVisible) connectionGeometryDirty = true;
        if (linksVisible && connectionGeometryDirty) {
          const bounds = charts.getBoundingClientRect();
          const w = charts.offsetWidth;
          const displayScale = bounds.width / w;
          const pScale = w / 640;
          const mScale = w / connectionTargets.width;
          const progressY = progressMount.offsetTop;
          const mixtureY = mixtureMount.offsetTop;
          connections.setAttribute('viewBox', `0 0 ${w} ${charts.offsetHeight}`);
          maskBackground.setAttribute('width', w);
          maskBackground.setAttribute('height', charts.offsetHeight);
          // Keep straight connectors clear of the chart labels they pass behind.
          textClearance.replaceChildren(...[...charts.querySelectorAll('.scale-story-progress text, .scale-story-mixture text')].map(node => {
            const box = node.getBoundingClientRect();
            return svg('rect', { x: (box.left - bounds.left) / displayScale - 3, y: (box.top - bounds.top) / displayScale - 2,
              width: box.width / displayScale + 6, height: box.height / displayScale + 4, rx: 2 });
          }));
          const sources = [points[0], points.at(-1)].map(([p, rms]) => [
            (58 + p / 100 * 552) * pScale,
            progressY + (145 - rms / .4 * 104) * pScale,
          ]);
          const targets = [connectionTargets.low, connectionTargets.high].map(([x, y]) => [
            x * mScale, mixtureY + y * mScale,
          ]);
          scaleLinks.forEach(({ path, origin }, i) => {
            const [sx, sy] = sources[i];
            const [tx, ty] = targets[i];
            const length = Math.hypot(tx - sx, ty - sy);
            const dx = (tx - sx) / length;
            const dy = (ty - sy) / length;
            path.setAttribute('d', `M${sx + dx * 5} ${sy + dy * 5} L${tx - dx * 5} ${ty - dy * 5}`);
            origin.setAttribute('cx', sources[i][0]);
            origin.setAttribute('cy', sources[i][1]);
          });
          connectionGeometryDirty = false;
        }
        scaleLinks.forEach(({ group }, i) => group.setAttribute('opacity', .72 * ramp(sceneTime, i ? 2.1 : 1.4, .45)));
        if (t === drawnMixtureTime) return;
        drawnMixtureTime = t;
        drawMixture(f);
      }

      function renderCorrelation(t) {
        const time = t - CORRELATION_START;
        const move = ramp(time, .3, 1.4);
        const episodeAlpha = 1 - ramp(time, 0, .55);
        episode.style.opacity = String(episodeAlpha);
        episode.style.transform = `translateY(${(1 - episodeAlpha) * -10}px)`;
        episode.inert = episodeAlpha === 0;
        episode.setAttribute('aria-hidden', String(episodeAlpha === 0));
        charts.style.transform = `translate(${stageGeometry.x * move}px, ${stageGeometry.y * move}px) scale(${lerp(1, stageGeometry.scale, move)})`;
        // Interpolate a text anchor, not text-align: changing alignment near
        // the end of the move used to snap the title sideways by half its gap.
        const headlineStart = charts.offsetLeft + charts.offsetWidth;
        const headlineEnd = stageGeometry.headlineX + stageGeometry.headlineWidth / 2;
        takeaway.style.left = `${lerp(headlineStart, headlineEnd, move)}px`;
        takeaway.style.transform = `translateX(${lerp(-100, -50, move)}%)`;
        takeaway.style.fontSize = `${lerp(window.innerWidth <= 1100 ? Math.min(22, window.innerWidth * .048) : 22, Math.min(22, stageGeometry.headlineWidth * .053), move)}px`;
        const alpha = ramp(time, 1.45, .75);
        correlation.style.opacity = String(alpha);
        correlation.style.visibility = alpha > 0 ? 'visible' : 'hidden';
        correlation.style.transform = `translate(${stageGeometry.mobile ? 0 : (1 - alpha) * 18}px, ${stageGeometry.mobile ? (1 - alpha) * 12 : 0}px)`;
        correlation.inert = alpha === 0;
        correlation.setAttribute('aria-hidden', String(alpha === 0));
        const titleAlpha = ramp(time, 3.8, .75);
        correlationTitle.style.opacity = String(titleAlpha);
        correlationTitle.style.transform = `translateY(${(1 - titleAlpha) * 5}px)`;
        if (correlationTrend) correlationTrend.rect.setAttribute('width', correlationTrend.width * ramp(time, 2.2, 1.8));
      }

      function render(t) {
        const stepIndex = STEP_TIMES.reduce((active, time, i) => t >= time ? i : active, 0);
        if (shownStep !== stepIndex) {
          shownStep = stepIndex;
          root.dataset.scaleCurrentStep = String(stepIndex + 1);
          steps.forEach(({ node, button }, i) => {
            node.dataset.stepState = i > stepIndex ? 'upcoming' : i === stepIndex ? 'active' : 'complete';
            button.setAttribute('aria-current', i === stepIndex ? 'step' : 'false');
          });
        }
        const p = progressAt(t);
        const compact = ramp(t, 10, .8);
        const isLow = t >= .8 && t < 2.6;
        const isHigh = t >= 7.6 && t < 9.4;
        const holding = isLow || isHigh;
        const holdTime = t - (isHigh ? 7.6 : .8);
        const color = isHigh ? C.orange : C.green;
        const pulse = .35 + .65 * Math.sin(holdTime * Math.PI / .8) ** 2;
        const height = lerp(progressHeight(initialBottom), progressHeight(145), compact);
        const bottom = lerp(initialBottom, 145, compact);
        const span = lerp(narrowLayout ? 228 : initialBottom - 12, 104, compact);
        const x = value => 58 + value / 100 * 552;
        const y = value => bottom - value / .4 * span;
        root.dataset.scalePhase = t >= CORRELATION_START ? 'correlation' : t < 10 ? 'task' : 'mixture';
        root.dataset.scaleTime = t.toFixed(3);
        root.dataset.scaleProgressValue = p.toFixed(3);
        root.style.setProperty('--scale-compact', compact);
        progressSVG.setAttribute('viewBox', `0 0 640 ${height}`);
        progressSVG.setAttribute('height', height);
        grid.forEach(({ value, rule, label }) => {
          rule.setAttribute('y1', y(value)); rule.setAttribute('y2', y(value));
          label.setAttribute('y', y(value) + 6);
          label.setAttribute('font-size', compactMixture ? 24 : 18);
        });
        xTicks.forEach(label => {
          label.setAttribute('y', bottom + 25);
          label.setAttribute('font-size', compactMixture ? 24 : 18);
        });
        axisLabel.setAttribute('y', height - 8);
        axisLabel.setAttribute('font-size', compactMixture ? 24 : 19);
        valueLabel.setAttribute('font-size', compactMixture ? 25 : 20);
        progressLabel.setAttribute('font-size', compactMixture ? 24 : 19);
        const curve = line(points.map(([px, py]) => [x(px), y(py)]));
        baseCurve.setAttribute('d', curve);
        revealedCurve.setAttribute('d', curve);
        clipRect.setAttribute('width', Math.max(0, x(p) - 58));
        dataDots.forEach((node, i) => {
          node.setAttribute('cx', x(points[i][0])); node.setAttribute('cy', y(points[i][1]));
          node.setAttribute('fill', points[i][0] <= p ? C.orange : '#d9ddd7');
        });
        cursor.setAttribute('opacity', 1 - compact);
        cursorLine.setAttribute('x1', x(p)); cursorLine.setAttribute('x2', x(p));
        cursorLine.setAttribute('y1', 30); cursorLine.setAttribute('y2', bottom);
        cursorLine.setAttribute('stroke', color);
        cursorLine.setAttribute('opacity', .55);
        const value = curveAt(p);
        cursorDot.setAttribute('visibility', value === null ? 'hidden' : 'visible');
        if (value !== null) {
          cursorDot.setAttribute('cx', x(p)); cursorDot.setAttribute('cy', y(value)); cursorDot.setAttribute('stroke', color);
          cursorPulse.setAttribute('cx', x(p)); cursorPulse.setAttribute('cy', y(value));
          cursorPulse.setAttribute('r', 10 + pulse * 7); cursorPulse.setAttribute('stroke', color);
          valueLabel.setAttribute('x', x(p) + (isHigh ? -19 : 19));
          valueLabel.setAttribute('y', y(value) + (isHigh ? -23 : 33));
          valueLabel.setAttribute('text-anchor', isHigh ? 'end' : 'start');
          valueLabel.setAttribute('fill', color);
          valueLabel.textContent = `${isHigh ? 'High' : 'Low'} scale · ${value.toFixed(3)}`;
        }
        cursorPulse.setAttribute('opacity', holding ? pulse * fade(holdTime, 0, .15) : 0);
        valueLabel.setAttribute('opacity', holding ? fade(holdTime, 0, .2) : 0);
        progressLabel.setAttribute('x', x(p)); progressLabel.setAttribute('fill', color);
        progressLabel.textContent = `${Math.round(p)}%`;
        progressLabel.setAttribute('opacity', holding ? 1 : 0);

        actionSVG.style.opacity = holding ? String(fade(holdTime, 0, .23)) : '0';
        actionSVG.setAttribute('aria-hidden', holding ? 'false' : 'true');
        if (holding) {
          const action = data.illustration[isHigh ? 'high' : 'low'];
          arrowHead.setAttribute('stroke', color);
          actionLines.forEach(({ group, backing, arrow }, i) => {
            const amount = fade(holdTime, (4 + i * 3) / 30, 13 / 30);
            group.setAttribute('opacity', amount);
            [backing, arrow].forEach(node => {
              node.setAttribute('x1', action.origin[0]); node.setAttribute('y1', action.origin[1]);
              node.setAttribute('x2', lerp(action.origin[0], action.ends[i][0], amount));
              node.setAttribute('y2', lerp(action.origin[1], action.ends[i][1], amount));
            });
            arrow.setAttribute('stroke', color);
          });
          [actionRing, actionOrigin].forEach(node => {
            node.setAttribute('cx', action.origin[0]); node.setAttribute('cy', action.origin[1]);
          });
          actionRing.setAttribute('r', 5 + pulse * 3); actionRing.setAttribute('opacity', pulse);
          actionOrigin.setAttribute('fill', color);
          actionTitle.textContent = action.label;
          actionTitle.setAttribute('fill', color);
        }
        setStage(t >= 10 ? 'Different states · different residual scales' : isLow ? 'Align with the tool' :
          isHigh ? 'Adjust the sweep' : p < 20 ? 'Align and grasp' : p < 90 ? 'Sweep and reposition' : 'Finish the sweep');
        const nativeFrame = Math.round(p / 100 * (data.video.frameCount - 1));
        if (nativeFrame !== lastVideoFrame) {
          lastVideoFrame = nativeFrame;
          desiredVideoTime = nativeFrame / data.video.nativeFps;
          seekVideo();
        }
        renderCorrelation(t);
        renderMixture(Math.max(0, t - 10));
        if (stageGeometry.mobile) {
          const firstHeight = Math.max(episode.offsetTop + episode.offsetHeight, charts.offsetTop + charts.offsetHeight);
          // Resize with the stage-four move, making room before the scatterplot
          // fades in without leaving its empty slot beneath stages one to three.
          const move = ramp(t - CORRELATION_START, .3, 1.4);
          layout.style.height = `${Math.ceil(lerp(firstHeight, stageGeometry.height, move))}px`;
        }
      }

      // Initial decoding gates startup, but a native-frame seek may transiently
      // lower readyState. It must not repeatedly stop/restart the story clock.
      function playable() { return videoReady && !videoFailed; }
      function canRun() { return desiredRunning && visible && !document.hidden && playable(); }

      function updateControl() {
        const playingIntent = desiredRunning && !completed && !videoFailed;
        const actuallyRunning = playingIntent && canRun();
        root.dataset.scaleState = completed ? 'complete' : actuallyRunning ? 'playing' : started ? 'paused' : 'ready';
        root.dataset.scaleSuspended = String(playingIntent && !actuallyRunning);
      }

      function tick(now) {
        frameId = 0;
        if (!canRun()) { previousTime = undefined; updateControl(); return; }
        if (previousTime !== undefined) elapsed = Math.min(TOTAL, elapsed + Math.min((now - previousTime) / 1000, .1));
        previousTime = now;
        render(elapsed);
        if (elapsed >= TOTAL) {
          desiredRunning = false; completed = true; previousTime = undefined;
          updateControl();
        } else frameId = requestAnimationFrame(tick);
      }

      function syncClock() {
        if (!canRun()) {
          cancelAnimationFrame(frameId); frameId = 0; previousTime = undefined;
        } else if (!frameId) {
          previousTime = undefined;
          frameId = requestAnimationFrame(tick);
        }
        updateControl();
      }

      function start(manual = false) {
        if (completed) {
          elapsed = 0; completed = false; lastVideoFrame = -1; drawnMixtureTime = -1;
          render(0);
        }
        started = true;
        manualMotion ||= manual;
        desiredRunning = true;
        syncClock();
      }

      function seekStep(index) {
        if (videoFailed) return;
        cancelAnimationFrame(frameId); frameId = 0; previousTime = undefined;
        elapsed = STEP_TIMES[index];
        started = true; completed = false; manualMotion = true; desiredRunning = true;
        lastVideoFrame = -1; drawnMixtureTime = -1; connectionGeometryDirty = true;
        render(elapsed);
        syncClock();
        const target = index === 0 ? video : index === 3 ? correlation : charts;
        const bounds = target.getBoundingClientRect();
        if (bounds.top < 0 || bounds.bottom > window.innerHeight) {
          target.scrollIntoView({ block: 'center', behavior: reduced.matches ? 'auto' : 'smooth' });
        }
      }

      function viewportChanged() {
        const bounds = root.getBoundingClientRect();
        visible = bounds.bottom > 0 && bounds.top < window.innerHeight && bounds.right > 0 && bounds.left < window.innerWidth;
        const videoBounds = video.getBoundingClientRect();
        const center = videoBounds.top + videoBounds.height / 2;
        if (!started && !completed && visible && !reduced.matches && center <= window.innerHeight * .65 && videoBounds.bottom > 0) start();
        else syncClock();
      }

      steps.forEach(({ button }, index) => {
        button.disabled = false;
        button.title = `Jump to step ${index + 1}`;
        button.addEventListener('click', () => seekStep(index));
      });
      video.addEventListener('seeked', seekVideo);
      video.addEventListener('loadedmetadata', seekVideo);
      video.addEventListener('loadeddata', () => { videoReady = true; seekVideo(); viewportChanged(); });
      video.addEventListener('canplay', () => { videoReady = true; syncClock(); });
      video.addEventListener('error', () => {
        videoFailed = true; desiredRunning = false; completed = true; elapsed = TOTAL;
        render(TOTAL); syncClock();
        steps.forEach(({ button }) => { button.disabled = true; });
      });
      document.addEventListener('visibilitychange', syncClock);
      window.addEventListener('scroll', viewportChanged, { passive: true });
      window.addEventListener('resize', viewportChanged, { passive: true });
      if ('ResizeObserver' in window) {
        const resizeObserver = new ResizeObserver(() => {
        const next = progressMount.offsetWidth < 400;
        const nextBottom = next ? 270 : video.offsetHeight /
          Math.max(1, progressMount.offsetWidth) * 640;
        let redraw = next !== narrowLayout || Math.abs(nextBottom - initialBottom) > .05;
        connectionGeometryDirty = true;
        initialBottom = nextBottom;
        narrowLayout = next;
        const nextCompactMixture = needsCompactMixture();
        if (nextCompactMixture !== compactMixture) {
          compactMixture = nextCompactMixture;
          drawMixture = buildMixtureScene(compactMixture);
          drawnMixtureTime = -1;
          redraw = true;
        }
        reserveChartHeight();
        measureStage();
        if (redraw || elapsed >= 10 || stageGeometry.mobile) render(elapsed);
        });
        resizeObserver.observe(progressMount);
        resizeObserver.observe(video);
      }
      if ('IntersectionObserver' in window) new IntersectionObserver(viewportChanged, { threshold: [0, .1, .5] }).observe(root);
      reduced.addEventListener('change', () => {
        if (reduced.matches && !manualMotion) {
          desiredRunning = false; completed = true; elapsed = TOTAL; render(TOTAL); syncClock();
        }
      });

      if (reduced.matches) { elapsed = TOTAL; completed = true; render(TOTAL); }
      else render(0);
      if (video.readyState < 1) video.load();
      viewportChanged();
    } catch {
      root.dataset.scaleState = 'unavailable';
      delete root.dataset.scaleReady;
      layout.style.minHeight = '';
      layout.style.height = '';
      root.querySelector('.scale-story-charts').style.transform = '';
      [episode, correlation].forEach(node => {
        node.style.opacity = ''; node.style.transform = ''; node.style.visibility = '';
        node.inert = false; node.removeAttribute('aria-hidden');
      });
      const strayTakeaway = layout.querySelector('.scale-story-takeaway');
      if (strayTakeaway) strayTakeaway.remove();
      correlationTitle.style.opacity = '';
      correlationTitle.style.transform = '';
      steps.forEach(({ button }) => { button.disabled = true; });
      // The HTML's video poster and explanatory text remain available.
    }
  }

  document.querySelectorAll('[data-scale-story]').forEach(init);
})();
