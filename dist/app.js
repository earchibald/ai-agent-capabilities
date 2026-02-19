'use strict';

// ── Constants ────────────────────────────────────────────
const API = './api/v1';

const CATEGORY_LABELS = {
  'agent-orchestration': 'Agent Orchestration',
  'code-completion':     'Code Completion',
  'code-generation':     'Code Generation',
  'chat-assistance':     'Chat Assistance',
  'code-explanation':    'Code Explanation',
  'code-refactoring':    'Code Refactoring',
  'testing':             'Testing',
  'debugging':           'Debugging',
  'documentation':       'Documentation',
  'command-line':        'Command Line',
  'multi-file-editing':  'Multi-File Editing',
  'context-awareness':   'Context Awareness',
  'language-support':    'Language Support',
  'ide-integration':     'IDE Integration',
  'api-integration':     'API Integration',
  'customization':       'Customization',
  'security':            'Security',
  'performance':         'Performance',
  'collaboration':       'Collaboration',
  'model-selection':     'Model Selection',
  'observability':       'Observability',
};

// ── State ────────────────────────────────────────────────
let state = {
  agentIndex: null,        // agents.json data
  capabilities: null,      // capabilities.json data
  agentDetails: {},        // cache: slug -> agents/{slug}.json data
  activeTab: 'compare',
  selectedAgent: null,
  expandedCompareRow: null,
  expandedBrowseCard: null,
  filters: { search: '', category: '', tier: '' },
};

// ── Fetch helper ─────────────────────────────────────────
async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json();
}

// ── Init ─────────────────────────────────────────────────
async function init() {
  try {
    const index = await fetchJSON(`${API}/index.json`);
    renderStats(index);
    await loadCompareTab();
  } catch (e) {
    console.error('Init failed:', e);
  }
}

// ── Stats strip ──────────────────────────────────────────
function renderStats(index) {
  const q = index.dataQuality;
  const strip = document.getElementById('stats-strip');
  const date = index.lastUpdated
    ? new Date(index.lastUpdated).toLocaleDateString('en-GB', {day:'numeric',month:'short',year:'numeric'})
    : '';
  strip.innerHTML = `
    <div class="stat"><span class="stat-value">${q.totalCapabilities}</span><span class="stat-label">capabilities tracked</span></div>
    <div class="stat"><span class="stat-value">${index.agents.length}</span><span class="stat-label">agents</span></div>
    <div class="stat"><span class="stat-value">${q.totalSources}</span><span class="stat-label">verified sources</span></div>
    <div class="stat"><span class="stat-value">${q.brokenSources}</span><span class="stat-label">broken sources</span></div>
    ${date ? `<div class="stat"><span class="stat-value" style="font-size:1rem">${date}</span><span class="stat-label">last updated</span></div>` : ''}
  `;
}

// ── Tabs ─────────────────────────────────────────────────
function switchTab(tab) {
  state.activeTab = tab;
  document.getElementById('pane-compare').style.display = tab === 'compare' ? '' : 'none';
  document.getElementById('pane-browse').style.display  = tab === 'browse'  ? '' : 'none';
  document.getElementById('tab-compare').classList.toggle('active', tab === 'compare');
  document.getElementById('tab-browse').classList.toggle('active',  tab === 'browse');
  if (tab === 'browse') loadBrowseTab();
}

// ── Copy URL ─────────────────────────────────────────────
function copyUrl() {
  const url = document.getElementById('llm-url').textContent.trim();
  navigator.clipboard.writeText(url).then(() => {
    const btn = document.getElementById('copy-btn');
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1500);
  });
}

// ── Badges ───────────────────────────────────────────────
function tierBadge(tier) {
  if (!tier || tier === 'free') return `<span class="badge badge-tier-free">Free</span>`;
  const label = tier.charAt(0).toUpperCase() + tier.slice(1);
  return `<span class="badge badge-tier-${tier}">${label}</span>`;
}

function maturityBadge(level) {
  if (!level || level === 'stable') return '';
  if (level === 'beta')         return `<span class="badge badge-beta">Beta</span>`;
  if (level === 'experimental') return `<span class="badge badge-experimental">Experimental</span>`;
  if (level === 'deprecated')   return `<span class="badge badge-deprecated">Deprecated</span>`;
  return '';
}

