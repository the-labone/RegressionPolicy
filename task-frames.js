// Preview example episodes alongside the unchanged residual-scale figure.
// Progress matches the horizontal axis; the clips illustrate the tasks, not
// individual samples in the aggregate residual statistics.
(async function enhanceTaskFrames() {
  const host = document.querySelector('.scales-explorer');
  const image = host?.querySelector('[data-residual-plot="scales"]');
  const hint = host?.querySelector('.task-explorer-hint');
  if (!image || !hint) return;

  let overlay;
  let card;
  try {
    const [source, response] = await Promise.all([
      loadFigure(image), fetch('assets/task-frames/manifest.json'),
    ]);
    if (!response.ok) return;
    const manifest = await response.json();
    const taskOrder = ['sweep_into_pile', 'open_drawer', 'close_drawer'];
    const labels = ['Sweep into pile', 'Open drawer', 'Close drawer'];
    const shortLabels = ['Sweep', 'Open', 'Close'];
    const markers = ['×', '●', '▲'];
    const curves = [...source.querySelectorAll('path[stroke-width="1.8"]')];
    if (curves.length !== 3) return;
    const tasks = taskOrder.map((id, index) => {
      const task = manifest.tasks.find(item => item.id === id);
      if (!task) throw new Error('Missing task frames');
      // Read the original plotted vertices and their transform. Do not
      // extrapolate the shorter Open/Close curves beyond their final bin.
      const numbers = curves[index].getAttribute('d').match(/-?\d*\.?\d+/g).map(Number);
      const transform = curves[index].transform.baseVal.consolidate().matrix;
      const points = [];
      for (let i = 0; i < numbers.length; i += 2) {
        const point = new DOMPoint(numbers[i], numbers[i + 1]).matrixTransform(transform);
        points.push({ x: point.x, y: point.y });
      }
      if (points.length !== (index === 0 ? 10 : 9)) throw new Error('Task curve changed');
      const sprite = new Image();
      sprite.src = task.sprite;
      return { ...task, label: labels[index], points, sprite };
    });
    // Decode the small sprites once, so scrubbing never flashes a loading frame.
    await Promise.all(tasks.map(task => task.sprite.decode()));

    const axes = { left: 314.429688, right: 480.75, top: 61.031185, bottom: 168.671852 };
    overlay = svgElement('svg', {
      class: 'task-plot-overlay', viewBox: '0 0 504 216', role: 'group',
      'aria-label': 'Task progress markers. Use left and right arrows for progress, up and down for tasks.',
    });
    const highlight = svgElement('g', { class: 'task-plot-highlight', visibility: 'hidden', 'aria-hidden': 'true' });
    const guide = svgElement('line', {
      y1: axes.top, y2: axes.bottom, stroke: '#9b693d',
      'stroke-width': '.8', 'stroke-dasharray': '2.5 3', 'stroke-opacity': '.5',
    });
    const dot = svgElement('circle', {
      r: '5.2', fill: 'none', stroke: '#8c592d', 'stroke-width': '1.4',
    });
    highlight.append(guide, dot);
    overlay.append(highlight);
    host.append(overlay);

    card = document.createElement('div');
    card.id = 'task-frame-preview';
    card.className = 'task-frame-preview';
    card.hidden = true;
    card.setAttribute('role', 'region');
    card.setAttribute('aria-label', 'Example task episode');
    card.innerHTML = `
      <div class="task-preview-heading">
        <div><h4 class="task-preview-title"></h4><p>Bridge · Example episode</p></div>
        <button class="task-preview-close" type="button" aria-label="Close frame preview">×</button>
      </div>
      <div class="task-preview-frame" role="img"></div>
      <div class="task-preview-progress"><span>Episode progress</span><output>50%</output></div>
      <input class="task-preview-scrubber" type="range" min="0" max="100" step="5" value="50" aria-label="Episode progress">
      <div class="task-preview-tasks" role="group" aria-label="Choose a task"></div>`;
    document.body.append(card);
    const title = card.querySelector('.task-preview-title');
    const frame = card.querySelector('.task-preview-frame');
    const progressLabel = card.querySelector('output');
    const scrubber = card.querySelector('.task-preview-scrubber');
    const buttons = tasks.map((task, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('aria-label', task.label);
      button.setAttribute('aria-pressed', 'false');
      button.innerHTML = `<span aria-hidden="true">${markers[index]}</span> ${shortLabels[index]}`;
      card.querySelector('.task-preview-tasks').append(button);
      return button;
    });

    let activeTask = 0;
    let progress = 50;
    let pinned = false;
    let hideTimer;
    let positionFrame;
    let activeMarker;
    let restoringFocus = false;
    const markerButtons = [];
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

    function curvePoint(task, value) {
      // Only highlight actual plotted samples, including when using the slider.
      return task.points.find((point, index) => value === 5 + index * 10);
    }

    function positionCard() {
      if (card.hidden) return;
      const plot = overlay.getBoundingClientRect();
      const cardWidth = card.offsetWidth;
      const cardHeight = card.offsetHeight;
      const viewportWidth = document.documentElement.clientWidth;
      const viewportHeight = window.innerHeight;
      const inset = 12;
      const gap = 14;
      const plotLeft = plot.left + plot.width * axes.left / 504;
      const plotRight = plot.left + plot.width * axes.right / 504;
      const plotTop = plot.top + plot.height * axes.top / 216;
      const plotBottom = plot.top + plot.height * axes.bottom / 216;
      let x;
      let y;
      if (plotRight + gap + cardWidth <= viewportWidth - inset) {
        x = plotRight + gap;
        y = (plotTop + plotBottom - cardHeight) / 2;
        card.dataset.side = 'right';
      } else if (plotLeft - gap - cardWidth >= inset) {
        x = plotLeft - gap - cardWidth;
        y = (plotTop + plotBottom - cardHeight) / 2;
        card.dataset.side = 'left';
      } else {
        x = (viewportWidth - cardWidth) / 2;
        y = plotTop >= cardHeight + inset + gap ? plotTop - cardHeight - gap : plot.bottom + 24;
        card.dataset.side = 'below';
      }
      card.style.left = `${clamp(x, inset, viewportWidth - cardWidth - inset)}px`;
      card.style.top = `${clamp(y, inset, viewportHeight - cardHeight - inset)}px`;
    }

    function selectFrame(taskIndex, value) {
      activeTask = taskIndex;
      progress = clamp(Math.round(value / 5) * 5, 0, 100);
      const task = tasks[activeTask];
      const tile = task.frames[Math.round(progress / 100 * (task.frameCount - 1))];
      title.textContent = task.label;
      frame.style.backgroundImage = `url("${task.sprite.src}")`;
      frame.style.backgroundSize = `${task.columns * 100}% ${task.rows * 100}%`;
      frame.style.backgroundPosition = `${tile.column / (task.columns - 1) * 100}% ${tile.row / (task.rows - 1) * 100}%`;
      frame.setAttribute('aria-label', `${task.label}, example episode at ${progress}% progress`);
      frame.dataset.task = task.id;
      frame.dataset.frame = tile.index;
      progressLabel.textContent = `${progress}%`;
      scrubber.value = progress;
      scrubber.style.setProperty('--progress', `${progress}%`);
      scrubber.setAttribute('aria-valuetext', `${task.label}, ${progress}%`);
      buttons.forEach((button, index) => button.setAttribute('aria-pressed', String(index === activeTask)));
      markerButtons.forEach(marker => marker.element.setAttribute('aria-expanded',
        String(!card.hidden && marker.taskIndex === activeTask && marker.progress === progress)));
      const point = curvePoint(task, progress);
      highlight.setAttribute('visibility', point ? 'visible' : 'hidden');
      if (point) {
        guide.setAttribute('x1', point.x);
        guide.setAttribute('x2', point.x);
        dot.setAttribute('cx', point.x);
        dot.setAttribute('cy', point.y);
      }
    }

    function show(taskIndex = activeTask, value = progress) {
      clearTimeout(hideTimer);
      card.hidden = false;
      selectFrame(taskIndex, value);
      positionCard();
    }

    function hide(restoreFocus = false) {
      clearTimeout(hideTimer);
      pinned = false;
      card.hidden = true;
      highlight.setAttribute('visibility', 'hidden');
      markerButtons.forEach(marker => marker.element.setAttribute('aria-expanded', 'false'));
      if (restoreFocus && activeMarker) {
        restoringFocus = true;
        activeMarker.element.focus({ preventScroll: true });
        restoringFocus = false;
      }
    }

    function scheduleHide() {
      if (!pinned && !card.contains(document.activeElement) && !overlay.contains(document.activeElement)) {
        hideTimer = setTimeout(() => hide(), 240);
      }
    }

    function activateMarker(marker) {
      activeMarker = marker;
      markerButtons.forEach(item => item.element.setAttribute('tabindex', item === marker ? '0' : '-1'));
      show(marker.taskIndex, marker.progress);
    }

    function closestMarker(event) {
      const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(overlay.getScreenCTM().inverse());
      // Nearly overlapping markers must remain selectable regardless of SVG
      // stacking order. Hit regions are local to markers, never the whole plot.
      let nearest;
      let distance = 6;
      for (const marker of markerButtons) {
        const delta = Math.hypot(marker.point.x - point.x, marker.point.y - point.y);
        if (delta <= distance) { nearest = marker; distance = delta; }
      }
      return nearest;
    }

    tasks.forEach((task, taskIndex) => task.points.forEach((point, pointIndex) => {
      const value = 5 + pointIndex * 10;
      const element = svgElement('g', {
        class: 'task-point', transform: `translate(${point.x} ${point.y})`,
        role: 'button', tabindex: taskIndex === 0 && pointIndex === 0 ? '0' : '-1',
        'aria-label': `${task.label} at ${value}%. Preview frame`,
        'aria-controls': card.id, 'aria-expanded': 'false',
      });
      element.append(svgElement('circle', { r: '6', fill: 'transparent', class: 'task-point-hit' }));
      if (taskIndex === 0) {
        // A narrow background stroke separates the cross from the curve.
        element.append(svgElement('path', {
          d: 'M-3.2-3.2 3.2 3.2M-3.2 3.2 3.2-3.2', fill: 'none',
          stroke: '#fdfdfa', 'stroke-width': '3', class: 'task-point-symbol',
        }));
        element.append(svgElement('path', {
          d: 'M-3.2-3.2 3.2 3.2M-3.2 3.2 3.2-3.2', fill: 'none',
          stroke: '#a36a31', 'stroke-width': '1.7', class: 'task-point-symbol',
        }));
      } else {
        element.append(svgElement(taskIndex === 1 ? 'circle' : 'path', {
          ...(taskIndex === 1 ? { r: '3.2' } : { d: 'M0-3.5-3.4 3H3.4Z' }),
          fill: '#a36a31', stroke: '#fdfdfa', 'stroke-width': '.9', class: 'task-point-symbol',
        }));
      }
      const marker = { element, point, taskIndex, pointIndex, progress: value };
      markerButtons.push(marker);
      const hover = event => {
        if (event.pointerType !== 'touch') {
          const nearest = closestMarker(event);
          if (nearest) activateMarker(nearest);
        }
      };
      element.addEventListener('pointerenter', hover);
      element.addEventListener('pointermove', hover);
      element.addEventListener('pointerleave', scheduleHide);
      element.addEventListener('click', event => {
        const nearest = closestMarker(event);
        if (nearest) { pinned = true; activateMarker(nearest); }
      });
      element.addEventListener('focus', () => {
        if (!restoringFocus) activateMarker(marker);
      });
      element.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          pinned = true;
          activateMarker(marker);
          scrubber.focus({ preventScroll: true });
          return;
        }
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let nextTask = taskIndex;
        let nextPoint = pointIndex;
        if (event.key === 'ArrowLeft') nextPoint--;
        if (event.key === 'ArrowRight') nextPoint++;
        if (event.key === 'ArrowUp') nextTask--;
        if (event.key === 'ArrowDown') nextTask++;
        nextTask = clamp(nextTask, 0, tasks.length - 1);
        if (event.key === 'Home') nextPoint = 0;
        if (event.key === 'End') nextPoint = tasks[nextTask].points.length - 1;
        nextPoint = clamp(nextPoint, 0, tasks[nextTask].points.length - 1);
        markerButtons.find(item => item.taskIndex === nextTask && item.pointIndex === nextPoint)
          .element.focus({ preventScroll: true });
      });
      overlay.insertBefore(element, highlight);
    }));
    hint.hidden = false;
    overlay.addEventListener('focusout', event => {
      if (!overlay.contains(event.relatedTarget) && !card.contains(event.relatedTarget)) hide();
    });
    buttons.forEach((button, index) => button.addEventListener('click', () => {
      pinned = true;
      selectFrame(index, progress);
    }));
    scrubber.addEventListener('input', () => { pinned = true; selectFrame(activeTask, Number(scrubber.value)); });
    card.addEventListener('pointerenter', () => clearTimeout(hideTimer));
    card.addEventListener('pointerleave', scheduleHide);
    card.addEventListener('focusout', event => {
      if (!card.contains(event.relatedTarget) && !overlay.contains(event.relatedTarget)) hide();
    });
    card.querySelector('.task-preview-close').addEventListener('click', () => hide(true));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !card.hidden) hide(card.contains(document.activeElement));
    });
    document.addEventListener('pointerdown', event => {
      if (!card.hidden && !card.contains(event.target) && !host.contains(event.target)) hide();
    });
    function reposition() {
      cancelAnimationFrame(positionFrame);
      positionFrame = requestAnimationFrame(() => {
        const rect = host.getBoundingClientRect();
        if (rect.bottom < 0 || rect.top > window.innerHeight) hide();
        else positionCard();
      });
    }
    window.addEventListener('resize', reposition, { passive: true });
    window.addEventListener('scroll', reposition, { passive: true });
  } catch {
    // Keep the original linked static plot if preview assets are unavailable.
    overlay?.remove();
    card?.remove();
    hint.hidden = true;
  }
})();
