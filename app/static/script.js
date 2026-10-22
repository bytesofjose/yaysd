const form = document.getElementById('downloadForm');
const urlInput = document.getElementById('urlInput');
const downloadBtn = document.getElementById('downloadBtn');
const feedbackContainer = document.getElementById('feedbackContainer');
const feedbackText = document.getElementById('feedbackText');

const overlay = document.getElementById('orbOverlay');
const orbProgress = document.getElementById('orbProgress');
const orbPercent = document.getElementById('orbPercent');
const orbCount = document.getElementById('orbCount');
const orbBarFill = document.getElementById('orbBarFill');
const orbTitle = document.getElementById('orbTitle');
const orbStage = document.getElementById('orbStage');
const orbCancel = document.getElementById('orbCancel');

const RING_C = 2 * Math.PI * 52;
orbProgress.style.strokeDasharray = String(RING_C);
orbProgress.style.strokeDashoffset = String(RING_C);

const LAST_URL_KEY = 'guardarol:lastUrl';
const ACTIVE_JOB_KEY = 'guardarol:activeJob';

let activeJob = null;
let pollTimer = null;

urlInput.value = localStorage.getItem(LAST_URL_KEY) || '';
urlInput.addEventListener('input', () => {
    const v = urlInput.value.trim();
    if (v) localStorage.setItem(LAST_URL_KEY, urlInput.value);
    else localStorage.removeItem(LAST_URL_KEY);
});

function clearUrl() {
    urlInput.value = '';
    try { localStorage.removeItem(LAST_URL_KEY); } catch (err) { /* ignore */ }
}

function clearActiveJob() {
    activeJob = null;
    try { localStorage.removeItem(ACTIVE_JOB_KEY); } catch (err) { /* ignore */ }
}

function saveActiveJob() {
    try {
        if (activeJob) localStorage.setItem(ACTIVE_JOB_KEY, JSON.stringify(activeJob));
    } catch (err) { /* ignore */ }
}

function stopPolling() {
    clearInterval(pollTimer);
    pollTimer = null;
}

function showOverlay() {
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('overflow-hidden');
}

function hideOverlay() {
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('overflow-hidden');
}

function renderJob(job) {
    const pct = Math.max(0, Math.min(100, Number(job.percent) || 0));
    orbProgress.style.strokeDashoffset = String(RING_C * (1 - pct / 100));
    orbPercent.textContent = `${Math.round(pct)}%`;
    orbBarFill.style.width = `${pct}%`;
    if (job.total > 0) {
        orbCount.textContent = `${job.done}/${job.total} rolas`;
    } else {
        orbCount.textContent = 'Leyendo links…';
    }
    orbTitle.textContent = job.current_title || job.message || 'Trabajando…';
    const stageMap = {
        descargando: '⬇ Descargando audio original',
        'guardando en biblioteca': '⚙ Guardando en tu biblioteca…',
        resolviendo: '🔍 Resolviendo URL…',
        'en pausa': '⏸ En pausa — reanuda desde Historial o aquí',
        listo: '✅ Listo'
    };
    orbStage.textContent = stageMap[job.stage] || job.stage || '';
    if (orbPause) orbPause.textContent = job.status === 'paused' ? 'Reanudar' : 'Pausar';
}

let toastTimer = null;

function showFeedback(ok, msg, sticky = false) {
    clearTimeout(toastTimer);
    feedbackContainer.classList.remove('hidden', 'success', 'error');
    feedbackContainer.classList.add(ok ? 'success' : 'error');
    feedbackText.textContent = msg;
    if (!sticky) {
        toastTimer = setTimeout(() => feedbackContainer.classList.add('hidden'), 6000);
    }
}

document.getElementById('feedbackClose').addEventListener('click', () => {
    clearTimeout(toastTimer);
    feedbackContainer.classList.add('hidden');
});

