(() => {
  const TAU = Math.PI * 2;
  const AXIS_ANGLE = Math.atan(0.5);
  const state = {
    stage: 'brief',
    order: null,
    sourceDataUrl: null,
    sourceName: '',
    sourceImage: null,
    maskPoints: [],
    maskClosed: false,
    maskDataUrl: null,
    calibration: { origin: null, x: null, y: null, rawX: null, rawY: null, active: 'origin' },
  };

  const $ = (id) => document.getElementById(id);
  const all = (selector) => [...document.querySelectorAll(selector)];
  const fmt = (value) => Number.isFinite(value) ? (Math.abs(value - Math.round(value)) < 0.005 ? String(Math.round(value)) : value.toFixed(2)) : '—';
  const vector = (a, b) => ({ x: b.x - a.x, y: b.y - a.y });
  const length = (v) => Math.hypot(v.x, v.y);
  const angle = (v) => (Math.atan2(-v.y, v.x) * 180 / Math.PI + 360) % 360;
  const includedAngle = (a, b) => Math.acos(Math.max(-1, Math.min(1, (a.x * b.x + a.y * b.y) / (length(a) * length(b))))) * 180 / Math.PI;
  const axisX = () => ({ x: -Math.cos(AXIS_ANGLE), y: -Math.sin(AXIS_ANGLE) });
  const axisY = () => ({ x: Math.cos(AXIS_ANGLE), y: -Math.sin(AXIS_ANGLE) });

  function setStatus(message, kind = '') {
    const box = $('status'); box.textContent = message; box.className = `status ${kind}`;
  }
  function setBusy(button, busy) { if (button) { button.disabled = busy; button.dataset.oldText ||= button.textContent; button.textContent = busy ? '处理中…' : button.dataset.oldText; } }
  function jsonFetch(url, options = {}) {
    return fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options }).then(async (response) => {
      const body = await response.json().catch(() => ({}));
      if (!response.ok || body.error) throw new Error(body.error || `HTTP ${response.status}`);
      return body;
    });
  }
  function readFile(file) {
    return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
  }
  function loadImage(dataUrl) {
    return new Promise((resolve, reject) => { const image = new Image(); image.onload = () => resolve(image); image.onerror = reject; image.src = dataUrl; });
  }

  function field(id) { return $(id).value.trim(); }
  function populateOrder() {
    const order = state.order || {};
    const source = order.source || {};
    const generator = source.generator || {};
    const references = order.references || {};
    const calibration = order.calibration || {};
    const processing = order.processing || {};
    const review = order.review || {};
    const values = {
      work_order_id: order.work_order_id || '', building_id: order.building_id || '', house_id: order.house_id || '128', building_family: order.building_family || '',
      density: order.density || 'town', era: order.era || 'post_2000', footprint: order.footprint || '1x1', height_tiles: order.height_tiles || 8,
      sprite_mode: order.sprite_mode || 'single',
      target_template: calibration.target_template || (order.footprint === '2x2' ? 'templates/isometric-2x2-h8/spec.json' : 'templates/isometric-1x1-h8/spec.json'),
      background_method: (processing.background || {}).method || 'mask_file', reference_style: references.style || '', reference_architecture: references.architecture || '', reference_sketch: references.sketch || '',
      provider: generator.provider || '', model: generator.model || '', model_version: generator.model_version || '', prompt_version: generator.prompt_version || '', seed: generator.seed || '', prompt: generator.prompt || '',
      review_notes: review.notes || '', rights_status: review.rights_status || 'review', qa_status: review.qa_status || 'pending', reviewer: review.reviewer || 'user', catalog_notes: review.notes || '',
    };
    Object.entries(values).forEach(([id, value]) => { if ($(id)) $(id).value = value; });
    if (source.image && !state.sourceDataUrl) {
      state.sourceName = source.image.split('/').pop();
      $('sourceLabel').textContent = state.sourceName;
      setPreview(`/api/file?path=${encodeURIComponent(source.image)}`);
      loadImage(`/api/file?path=${encodeURIComponent(source.image)}`).then((image) => { state.sourceImage = image; drawAll(); }).catch(() => {});
    }
    if (calibration.source_origin) state.calibration.origin = point(calibration.source_origin);
    if (calibration.source_x_axis && state.calibration.origin) state.calibration.x = add(state.calibration.origin, point(calibration.source_x_axis));
    if (calibration.source_y_axis && state.calibration.origin) state.calibration.y = add(state.calibration.origin, point(calibration.source_y_axis));
    state.calibration.active = 'origin';
    updateSummary(); updateMetrics(); drawAll();
  }
  function newOrder() {
    state.order = null; state.sourceDataUrl = null; state.sourceName = ''; state.sourceImage = null; state.maskPoints = []; state.maskClosed = false; state.maskDataUrl = null;
    state.calibration = { origin: null, x: null, y: null, rawX: null, rawY: null, active: 'origin' };
    all('input, textarea').forEach((element) => { if (element.type === 'checkbox') element.checked = false; else if (element.id !== 'house_id' && element.id !== 'height_tiles' && element.id !== 'reviewer') element.value = ''; });
    $('house_id').value = '128'; $('height_tiles').value = '8'; $('density').value = 'town'; $('era').value = 'post_2000'; $('footprint').value = '1x1'; $('sprite_mode').value = 'single'; $('target_template').value = 'templates/isometric-1x1-h8/spec.json'; $('background_method').value = 'mask_file'; $('reviewer').value = 'user'; $('sourceLabel').textContent = '选择 AI 生成图（PNG/JPEG/WebP）';
    $('sourcePreview').innerHTML = '<span class="hint">尚未上传图像</span>'; setStage('brief'); updateSummary(); updateMetrics(); drawAll(); setStatus('新工单已准备好');
  }
  function buildOrder() {
    const o = state.order || {};
    const cal = state.calibration;
    const origin = cal.origin || { x: 0, y: 0 };
    const xv = cal.x ? vector(origin, cal.x) : { x: 128, y: 64 };
    const yv = cal.y ? vector(origin, cal.y) : { x: -128, y: 64 };
    const footprint = field('footprint');
    const backgroundMethod = field('background_method');
    return {
      schema: 1, work_order_id: field('work_order_id'), building_id: field('building_id'), house_id: field('house_id'), building_family: field('building_family'), density: field('density'), era: field('era'), footprint, height_tiles: Number(field('height_tiles') || 8),
      source: { image: (o.source || {}).image || '', generator: { provider: field('provider'), model: field('model'), model_version: field('model_version'), prompt_version: field('prompt_version'), seed: field('seed'), prompt: field('prompt') } },
      references: { style: field('reference_style'), architecture: field('reference_architecture'), sketch: field('reference_sketch') },
      calibration: { source_origin: [Math.round(origin.x), Math.round(origin.y)], source_x_axis: [Math.round(xv.x), Math.round(xv.y)], source_y_axis: [Math.round(yv.x), Math.round(yv.y)], ground_tile_size: Math.max(length(xv), length(yv)), ground_tile_policy: 'square_max', axis_scope: footprint === '2x2' ? 'footprint' : 'tile', projection_mode: 'uniform', target_template: field('target_template'), notes: 'Created in the TTD building workbench.' },
      processing: { saturation: 1, background: backgroundMethod === 'mask_file' ? (state.maskDataUrl ? { method: 'mask_file' } : ((o.processing || {}).background || { method: 'mask_file' })) : { method: backgroundMethod, tolerance: 24 } },
      sprite_mode: field('sprite_mode') || 'single',
      deliverables: o.deliverables || { preview: '', approved_zi4: '', mask: '' },
      review: { rights_status: field('rights_status') || 'review', qa_status: field('qa_status') || 'pending', reviewer: field('reviewer'), reviewed_at: o.review?.reviewed_at || '', notes: field('catalog_notes') || field('review_notes') },
    };
  }
  async function save() {
    const order = buildOrder();
    if (!order.work_order_id || !order.building_id) throw new Error('请先填写工单 ID 和建筑 ID');
    const result = await jsonFetch('/api/save', { method: 'POST', body: JSON.stringify({ order, source_data_url: state.sourceDataUrl, mask_data_url: state.maskDataUrl }) });
    state.order = result.order; updateSummary(); setStatus(`已保存 ${result.path}`, 'ok'); refreshState(); return result;
  }
  async function run(action) {
    const button = action === 'preview' ? $('runPreview') : action === 'process' ? $('runProcess') : action === 'slice' ? $('runSlice') : $('runRegister');
    try { setBusy(button, true); await save(); const result = await jsonFetch('/api/run', { method: 'POST', body: JSON.stringify({ work_order_id: field('work_order_id'), action }) }); state.order = result.order; updateSummary(); setStatus(`${action} 完成：${result.output}`, 'ok'); if (action === 'process') showFile(result.output); refreshState(); } catch (error) { setStatus(error.message, 'error'); } finally { setBusy(button, false); }
  }
  async function approve() {
    try { setBusy($('approveHere'), true); await save(); const result = await jsonFetch('/api/approve', { method: 'POST', body: JSON.stringify({ work_order_id: field('work_order_id'), rights_status: field('rights_status'), qa_status: field('qa_status'), reviewer: field('reviewer'), notes: field('catalog_notes') || field('review_notes'), reviewed_at: new Date().toISOString().slice(0, 10) }) }); state.order = result.order; updateSummary(); setStatus(result.approved ? '审核通过，已复制到 assets/approved/' : '审核状态已保存', result.approved ? 'ok' : ''); refreshState(); } catch (error) { setStatus(error.message, 'error'); } finally { setBusy($('approveHere'), false); }
  }
  async function build() {
    try { setBusy($('buildHere'), true); await save(); const result = await jsonFetch('/api/build', { method: 'POST', body: '{}' }); $('buildOutput').textContent = result.output || '构建完成'; setStatus('GRF 构建完成', 'ok'); refreshState(); } catch (error) { $('buildOutput').textContent = error.message; setStatus(error.message, 'error'); } finally { setBusy($('buildHere'), false); }
  }
  function setStage(stage) { state.stage = stage; all('[data-panel]').forEach((panel) => panel.classList.toggle('hidden', panel.dataset.panel !== stage)); all('#stageNav button').forEach((button) => button.classList.toggle('active', button.dataset.stage === stage)); const meta = { brief: ['参数与参考图', '先建立建筑身份、NML 参数和参考图记录。'], generate: ['生成与审核', '记录生成参数，人工抽卡并决定重做或继续。'], mask: ['人工扣图', '用多边形套索制作可重复的 alpha mask。'], calibrate: ['XY 投影标定', '把人工测量的原点和地面轴写入工单。'], process: ['自动配准与切片', '调用现有 Pillow 工具生成 zi4 和多 tile 检查图。'], catalog: ['素材库与构建', '审核、登记 manifest，或构建整个 GRF。'] }[stage]; $('stageTitle').textContent = meta[0]; $('stageDescription').textContent = meta[1]; drawAll(); }
  function point(value) { return { x: Number(value[0]), y: Number(value[1]) }; }
  function add(a, b) { return { x: a.x + b.x, y: a.y + b.y }; }
  function snapToAxis(p, axis) { const o = state.calibration.origin; const distance = (p.x - o.x) * axis.x + (p.y - o.y) * axis.y; return add(o, { x: axis.x * distance, y: axis.y * distance }); }
  function imagePoint(canvas, event) { const rect = canvas.getBoundingClientRect(); return { x: (event.clientX - rect.left) * canvas.width / rect.width, y: (event.clientY - rect.top) * canvas.height / rect.height }; }
  function setupCanvas(canvas) { if (!state.sourceImage) return; canvas.width = state.sourceImage.width; canvas.height = state.sourceImage.height; canvas.style.aspectRatio = `${canvas.width} / ${canvas.height}`; }
  function drawImageBase(ctx, canvas) { ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.fillStyle = '#080b0d'; ctx.fillRect(0, 0, canvas.width, canvas.height); if (state.sourceImage) { ctx.imageSmoothingEnabled = false; ctx.drawImage(state.sourceImage, 0, 0); } }
  function drawMask() { const canvas = $('maskCanvas'); if (!state.sourceImage) { canvas.width = 1; canvas.height = 1; return; } setupCanvas(canvas); const ctx = canvas.getContext('2d'); drawImageBase(ctx, canvas); if (!state.maskPoints.length) return; ctx.save(); ctx.fillStyle = '#70e38a55'; ctx.strokeStyle = '#70e38a'; ctx.lineWidth = Math.max(2, canvas.width / 500); ctx.beginPath(); state.maskPoints.forEach((p, index) => index ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)); if (state.maskClosed) ctx.closePath(); ctx.fill(); ctx.stroke(); state.maskPoints.forEach((p, index) => { ctx.fillStyle = index === 0 ? '#70e38a' : '#55d6e8'; ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(4, canvas.width / 160), 0, TAU); ctx.fill(); }); ctx.restore(); }
  function drawCalibration() { const canvas = $('calCanvas'); if (!state.sourceImage) { canvas.width = 1; canvas.height = 1; return; } setupCanvas(canvas); const ctx = canvas.getContext('2d'); drawImageBase(ctx, canvas); const cal = state.calibration; if (!cal.origin) return; const drawLine = (a, b, color, dash = []) => { ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = Math.max(2, canvas.width / 600); ctx.setLineDash(dash); ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); ctx.restore(); }; const infinite = (origin, direction, color) => { const far = 3 * Math.max(canvas.width, canvas.height); drawLine({ x: origin.x - direction.x * far, y: origin.y - direction.y * far }, { x: origin.x + direction.x * far, y: origin.y + direction.y * far }, color, [8, 8]); }; infinite(cal.origin, axisX(), '#55d6e855'); infinite(cal.origin, axisY(), '#ffca6455'); if (cal.x) drawLine(cal.origin, cal.x, '#55d6e8'); if (cal.y) drawLine(cal.origin, cal.y, '#ffca64'); [[cal.origin, '#70e38a'], [cal.x, '#55d6e8'], [cal.y, '#ffca64']].forEach(([p, color]) => { if (!p) return; ctx.fillStyle = color; ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(5, canvas.width / 100), 0, TAU); ctx.fill(); }); }
  function drawAll() { drawMask(); drawCalibration(); }
  function updateMetrics() { const cal = state.calibration; $('metricOrigin').textContent = cal.origin ? `(${fmt(cal.origin.x)}, ${fmt(cal.origin.y)})` : '未设置'; const xv = cal.origin && cal.x ? vector(cal.origin, cal.x) : null; const yv = cal.origin && cal.y ? vector(cal.origin, cal.y) : null; $('metricX').textContent = xv ? `(${fmt(xv.x)}, ${fmt(xv.y)}) · ${fmt(length(xv))} px` : '未设置'; $('metricY').textContent = yv ? `(${fmt(yv.x)}, ${fmt(yv.y)}) · ${fmt(length(yv))} px` : '未设置'; $('metricAngle').textContent = xv && yv ? `${fmt(includedAngle(xv, yv))}° · 目标 126.87°` : '未设置'; $('metricSize').textContent = xv && yv ? `${fmt(Math.max(length(xv), length(yv)))} px` : '未设置'; }
  function updateSummary() { const order = state.order || buildOrder(); $('orderSummary').textContent = JSON.stringify(order, null, 2); }
  function setPreview(src) { $('sourcePreview').innerHTML = `<img alt="生成结果" src="${src}">`; }
  function showFile(path) { setPreview(`/api/file?path=${encodeURIComponent(path)}`); $('processPreview').innerHTML = `<img alt="zi4 输出" src="/api/file?path=${encodeURIComponent(path)}">`; }
  function makeMaskDataUrl() { if (!state.sourceImage || state.maskPoints.length < 3 || !state.maskClosed) return null; const canvas = document.createElement('canvas'); canvas.width = state.sourceImage.width; canvas.height = state.sourceImage.height; const ctx = canvas.getContext('2d'); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.fillStyle = '#fff'; ctx.beginPath(); state.maskPoints.forEach((p, index) => index ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)); ctx.closePath(); ctx.fill(); return canvas.toDataURL('image/png'); }
  async function refreshState() { try { const result = await fetch('/api/state').then((response) => response.json()); const items = result.manifest || []; const orders = result.orders || []; $('orderSelect').innerHTML = '<option value="">选择工单…</option>' + orders.map((order) => `<option value="${order.work_order_id}">${order.work_order_id} · ${order.building_id || '未命名'}</option>`).join(''); $('manifestList').innerHTML = items.length ? items.map((row) => `<div class="panel small"><b>${row.asset_id || '—'}</b><br>${row.building_id || '—'} · ${row.footprint || '—'}<br><span class="hint">${row.qa_status || '—'} / ${row.rights_status || '—'}</span></div>`).join('') : '<span class="hint">尚无登记素材</span>'; } catch (_) { $('manifestList').textContent = '本地服务未连接'; } }
  async function loadExisting() { try { const selectedId = $('orderSelect').value; if (!selectedId) { setStatus('请先选择一个已保存工单'); return; } const result = await fetch('/api/state').then((response) => response.json()); const selected = (result.orders || []).find((order) => order.work_order_id === selectedId); if (!selected) { setStatus('工单列表已变化，请刷新后重试', 'error'); return; } state.order = selected; state.sourceDataUrl = null; state.maskDataUrl = null; state.maskPoints = []; state.maskClosed = false; populateOrder(); setStatus(`已读取 ${state.order.work_order_id}`, 'ok'); } catch (error) { setStatus(error.message, 'error'); } }

  $('sourceInput').addEventListener('change', async () => { const file = $('sourceInput').files[0]; if (!file) return; state.sourceName = file.name; state.sourceDataUrl = await readFile(file); state.sourceImage = await loadImage(state.sourceDataUrl); $('sourceLabel').textContent = `${file.name} · ${state.sourceImage.width}×${state.sourceImage.height}`; setPreview(state.sourceDataUrl); state.maskPoints = []; state.maskClosed = false; state.maskDataUrl = null; state.calibration = { origin: null, x: null, y: null, rawX: null, rawY: null, active: 'origin' }; drawAll(); updateMetrics(); updateSummary(); });
  $('sourceDrop').addEventListener('dragover', (event) => { event.preventDefault(); $('sourceDrop').classList.add('drag'); }); $('sourceDrop').addEventListener('dragleave', () => $('sourceDrop').classList.remove('drag')); $('sourceDrop').addEventListener('drop', (event) => { event.preventDefault(); $('sourceDrop').classList.remove('drag'); const file = event.dataTransfer.files[0]; if (file) { const transfer = new DataTransfer(); transfer.items.add(file); $('sourceInput').files = transfer.files; $('sourceInput').dispatchEvent(new Event('change')); } });
  $('maskCanvas').addEventListener('click', (event) => { if (!state.sourceImage || state.maskClosed) return; state.maskPoints.push(imagePoint($('maskCanvas'), event)); drawMask(); }); $('maskCanvas').addEventListener('dblclick', (event) => { event.preventDefault(); state.maskClosed = state.maskPoints.length >= 3; state.maskDataUrl = makeMaskDataUrl(); drawMask(); updateSummary(); });
  $('maskUndo').addEventListener('click', () => { if (state.maskClosed) state.maskClosed = false; state.maskPoints.pop(); state.maskDataUrl = makeMaskDataUrl(); drawMask(); }); $('maskClose').addEventListener('click', () => { state.maskClosed = state.maskPoints.length >= 3; state.maskDataUrl = makeMaskDataUrl(); drawMask(); updateSummary(); }); $('maskClear').addEventListener('click', () => { state.maskPoints = []; state.maskClosed = false; state.maskDataUrl = null; drawMask(); updateSummary(); });
  $('calCanvas').addEventListener('click', (event) => { if (!state.sourceImage) return; const p = imagePoint($('calCanvas'), event); const cal = state.calibration; if (cal.active === 'origin') { cal.origin = p; cal.x = cal.y = cal.rawX = cal.rawY = null; cal.active = 'x'; } else if (cal.active === 'x') { cal.rawX = p; cal.x = snapToAxis(p, axisX()); cal.active = 'y'; } else { cal.rawY = p; cal.y = snapToAxis(p, axisY()); cal.active = 'x'; } updateMetrics(); updateSummary(); drawCalibration(); });
  $('calReset').addEventListener('click', () => { state.calibration = { origin: null, x: null, y: null, rawX: null, rawY: null, active: 'origin' }; updateMetrics(); updateSummary(); drawCalibration(); }); $('calOrigin').addEventListener('click', () => { state.calibration.active = 'origin'; }); $('calX').addEventListener('click', () => { state.calibration.active = 'x'; }); $('calY').addEventListener('click', () => { state.calibration.active = 'y'; });
  $('footprint').addEventListener('change', () => { $('target_template').value = field('footprint') === '2x2' ? 'templates/isometric-2x2-h8/spec.json' : 'templates/isometric-1x1-h8/spec.json'; updateSummary(); });
  $('stageNav').addEventListener('click', (event) => { const button = event.target.closest('button[data-stage]'); if (button) setStage(button.dataset.stage); }); $('newOrder').addEventListener('click', newOrder); $('loadOrder').addEventListener('click', loadExisting); $('saveOrder').addEventListener('click', async () => { try { setBusy($('saveOrder'), true); await save(); } catch (error) { setStatus(error.message, 'error'); } finally { setBusy($('saveOrder'), false); } });
  $('runPreview').addEventListener('click', () => run('preview')); $('runProcess').addEventListener('click', () => run('process')); $('runSlice').addEventListener('click', () => run('slice')); $('runRegister').addEventListener('click', () => run('register')); $('processHere').addEventListener('click', () => run('process')); $('sliceHere').addEventListener('click', () => run('slice')); $('approveHere').addEventListener('click', approve); $('registerHere').addEventListener('click', () => run('register')); $('buildHere').addEventListener('click', build);
  $('copyPrompt').addEventListener('click', async () => { try { await navigator.clipboard.writeText(field('prompt')); setStatus('提示词已复制'); } catch (_) { setStatus('浏览器不允许复制，请手动选择提示词'); } }); $('markGenerated').addEventListener('click', () => { setStage('mask'); setStatus('请继续进行人工扣图和标定'); });
  window.addEventListener('resize', drawAll);
  newOrder(); refreshState();
})();
