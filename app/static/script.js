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

let pollTimer = null;
let activeJob = null;

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
        listo: '✅ Listo'
    };
    orbStage.textContent = stageMap[job.stage] || job.stage || '';
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
            clearInterval(pollTimer);
            pollTimer = null;
            activeJob = null;
            hideOverlay();
            downloadBtn.disabled = false;
            const ok = job.status === 'done';
            const failNote = job.failed > 0 ? ` (⚠ ${job.failed} fallaron — ver Historial)` : '';
            showFeedback(ok, (job.message || job.status) + failNote, true);
            refreshHistory();
            if (ok) urlInput.value = '';
        }
    } catch (err) {
        clearInterval(pollTimer);
        pollTimer = null;
        activeJob = null;
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
const historyClose = document.getElementById('historyClose');
const historyList = document.getElementById('historyList');

const STATUS_STYLE = {
    done: 'border-dracula-green/40 text-dracula-green',
    error: 'border-dracula-red/40 text-dracula-red',
    cancelled: 'border-dracula-yellow/40 text-dracula-yellow',
};

const STATUS_LABEL = { done: '✅ listo', error: '❌ error', cancelled: '⏸ cancelado' };

function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function fmtTime(ts) {
    if (!ts) return '';
    return new Date(ts * 1000).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

function jobCard(job, open = false) {
    const fails = (job.items || []).filter((it) => it.status === 'fail');
    const failsHtml = fails.length
        ? `<div class="mt-2 text-xs"><p class="text-dracula-red font-semibold mb-1">Fallaron (${fails.length}):</p><ul class="list-disc ml-5 space-y-0.5 text-dracula-fg/90">${fails.map((it) => `<li>${esc(it.title)}</li>`).join('')}</ul></div>`
        : '';
    const oks = (job.items || []).filter((it) => it.status === 'ok').length;
    return `<details ${open ? 'open' : ''} class="bg-black/20 border rounded-2xl px-4 py-3 ${STATUS_STYLE[job.status] || 'border-dracula-comment/30'}">
        <summary class="cursor-pointer flex flex-wrap items-center gap-x-3 gap-y-1">
            <span class="font-semibold">${STATUS_LABEL[job.status] || esc(job.status)}</span>
            <span class="text-dracula-fg text-sm">${job.total > 1 ? `${oks}/${job.total} rolas` : esc(job.message || '')}</span>
            <span class="text-dracula-comment text-xs ml-auto">${fmtTime(job.finished || job.created)}</span>
        </summary>
        <p class="mt-2 text-xs text-dracula-comment break-all">${esc(job.url)}</p>
        ${failsHtml}
    </details>`;
}

async function refreshHistory() {
    try {
        const res = await fetch('/api/history?limit=50');
        if (!res.ok) return;
        const data = await res.json();
        const hist = data.history || [];
        historyList.innerHTML = hist.length
            ? hist.map((job, i) => jobCard(job, i === 0)).join('')
            : '<p class="text-dracula-comment text-sm">Sin descargas todavía.</p>';
    } catch (err) {
        historyList.innerHTML = '<p class="text-dracula-red text-sm">No se pudo cargar el historial.</p>';
    }
}

historyBtn.addEventListener('click', () => {
    historyOverlay.classList.remove('hidden');
    historyOverlay.setAttribute('aria-hidden', 'false');
    refreshHistory();
});

function closeHistory() {
    historyOverlay.classList.add('hidden');
    historyOverlay.setAttribute('aria-hidden', 'true');
}

historyClose.addEventListener('click', closeHistory);
historyOverlay.addEventListener('click', (e) => {
    if (e.target === historyOverlay) closeHistory();
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !historyOverlay.classList.contains('hidden')) closeHistory();
});