async function pollJob(jobId) {
    try {
        const res = await fetch(`/api/job/${jobId}`);
        if (!res.ok) throw new Error('job perdido');
        const job = await res.json();
        renderJob(job);
        if (job.status === 'done' || job.status === 'error' || job.status === 'cancelled') {
            stopPolling();
            clearActiveJob();
            hideOverlay();
            downloadBtn.disabled = false;
            const ok = job.status === 'done';
            const failNote = job.failed > 0 ? ` (⚠ ${job.failed} fallaron — ver Historial)` : '';
            showFeedback(ok, (job.message || job.status) + failNote, true);
            refreshHistory();
            if (ok) clearUrl();
        }
    } catch (err) {
        stopPolling();
        hideOverlay();
        downloadBtn.disabled = false;
        showFeedback(false, 'Se perdió la conexión con el servidor.');
    }
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url || activeJob) return;

    clearTimeout(toastTimer);
    feedbackContainer.classList.add('hidden');
    downloadBtn.disabled = true;
    showOverlay();
    renderJob({ percent: 0, total: 0, done: 0, current_title: '', stage: 'resolviendo', message: 'Resolviendo URL…' });

    try {
        const formData = new FormData();
        formData.append('url', url);
        const res = await fetch('/download', { method: 'POST', body: formData });
        const data = await res.json();
        if (!data.job_id) throw new Error(data.message || 'sin job');
        activeJob = data.job_id;
        saveActiveJob();
        stopPolling();
        pollTimer = setInterval(() => pollJob(activeJob), 1000);
        pollJob(activeJob);
    } catch (err) {
        hideOverlay();
        downloadBtn.disabled = false;
        showFeedback(false, 'Error de conexión con el servidor.');
    }
});

orbCancel.addEventListener('click', async () => {
    if (!activeJob) return;
    orbCancel.disabled = true;
    try {
        await fetch(`/api/job/${activeJob}/cancel`, { method: 'POST' });
    } catch (err) {
        /* poll loop will surface the state */
    }
    orbCancel.disabled = false;
});

const historyBtn = document.getElementById('historyBtn');
const historyOverlay = document.getElementById('historyOverlay');
const historyBack = document.getElementById('historyBack');
const historyList = document.getElementById('historyList');
const orbPause = document.getElementById('orbPause');

const BADGE = {
    running: 'border-dracula-cyan/40 text-dracula-cyan',
    paused: 'border-dracula-yellow/40 text-dracula-yellow',
    ok: 'border-dracula-green/40 text-dracula-green',
    warning: 'border-dracula-yellow/40 text-dracula-yellow',
    error: 'border-dracula-red/40 text-dracula-red',
    cancelled: 'border-dracula-comment/40 text-dracula-comment',
};

function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function fmtTime(ts) {
    if (!ts) return '';
    return new Date(ts * 1000).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

function jobBadge(job) {
    if (job.status === 'resolving' || job.status === 'downloading') return ['running', '● En curso'];
    if (job.status === 'paused') return ['paused', '⏸ En pausa'];
    if (job.status === 'done') return job.failed > 0 ? ['warning', '⚠ Terminó con avisos'] : ['ok', '✅ OK'];
    if (job.status === 'error') return ['error', '❌ Error'];
    return ['cancelled', '⏹ Cancelado'];
}

function jobCard(job, open = false) {
    const [cls, label] = jobBadge(job);
    const live = job.status === 'resolving' || job.status === 'downloading' || job.status === 'paused';
    const items = job.items || [];
    const oks = items.filter((it) => it.status === 'ok').length;
    const skipped = items.filter((it) => it.status === 'skipped').length;
    const failed = job.failed || items.filter((it) => it.status === 'fail').length;
    const fails = items.filter((it) => it.status === 'fail');
    const failsHtml = fails.length
        ? `<div class="mt-2 text-xs"><p class="text-dracula-red font-semibold mb-1">Fallaron (${fails.length}):</p><ul class="list-disc ml-5 space-y-0.5 text-dracula-fg/90">${fails.map((it) => `<li>${esc(it.title)}</li>`).join('')}</ul></div>`
        : '';
    const pct = Math.max(0, Math.min(100, Number(job.percent) || 0));
    const progressHtml = live
        ? `<div class="mt-2 w-full h-2 rounded-full bg-black/40 overflow-hidden"><div class="h-full rounded-full bg-gradient-to-r from-dracula-purple to-dracula-pink" style="width:${pct}%"></div></div>`
        : '';
    const controlsHtml = live
        ? `<div class="mt-3 flex gap-2">
               ${job.status === 'paused'
                   ? `<button data-act="resume" data-id="${job.id}" class="px-4 py-1.5 text-sm rounded-full border border-dracula-green text-dracula-green cursor-pointer transition-all hover:bg-dracula-green hover:text-dracula-bg">▶ Reanudar</button>`
                   : `<button data-act="pause" data-id="${job.id}" class="px-4 py-1.5 text-sm rounded-full border border-dracula-yellow text-dracula-yellow cursor-pointer transition-all hover:bg-dracula-yellow hover:text-dracula-bg">⏸ Pausar</button>`}
               <button data-act="cancel" data-id="${job.id}" class="px-4 py-1.5 text-sm rounded-full border border-dracula-red text-dracula-red cursor-pointer transition-all hover:bg-dracula-red hover:text-dracula-bg">⏹ Detener</button>
           </div>`
        : '';
    return `<div class="bg-black/20 border rounded-2xl px-4 py-3 ${BADGE[cls]}">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span class="font-semibold text-sm border rounded-full px-3 py-0.5 ${BADGE[cls]}">${label}</span>
            <span class="text-dracula-fg text-sm font-semibold">${job.total > 1 ? `${oks + skipped}/${job.total} rolas` : esc(job.current_title || job.message || '')}</span>
        </div>
        <p class="mt-2 text-xs text-dracula-fg/80 break-all">${esc(job.url)}</p>
        <div class="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <div><span class="text-dracula-comment">IP </span><span class="text-dracula-fg">${esc(job.ip || '—')}</span></div>
            <div><span class="text-dracula-comment">Inicio </span><span class="text-dracula-fg">${fmtTime(job.created)}</span></div>
            <div><span class="text-dracula-comment">Fin </span><span class="text-dracula-fg">${job.finished ? fmtTime(job.finished) : '—'}</span></div>
            <div><span class="text-dracula-comment">OK/hay/fallo </span><span class="text-dracula-fg">${oks}/${skipped}/${failed}</span></div>
        </div>
        ${progressHtml}
        ${failsHtml}
        ${controlsHtml}
    </div>`;
}

let historyTimer = null;

async function refreshHistory() {
    try {
        const res = await fetch('/api/history?limit=50');
        if (!res.ok) return;
        const data = await res.json();
        const hist = data.history || [];
        historyList.innerHTML = hist.length
            ? hist.map((job) => jobCard(job, false)).join('')
            : '<p class="text-dracula-comment text-sm">Sin descargas todavía.</p>';
    } catch (err) {
        historyList.innerHTML = '<p class="text-dracula-red text-sm">No se pudo cargar el historial.</p>';
    }
}

historyList.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-act]');
    if (!btn) return;
    const { act, id } = btn.dataset;
    const endpoint = act === 'pause' ? 'pause' : act === 'resume' ? 'resume' : 'cancel';
    btn.disabled = true;
    try {
        await fetch(`/api/job/${id}/${endpoint}`, { method: 'POST' });
    } catch (err) { /* refresh will show it */ }
    refreshHistory();
});