// ── Detail panel HTML ────────────────────────────────────
function detailPanelHTML(cap) {
  const terminology = cap.terminology
    ? `<p style="font-size:.8rem;color:var(--text-muted);margin-bottom:.5rem">Known as <strong>${escHtml(cap.terminology)}</strong> in this agent</p>`
    : '';
  const limitations = (cap.limitations || []).map(l => `<li>${escHtml(l)}</li>`).join('');
  const requirements = (cap.requirements || []).map(r => `<li>${escHtml(r)}</li>`).join('');
  const sources = (cap.sources || []).map(s => {
    const granLabel = s.sourceGranularity === 'dedicated' ? 'Dedicated page'
                    : s.sourceGranularity === 'section'   ? 'Section'
                    : 'Excerpt';
    const excerptHtml = s.excerpt
      ? `<span class="source-excerpt">${escHtml(s.excerpt)}</span>`
      : '';
    return `<div class="source-item">
      <a href="${s.url}" target="_blank" rel="noopener">${escHtml(s.description || s.url)}</a>
      <div class="source-meta">${granLabel} · Verified ${s.verifiedDate || '—'}</div>
      ${excerptHtml}
    </div>`;
  }).join('');

  return `
    <div class="detail-panel">
      <div class="detail-section" style="grid-column:1/-1">
        <h4>Description</h4>
        ${terminology}
        <p>${escHtml(cap.description || '')}</p>
      </div>
      ${limitations ? `<div class="detail-section"><h4>Limitations</h4><ul>${limitations}</ul></div>` : ''}
      ${requirements ? `<div class="detail-section"><h4>Requirements</h4><ul>${requirements}</ul></div>` : ''}
      ${sources ? `<div class="detail-section" style="grid-column:1/-1"><h4>Sources</h4><div class="source-list">${sources}</div></div>` : ''}
    </div>`;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// ── Compare tab ──────────────────────────────────────────
async function loadCompareTab() {
  try {
    const [capsData, agentsData] = await Promise.all([
      fetchJSON(`${API}/capabilities.json`),
      fetchJSON(`${API}/agents.json`),
    ]);
    state.capabilities = capsData.capabilities;
    state.agentIndex = agentsData.agents;

    // Fetch all agent detail files in parallel (needed for expand detail panel)
    const detailFetches = agentsData.agents.map(a =>
      fetchJSON(`${API}/agents/${a.slug}.json`).then(d => { state.agentDetails[a.slug] = d; })
    );
    await Promise.all(detailFetches);

    // Populate category filter
    const cats = [...new Set(state.capabilities.map(c => c.category))].sort();
    const catSelect = document.getElementById('filter-category');
    cats.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = CATEGORY_LABELS[c] || c;
      catSelect.appendChild(opt);
    });

    renderCompareTable();
  } catch (e) {
    document.getElementById('compare-table-wrap').innerHTML =
      `<div class="empty-state"><p>Failed to load data. Please refresh.</p></div>`;
    console.error(e);
  }
}

function applyFilters() {
  state.filters.search   = document.getElementById('filter-search').value.toLowerCase();
  state.filters.category = document.getElementById('filter-category').value;
  state.filters.tier     = document.getElementById('filter-tier').value;
  state.expandedCompareRow = null;
  renderCompareTable();
}

function renderCompareTable() {
  const agents = state.agentIndex;
  let caps = state.capabilities;

  if (state.filters.search) {
    caps = caps.filter(c => c.name.toLowerCase().includes(state.filters.search));
  }
  if (state.filters.category) {
    caps = caps.filter(c => c.category === state.filters.category);
  }
  if (state.filters.tier) {
    caps = caps.filter(c =>
      c.agents.some(a => a.tier === state.filters.tier && a.available)
    );
  }

  document.getElementById('filter-count').textContent =
    caps.length === state.capabilities.length ? `${caps.length} capabilities`
    : `${caps.length} of ${state.capabilities.length} capabilities`;

  if (caps.length === 0) {
    document.getElementById('compare-table-wrap').innerHTML =
      `<div class="empty-state"><p>No capabilities match the current filters.</p></div>`;
    return;
  }

  const byCategory = {};
  caps.forEach(c => {
    if (!byCategory[c.category]) byCategory[c.category] = [];
    byCategory[c.category].push(c);
  });

  const agentColspan = agents.length + 1;
  let html = `<table class="compare">
    <thead>
      <tr>
        <th class="col-name">Capability</th>
        ${agents.map(a => `<th class="col-agent">${escHtml(a.name)}</th>`).join('')}
      </tr>
    </thead>
    <tbody>`;

  Object.entries(byCategory).sort(([a],[b]) => a.localeCompare(b)).forEach(([cat, catCaps]) => {
    html += `<tr class="category-row"><td colspan="${agentColspan}">${escHtml(CATEGORY_LABELS[cat] || cat)}</td></tr>`;
    catCaps.forEach(cap => {
      const isExpanded = state.expandedCompareRow === cap.slug;
      html += `<tr class="cap-row${isExpanded ? ' expanded' : ''}"
        onclick="toggleCompareRow('${escHtml(cap.slug)}')">
        <td class="col-name">${escHtml(cap.name)}</td>
        ${agents.map(agent => {
          const ad = cap.agents.find(a => a.agent === agent.slug);
          if (!ad) return `<td class="col-agent"><div class="cell-available"><span class="cell-dash">—</span></div></td>`;
          const check = ad.available ? `<span class="cell-check">✓</span>` : `<span class="cell-dash">—</span>`;
          const tier = ad.available ? tierBadge(ad.tier) : '';
          const mat  = ad.available ? maturityBadge(ad.maturityLevel) : '';
          const term = ad.available && ad.terminology ? `<span style="font-size:.7rem;color:var(--text-muted)">${escHtml(ad.terminology)}</span>` : '';
          return `<td class="col-agent"><div class="cell-available">${check}${term}${tier}${mat}</div></td>`;
        }).join('')}
      </tr>`;
      if (isExpanded) {
        html += `<tr class="detail-row"><td colspan="${agentColspan}">${expandedCompareHTML(cap, agents)}</td></tr>`;
      }
    });
  });

  html += `</tbody></table>`;
  document.getElementById('compare-table-wrap').innerHTML = html;
}

function toggleCompareRow(slug) {
  state.expandedCompareRow = state.expandedCompareRow === slug ? null : slug;
  renderCompareTable();
}

function expandedCompareHTML(cap, agents) {
  const panels = agents.map(agent => {
    const agentDetail = state.agentDetails[agent.slug];
    if (!agentDetail) return '';
    const fullCap = agentDetail.capabilities.find(c => c.name === cap.name);
    if (!fullCap) return `<div><strong>${escHtml(agent.name)}</strong><p style="color:var(--text-muted);font-size:.8rem;margin-top:.5rem">Not available</p></div>`;
    return `<div>
      <strong style="font-size:.85rem">${escHtml(agent.name)}</strong>
      ${detailPanelHTML(fullCap)}
    </div>`;
  }).join('');
  return `<div style="padding:1rem">${panels}</div>`;
}

// ── Browse tab ───────────────────────────────────────────
async function loadBrowseTab() {
  try {
    if (!state.agentIndex) {
      const agentsData = await fetchJSON(`${API}/agents.json`);
      state.agentIndex = agentsData.agents;
    }
    renderAgentPicker();
  } catch (e) {
    document.getElementById('agent-picker').innerHTML =
      `<div class="empty-state"><p>Failed to load agents.</p></div>`;
  }
}

function renderAgentPicker() {
  const picker = document.getElementById('agent-picker');
  picker.innerHTML = state.agentIndex.map(a => `
    <div class="agent-card${state.selectedAgent === a.slug ? ' selected' : ''}"
      onclick="selectAgent('${a.slug}')">
      <div class="agent-card-name">${escHtml(a.name)}</div>
      <div class="agent-card-vendor">${escHtml(a.vendor)}</div>
      <div class="agent-card-count">${a.totalCapabilities} capabilities</div>
    </div>
  `).join('');
}

async function selectAgent(slug) {
  state.selectedAgent = slug;
  state.expandedBrowseCard = null;
  renderAgentPicker();

  const content = document.getElementById('browse-content');
  if (!state.agentDetails[slug]) {
    content.innerHTML = `<div class="loading">Loading…</div>`;
    try {
      state.agentDetails[slug] = await fetchJSON(`${API}/agents/${slug}.json`);
    } catch (e) {
      content.innerHTML = `<div class="empty-state"><p>Failed to load agent data.</p></div>`;
      return;
    }
  }
  renderBrowseCards(slug);
}

function renderBrowseCards(slug) {
  const data = state.agentDetails[slug];
  if (!data) return;

  const byCategory = {};
  data.capabilities.forEach(c => {
    if (!byCategory[c.category]) byCategory[c.category] = [];
    byCategory[c.category].push(c);
  });

  let html = '';
  Object.entries(byCategory).sort(([a],[b]) => a.localeCompare(b)).forEach(([cat, caps]) => {
    html += `<div class="browse-category">
      <h3 class="browse-category-title">${escHtml(CATEGORY_LABELS[cat] || cat)}</h3>
      <div class="cap-grid">
        ${caps.map(cap => {
          const cardKey = `${slug}::${cap.name}`;
          const isExpanded = state.expandedBrowseCard === cardKey;
          const detail = isExpanded ? `<div class="cap-card-detail">${detailPanelHTML(cap)}</div>` : '';
          return `<div class="cap-card${isExpanded ? ' expanded' : ''}"
            onclick="toggleBrowseCard('${escHtml(slug)}', '${escHtml(cap.name).replace(/'/g,"\\'")}')" >
            <div class="cap-card-header">
              <span class="cap-card-name">${escHtml(cap.name)}</span>
            </div>
            <p class="cap-card-desc">${escHtml(cap.description || '')}</p>
            <div class="cap-card-badges">
              ${tierBadge(cap.tier)}${maturityBadge(cap.maturityLevel)}
            </div>
            ${detail}
          </div>`;
        }).join('')}
      </div>
    </div>`;
  });

  document.getElementById('browse-content').innerHTML = html;
}

function toggleBrowseCard(slug, name) {
  const key = `${slug}::${name}`;
  state.expandedBrowseCard = state.expandedBrowseCard === key ? null : key;
  renderBrowseCards(slug);
}

// ── Boot ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