function openHistory() {
    historyOverlay.classList.remove('hidden');
    historyOverlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('overflow-hidden');
    refreshHistory();
    if (!historyTimer) historyTimer = setInterval(refreshHistory, 2000);
}

function closeHistory() {
    historyOverlay.classList.add('hidden');
    historyOverlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('overflow-hidden');
    clearInterval(historyTimer);
    historyTimer = null;
}

historyBtn.addEventListener('click', openHistory);
historyBack.addEventListener('click', closeHistory);
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !historyOverlay.classList.contains('hidden')) closeHistory();
});

orbPause.addEventListener('click', async () => {
    if (!activeJob) return;
    orbPause.disabled = true;
    try {
        const res = await fetch(`/api/job/${activeJob}`, { cache: 'no-store' }).then((r) => r.json());
        const endpoint = res.status === 'paused' ? 'resume' : 'pause';
        await fetch(`/api/job/${activeJob}/${endpoint}`, { method: 'POST' });
    } catch (err) { /* poll loop will show it */ }
    orbPause.disabled = false;
});

async function reattach() {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(ACTIVE_JOB_KEY) || 'null'); } catch (err) { /* ignore */ }
    if (!saved) return;
    try {
        const res = await fetch(`/api/job/${saved}`);
        if (!res.ok) throw new Error('job perdido');
        const job = await res.json();
        if (job.status === 'resolving' || job.status === 'downloading') {
            activeJob = saved;
            if (job.url) {
                urlInput.value = job.url;
                try { localStorage.setItem(LAST_URL_KEY, job.url); } catch (err) { /* ignore */ }
            }
            downloadBtn.disabled = true;
            showOverlay();
            renderJob(job);
            stopPolling();
            pollTimer = setInterval(() => pollJob(activeJob), 1000);
        } else {
            clearActiveJob();
            renderJob(job);
            const ok = job.status === 'done';
            showFeedback(ok, job.message || job.status, true);
            refreshHistory();
            if (ok) clearUrl();
        }
    } catch (err) {
        clearActiveJob();
    }
}

reattach();
