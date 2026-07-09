/**
 * Mana Vault — Main Dashboard Application
 * Treats Magic: The Gathering cards like stocks with technical analysis.
 */

import { createChart, CrosshairMode, LineStyle, AreaSeries, LineSeries } from 'lightweight-charts';

// ═══════════════════════════════════
// State
// ═══════════════════════════════════
let portfolio = null;
let cards = [];
let movers = [];
let arbitrage = [];
let events = null;
let alerts = null;
let buylist = [];
let priceHistory = null;  // Lazy loaded
let selectedCard = null;
let priceChart = null;
let rsiChart = null;
let portfolioChart = null;
let currentView = 'portfolio';
let collectionPage = 0;
const PAGE_SIZE = 50;

// Vault state
let currentVaultSlug = null;
let currentVaultMeta = null;
const API_BASE = '/api';

// ═══════════════════════════════════
// Data Loading
// ═══════════════════════════════════
function getDataBase() {
  // If viewing a vault, load from vault data path
  if (currentVaultSlug) return `/vaults/${currentVaultSlug}/data`;
  return '/data';
}

async function loadData() {
  console.time('loadData');
  const base = getDataBase();
  
  const fetches = [
    fetch(`${base}/portfolio.json`).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); }),
    fetch(`${base}/cards.json`).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); }),
    fetch(`${base}/arbitrage.json`).then(r => r.ok ? r.json() : []),
    fetch(`${base}/events.json`).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch(`${base}/alerts.json`).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch(`${base}/buylist_margins.json`).then(r => r.ok ? r.json() : []).catch(() => []),
  ];

  // Movers only exist for default (owner) data
  if (!currentVaultSlug) {
    fetches.push(fetch(`${base}/movers.json`).then(r => r.ok ? r.json() : []));
  }

  const results = await Promise.all(fetches);

  portfolio = results[0];
  cards = results[1];
  arbitrage = results[2];
  events = results[3] || null;
  alerts = results[4] || null;
  buylist = results[5] || [];
  movers = results[6] || [];
  
  // Reset lazy-loaded data
  priceHistory = null;
  
  console.timeEnd('loadData');
  console.log(`Loaded: ${cards.length} cards, ${movers.length} movers, ${arbitrage.length} arbs`);
}

async function loadPriceHistory() {
  if (priceHistory) return priceHistory;
  console.time('loadPriceHistory');
  const base = getDataBase();
  priceHistory = await fetch(`${base}/price_history.json`).then(r => r.json());
  console.timeEnd('loadPriceHistory');
  return priceHistory;
}

// ═══════════════════════════════════
// Utilities
// ═══════════════════════════════════
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function fmt(n, decimals = 2) {
  if (n === null || n === undefined) return '—';
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtPct(n) {
  if (n === null || n === undefined) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function pnlClass(n) {
  if (n === null || n === undefined) return '';
  return n >= 0 ? 'positive' : 'negative';
}

function scryfallImage(id, size = 'small') {
  return `https://api.scryfall.com/cards/${id}?format=image&version=${size}`;
}

function rarityClass(r) {
  return `rarity-${r}`;
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// ═══════════════════════════════════
// Navigation
// ═══════════════════════════════════
function initNav() {
  $$('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      switchView(view);
    });
  });
}

function switchView(view) {
  currentView = view;
  $$('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  $$('.view').forEach(v => v.classList.toggle('active', v.id === `view-${view}`));
  
  // Lazy init views
  if (view === 'chart' && !priceChart) initChartView();
  if (view === 'movers') renderMovers();
  if (view === 'signals') renderSignals();
  if (view === 'arbitrage') renderArbitrage();
  if (view === 'collection') renderCollection();
  if (view === 'events') renderEvents();
  if (view === 'alerts') renderAlerts();
  if (view === 'buylist') renderBuylist();
  if (view === 'gallery') renderGallery();
}

// ═══════════════════════════════════
// Portfolio View
// ═══════════════════════════════════
function renderPortfolio() {
  if (!portfolio) return;
  
  // Header stats
  $('#header-total').textContent = fmt(portfolio.total_current, 0);
  const pnlEl = $('#header-pnl-value');
  pnlEl.textContent = `${fmt(portfolio.total_pnl, 0)} (${fmtPct(portfolio.total_pnl_pct)})`;
  pnlEl.className = `stat-value ${pnlClass(portfolio.total_pnl)}`;
  
  // KPIs
  const setKPI = (id, value, sub) => {
    const el = $(`#${id}`);
    el.querySelector('.kpi-value').textContent = value;
    if (sub) el.querySelector('.kpi-sub').textContent = sub;
  };
  
  setKPI('kpi-current', fmt(portfolio.total_current, 0), 'TCGPlayer Retail');
  setKPI('kpi-purchase', fmt(portfolio.total_purchase, 0), 'Purchase Price');
  
  const pnlKpi = $('#kpi-pnl');
  pnlKpi.querySelector('.kpi-value').textContent = fmt(portfolio.total_pnl, 0);
  pnlKpi.querySelector('.kpi-value').className = `kpi-value ${pnlClass(portfolio.total_pnl)}`;
  pnlKpi.querySelector('.kpi-sub').textContent = fmtPct(portfolio.total_pnl_pct);
  pnlKpi.querySelector('.kpi-sub').className = `kpi-sub ${pnlClass(portfolio.total_pnl)}`;
  
  setKPI('kpi-cards', portfolio.card_count.toLocaleString(), `${portfolio.unique_cards.toLocaleString()} unique`);
  
  // Portfolio chart
  renderPortfolioChart();
  
  // Top gainers/losers
  renderTopMovers();
  
  // Binder breakdown
  renderBinderBreakdown();
  
  // Rarity breakdown
  renderRarityBreakdown();
}

function renderPortfolioChart() {
  const container = $('#portfolio-chart');
  container.innerHTML = '';
  
  if (portfolioChart) {
    portfolioChart.remove();
    portfolioChart = null;
  }
  
  portfolioChart = createChart(container, {
    width: container.clientWidth,
    height: 320,
    layout: {
      background: { color: 'transparent' },
      textColor: '#8b95b0',
      fontFamily: "'Inter', sans-serif",
    },
    grid: {
      vertLines: { color: 'rgba(255,255,255,0.03)' },
      horzLines: { color: 'rgba(255,255,255,0.03)' },
    },
    crosshair: {
      mode: CrosshairMode.Magnet,
      vertLine: { color: 'rgba(124,92,252,0.3)', labelBackgroundColor: '#7c5cfc' },
      horzLine: { color: 'rgba(124,92,252,0.3)', labelBackgroundColor: '#7c5cfc' },
    },
    rightPriceScale: {
      borderColor: 'rgba(255,255,255,0.06)',
    },
    timeScale: {
      borderColor: 'rgba(255,255,255,0.06)',
      timeVisible: false,
    },
  });
  
  const values = portfolio.portfolio_values;
  const dates = Object.keys(values).sort();
  
  const data = dates.map(d => ({
    time: d,
    value: typeof values[d] === 'object' ? values[d] : values[d],
  }));
  
  // Area series for portfolio value
  const areaSeries = portfolioChart.addSeries(AreaSeries, {
    lineColor: '#a855f7',
    topColor: 'rgba(168, 85, 247, 0.3)',
    bottomColor: 'rgba(168, 85, 247, 0.02)',
    lineWidth: 2,
    priceFormat: { type: 'custom', formatter: v => '$' + Math.round(v).toLocaleString() },
  });
  
  areaSeries.setData(data);
  
  // Purchase price reference line
  const costLine = portfolioChart.addSeries(LineSeries, {
    color: '#00d4ff',
    lineWidth: 1,
    lineStyle: LineStyle.Dashed,
    priceFormat: { type: 'custom', formatter: v => '$' + Math.round(v).toLocaleString() },
  });
  
  costLine.setData(data.map(d => ({ time: d.time, value: portfolio.total_purchase })));
  
  portfolioChart.timeScale().fitContent();
  
  // Responsive resize
  new ResizeObserver(() => {
    portfolioChart.applyOptions({ width: container.clientWidth });
  }).observe(container);
}

function renderTopMovers() {
  const withChanges = cards.filter(c => c.change_30d !== null && c.current_price !== null);
  
  const gainers = [...withChanges].sort((a, b) => (b.change_30d || 0) - (a.change_30d || 0)).slice(0, 15);
  const losers = [...withChanges].sort((a, b) => (a.change_30d || 0) - (b.change_30d || 0)).slice(0, 15);
  
  const renderList = (items, containerId) => {
    const container = $(containerId);
    container.innerHTML = items.map((c, i) => `
      <div class="card-list-item" data-scryfall="${c.scryfall_id}">
        <span class="card-rank">${i + 1}</span>
        <img class="card-thumb" src="${scryfallImage(c.scryfall_id)}" alt="" loading="lazy" />
        <div class="card-list-info">
          <div class="card-list-name">${c.name}</div>
          <div class="card-list-set">${c.set_code} · ${c.foil} · x${c.quantity}</div>
        </div>
        <div class="card-list-price">
          <div class="card-list-current">${fmt(c.current_price)}</div>
          <div class="card-list-change ${pnlClass(c.change_30d)}">${fmtPct(c.change_30d)}</div>
        </div>
      </div>
    `).join('');
    
    container.querySelectorAll('.card-list-item').forEach(el => {
      el.addEventListener('click', () => {
        switchView('chart');
        selectCard(el.dataset.scryfall);
      });
    });
  };
  
  renderList(gainers, '#top-gainers');
  renderList(losers, '#top-losers');
}

function renderBinderBreakdown() {
  const binders = portfolio.binder_summary;
  const sorted = Object.entries(binders).sort((a, b) => b[1].current - a[1].current);
  const maxVal = sorted[0]?.[1].current || 1;
  
  const container = $('#binder-breakdown');
  container.innerHTML = sorted.slice(0, 15).map(([name, data]) => `
    <div class="breakdown-item">
      <span class="breakdown-name" title="${name}">${name}</span>
      <div class="breakdown-bar">
        <div class="breakdown-fill" style="width: ${(data.current / maxVal * 100).toFixed(1)}%"></div>
      </div>
      <span class="breakdown-value">${fmt(data.current, 0)}</span>
    </div>
  `).join('');
}

function renderRarityBreakdown() {
  const rarities = portfolio.rarity_summary;
  const order = ['mythic', 'rare', 'uncommon', 'common', 'special'];
  const maxVal = Math.max(...Object.values(rarities).map(r => r.value));
  
  const container = $('#rarity-breakdown');
  container.innerHTML = order
    .filter(r => rarities[r])
    .map(r => {
      const data = rarities[r];
      const colors = { mythic: '#e65100', rare: '#ffd740', uncommon: '#b0bec5', common: '#546e7a', special: '#7c5cfc' };
      return `
        <div class="breakdown-item">
          <span class="breakdown-name ${rarityClass(r)}">${r.charAt(0).toUpperCase() + r.slice(1)} (${data.count})</span>
          <div class="breakdown-bar">
            <div class="breakdown-fill" style="width: ${(data.value / maxVal * 100).toFixed(1)}%; background: ${colors[r] || '#7c5cfc'}"></div>
          </div>
          <span class="breakdown-value">${fmt(data.value, 0)}</span>
        </div>
      `;
    }).join('');
}

// ═══════════════════════════════════
// Price Chart View
// ═══════════════════════════════════
let chartSeries = {};

function initChartView() {
  initCardSearch();
  initChartToolbar();
  
  // Auto-select top card
  const topCard = cards
    .filter(c => c.current_price !== null)
    .sort((a, b) => (b.current_price || 0) * b.quantity - (a.current_price || 0) * a.quantity)[0];
  
  if (topCard) selectCard(topCard.scryfall_id);
}

function initCardSearch() {
  const input = $('#card-search');
  const results = $('#search-results');
  
  input.addEventListener('input', debounce(() => {
    const query = input.value.toLowerCase().trim();
    if (query.length < 2) {
      results.classList.remove('open');
      return;
    }
    
    const matches = cards
      .filter(c => c.name.toLowerCase().includes(query))
      .filter((c, i, arr) => arr.findIndex(x => x.scryfall_id === c.scryfall_id) === i)
      .sort((a, b) => (b.current_price || 0) - (a.current_price || 0))
      .slice(0, 20);
    
    results.innerHTML = matches.map(c => `
      <div class="search-result-item" data-scryfall="${c.scryfall_id}">
        <span class="search-result-name">${c.name}</span>
        <span class="search-result-meta">${c.set_code} · ${fmt(c.current_price)}</span>
      </div>
    `).join('');
    
    results.classList.add('open');
    
    results.querySelectorAll('.search-result-item').forEach(el => {
      el.addEventListener('click', () => {
        selectCard(el.dataset.scryfall);
        results.classList.remove('open');
        input.value = '';
      });
    });
  }, 200));
  
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-box')) results.classList.remove('open');
  });
}

function initChartToolbar() {
  // Indicator toggles
  ['ema8', 'ema21', 'sma50', 'bb', 'cost'].forEach(id => {
    $(`#toggle-${id}`).addEventListener('change', () => updateChartIndicators());
  });
  
  // Vendor toggles
  $$('.vendor-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.vendor-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (selectedCard) renderPriceChart(selectedCard);
    });
  });
}

async function selectCard(scryfallId) {
  selectedCard = scryfallId;
  const card = cards.find(c => c.scryfall_id === scryfallId);
  if (!card) return;
  
  // Update card info panel
  const img = $('#card-image');
  img.src = scryfallImage(scryfallId, 'normal');
  img.alt = card.name;
  
  const details = $('#card-details');
  details.innerHTML = `
    <div class="detail-row">
      <span class="detail-label">Card</span>
      <span class="detail-value">${card.name}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Set</span>
      <span class="detail-value">${card.set_name} (${card.set_code})</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Finish</span>
      <span class="detail-value">${card.foil}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Rarity</span>
      <span class="detail-value ${rarityClass(card.rarity)}">${card.rarity}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Quantity</span>
      <span class="detail-value">${card.quantity}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Purchase</span>
      <span class="detail-value">${fmt(card.purchase_price)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Current</span>
      <span class="detail-value">${fmt(card.current_price)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">P&L</span>
      <span class="detail-value ${pnlClass(card.pnl)}">${fmt(card.pnl)} (${fmtPct(card.pnl_pct)})</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">7d Change</span>
      <span class="detail-value ${pnlClass(card.change_7d)}">${fmtPct(card.change_7d)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">30d Change</span>
      <span class="detail-value ${pnlClass(card.change_30d)}">${fmtPct(card.change_30d)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Binder</span>
      <span class="detail-value">${card.binder}</span>
    </div>
  `;
  
  await renderPriceChart(scryfallId);
}

async function renderPriceChart(scryfallId) {
  const history = await loadPriceHistory();
  const cardData = history[scryfallId];
  if (!cardData) return;
  
  const card = cards.find(c => c.scryfall_id === scryfallId);
  const container = $('#price-chart');
  const rsiContainer = $('#rsi-chart');
  
  // Destroy existing charts
  if (priceChart) { priceChart.remove(); priceChart = null; }
  if (rsiChart) { rsiChart.remove(); rsiChart = null; }
  
  chartSeries = {};
  
  // Create main price chart
  priceChart = createChart(container, {
    width: container.clientWidth,
    height: 420,
    layout: {
      background: { color: 'transparent' },
      textColor: '#8b95b0',
      fontFamily: "'Inter', sans-serif",
    },
    grid: {
      vertLines: { color: 'rgba(255,255,255,0.03)' },
      horzLines: { color: 'rgba(255,255,255,0.03)' },
    },
    crosshair: {
      mode: CrosshairMode.Magnet,
      vertLine: { color: 'rgba(124,92,252,0.3)', labelBackgroundColor: '#7c5cfc' },
      horzLine: { color: 'rgba(124,92,252,0.3)', labelBackgroundColor: '#7c5cfc' },
    },
    rightPriceScale: { borderColor: 'rgba(255,255,255,0.06)' },
    timeScale: { borderColor: 'rgba(255,255,255,0.06)', timeVisible: false },
  });
  
  // Price data
  const priceData = cardData.history.map(h => ({ time: h.date, value: h.price }));
  
  // Main price line — use LineSeries for clean look
  const priceSeries = priceChart.addSeries(LineSeries, {
    color: '#00d4ff',
    lineWidth: 2,
    priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    lastValueVisible: true,
    priceLineVisible: false,
  });
  priceSeries.setData(priceData);
  chartSeries.price = priceSeries;
  
  // Technical indicators
  const tech = cardData.technicals;
  if (tech && tech.dates) {
    addIndicatorSeries(tech, priceData);
  }
  
  // Cost basis — use priceLine marker so it doesn't affect Y-axis scale
  if (card && card.purchase_price > 0) {
    const costLine = priceSeries.createPriceLine({
      price: card.purchase_price,
      color: '#ff9800',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: 'Cost Basis',
      axisLabelColor: '#ff9800',
      axisLabelTextColor: '#000',
    });
    chartSeries.costLine = costLine;
  }
  
  priceChart.timeScale().fitContent();
  
  // RSI chart
  if (tech && tech.rsi_14) {
    rsiChart = createChart(rsiContainer, {
      width: rsiContainer.clientWidth,
      height: 140,
      layout: {
        background: { color: 'transparent' },
        textColor: '#8b95b0',
        fontFamily: "'Inter', sans-serif",
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.03)' },
        horzLines: { color: 'rgba(255,255,255,0.03)' },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.06)' },
      timeScale: { borderColor: 'rgba(255,255,255,0.06)', timeVisible: false, visible: false },
    });
    
    const rsiSeries = rsiChart.addSeries(LineSeries, {
      color: '#f0b400',
      lineWidth: 2,
      priceFormat: { type: 'custom', formatter: v => v.toFixed(0) },
    });
    
    const rsiData = tech.dates
      .map((d, i) => tech.rsi_14[i] !== null ? { time: d, value: tech.rsi_14[i] } : null)
      .filter(Boolean);
    
    rsiSeries.setData(rsiData);
    
    // Overbought/oversold lines
    const ob = rsiChart.addSeries(LineSeries, { color: 'rgba(229,57,53,0.4)', lineWidth: 1, lineStyle: LineStyle.Dashed });
    const os = rsiChart.addSeries(LineSeries, { color: 'rgba(0,255,136,0.4)', lineWidth: 1, lineStyle: LineStyle.Dashed });
    ob.setData(rsiData.map(d => ({ time: d.time, value: 70 })));
    os.setData(rsiData.map(d => ({ time: d.time, value: 30 })));
    
    rsiChart.timeScale().fitContent();
    
    // Sync crosshair between charts
    priceChart.subscribeCrosshairMove((param) => {
      if (param.time) rsiChart.timeScale().scrollToPosition(
        priceChart.timeScale().scrollPosition(), false
      );
    });
  }
  
  // Signals
  renderChartSignals(tech);
  
  // Responsive
  new ResizeObserver(() => {
    if (priceChart) priceChart.applyOptions({ width: container.clientWidth });
    if (rsiChart) rsiChart.applyOptions({ width: rsiContainer.clientWidth });
  }).observe(container);
}

function addIndicatorSeries(tech, priceData) {
  if (!tech.dates) return;
  
  const makeData = (arr) => tech.dates
    .map((d, i) => arr[i] !== null ? { time: d, value: arr[i] } : null)
    .filter(Boolean);
  
  // EMA 8
  if (tech.ema_8) {
    const s = priceChart.addSeries(LineSeries, { color: '#00ff88', lineWidth: 1, title: 'EMA 8' });
    s.setData(makeData(tech.ema_8));
    chartSeries.ema8 = s;
    if (!$('#toggle-ema8').checked) s.applyOptions({ visible: false });
  }
  
  // EMA 21
  if (tech.ema_21) {
    const s = priceChart.addSeries(LineSeries, { color: '#f0b400', lineWidth: 1, title: 'EMA 21' });
    s.setData(makeData(tech.ema_21));
    chartSeries.ema21 = s;
    if (!$('#toggle-ema21').checked) s.applyOptions({ visible: false });
  }
  
  // SMA 50
  if (tech.sma_50) {
    const s = priceChart.addSeries(LineSeries, { color: '#ff6b6b', lineWidth: 1, title: 'SMA 50' });
    s.setData(makeData(tech.sma_50));
    chartSeries.sma50 = s;
    if (!$('#toggle-sma50').checked) s.applyOptions({ visible: false });
  }
  
  // Bollinger Bands
  if (tech.bb_upper && tech.bb_lower) {
    const upper = priceChart.addSeries(LineSeries, {
      color: 'rgba(168, 85, 247, 0.5)',
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
    });
    const lower = priceChart.addSeries(LineSeries, {
      color: 'rgba(168, 85, 247, 0.5)',
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
    });
    upper.setData(makeData(tech.bb_upper));
    lower.setData(makeData(tech.bb_lower));
    chartSeries.bbUpper = upper;
    chartSeries.bbLower = lower;
    
    if (!$('#toggle-bb').checked) {
      upper.applyOptions({ visible: false });
      lower.applyOptions({ visible: false });
    }
  }
}

function updateChartIndicators() {
  const toggles = {
    ema8: $('#toggle-ema8').checked,
    ema21: $('#toggle-ema21').checked,
    sma50: $('#toggle-sma50').checked,
    bb: $('#toggle-bb').checked,
  };
  
  if (chartSeries.ema8) chartSeries.ema8.applyOptions({ visible: toggles.ema8 });
  if (chartSeries.ema21) chartSeries.ema21.applyOptions({ visible: toggles.ema21 });
  if (chartSeries.sma50) chartSeries.sma50.applyOptions({ visible: toggles.sma50 });
  if (chartSeries.bbUpper) chartSeries.bbUpper.applyOptions({ visible: toggles.bb });
  if (chartSeries.bbLower) chartSeries.bbLower.applyOptions({ visible: toggles.bb });
}

function renderChartSignals(tech) {
  const container = $('#chart-signals');
  if (!tech || !tech.signals || tech.signals.length === 0) {
    container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 8px;">No technical signals detected for this card.</div>';
    return;
  }
  
  // Show last 10 signals
  const recent = tech.signals.slice(-10);
  container.innerHTML = recent.map(s => {
    const type = s.type.includes('bullish') || s.type.includes('oversold') || s.type.includes('bb_lower') ? 'bullish' :
                 s.type.includes('bearish') || s.type.includes('overbought') || s.type.includes('bb_upper') ? 'bearish' : 'neutral';
    return `<span class="signal-badge ${type}">${s.date}: ${s.label}</span>`;
  }).join('');
}

// ═══════════════════════════════════
// MTGStocks Movers View
// ═══════════════════════════════════
function renderMovers() {
  // Populate date filter
  const dates = [...new Set(movers.map(m => m.date))].sort().reverse();
  const dateFilter = $('#movers-date-filter');
  if (dateFilter.options.length <= 1) {
    dates.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d;
      opt.textContent = d;
      dateFilter.appendChild(opt);
    });
  }
  
  const applyFilters = () => {
    const dateVal = dateFilter.value;
    const typeVal = $('#movers-type-filter').value;
    const collOnly = $('#movers-collection-only').checked;
    
    let filtered = movers;
    if (dateVal !== 'all') filtered = filtered.filter(m => m.date === dateVal);
    if (typeVal !== 'all') filtered = filtered.filter(m => m.price_type === typeVal);
    if (collOnly) filtered = filtered.filter(m => m.in_collection);
    
    const tbody = $('#movers-tbody');
    tbody.innerHTML = filtered.map(m => `
      <tr class="${m.in_collection ? 'in-collection' : ''}">
        <td>${m.date}</td>
        <td><strong>${m.name}</strong></td>
        <td>${m.set_code}</td>
        <td style="font-family: var(--font-mono)">${fmt(m.price)}</td>
        <td class="${pnlClass(m.pct_change)}" style="font-family: var(--font-mono); font-weight: 600">${fmtPct(m.pct_change)}</td>
        <td>${m.price_type}</td>
        <td>${m.in_collection ? 
          `<span class="highlight">✓ ${m.collection_matches.length > 0 ? m.collection_matches[0].binder : ''}</span>` : 
          '—'}</td>
      </tr>
    `).join('');
  };
  
  dateFilter.addEventListener('change', applyFilters);
  $('#movers-type-filter').addEventListener('change', applyFilters);
  $('#movers-collection-only').addEventListener('change', applyFilters);
  
  applyFilters();
}

// ═══════════════════════════════════
// Signals View
// ═══════════════════════════════════
async function renderSignals() {
  const history = await loadPriceHistory();
  
  let bullishSignals = [];
  let bearishSignals = [];
  let totalBullish = 0;
  let totalBearish = 0;
  let overboughtCount = 0;
  let oversoldCount = 0;
  
  for (const card of cards) {
    const detail = history[card.scryfall_id];
    if (!detail || !detail.technicals || !detail.technicals.signals) continue;
    
    const signals = detail.technicals.signals;
    const lastSignal = signals[signals.length - 1];
    if (!lastSignal) continue;
    
    // Count recent signals (last 7 days)
    const recentDate = detail.technicals.dates?.[detail.technicals.dates.length - 7] || '2026-03-03';
    const recentSignals = signals.filter(s => s.date >= recentDate);
    
    for (const s of recentSignals) {
      const entry = {
        name: card.name,
        scryfall_id: card.scryfall_id,
        set_code: card.set_code,
        current_price: card.current_price,
        signal: s,
        binder: card.binder,
      };
      
      if (s.type.includes('bullish') || s.type.includes('oversold') || s.type === 'bb_lower_break') {
        bullishSignals.push(entry);
        totalBullish++;
        if (s.type === 'oversold') oversoldCount++;
      } else {
        bearishSignals.push(entry);
        totalBearish++;
        if (s.type === 'overbought') overboughtCount++;
      }
    }
  }
  
  // Deduplicate by card (keep latest signal)
  const dedup = (arr) => {
    const seen = new Map();
    for (const item of arr) {
      const existing = seen.get(item.scryfall_id);
      if (!existing || item.signal.date > existing.signal.date) {
        seen.set(item.scryfall_id, item);
      }
    }
    return [...seen.values()].sort((a, b) => b.signal.date.localeCompare(a.signal.date));
  };
  
  bullishSignals = dedup(bullishSignals);
  bearishSignals = dedup(bearishSignals);
  
  // Summary
  $('#signals-summary').innerHTML = `
    <div class="signal-stat">
      <div class="signal-stat-num positive">${bullishSignals.length}</div>
      <div class="signal-stat-label">Bullish Signals</div>
    </div>
    <div class="signal-stat">
      <div class="signal-stat-num negative">${bearishSignals.length}</div>
      <div class="signal-stat-label">Bearish / Overbought</div>
    </div>
    <div class="signal-stat">
      <div class="signal-stat-num" style="color: var(--gold)">${overboughtCount}</div>
      <div class="signal-stat-label">RSI Overbought (>70)</div>
    </div>
    <div class="signal-stat">
      <div class="signal-stat-num" style="color: var(--blue)">${oversoldCount}</div>
      <div class="signal-stat-label">RSI Oversold (<30)</div>
    </div>
  `;
  
  const renderSignalList = (items, containerId) => {
    const container = $(containerId);
    container.innerHTML = items.slice(0, 30).map(item => `
      <div class="signal-card-item" data-scryfall="${item.scryfall_id}">
        <img class="signal-card-thumb" src="${scryfallImage(item.scryfall_id)}" alt="" loading="lazy" />
        <div class="signal-card-info">
          <div class="signal-card-name">${item.name}</div>
          <div class="signal-card-signal">${item.signal.date}: ${item.signal.label}</div>
        </div>
        <div class="signal-card-price ${pnlClass(item.current_price - (item.purchase_price || 0))}">
          ${fmt(item.current_price)}
        </div>
      </div>
    `).join('');
    
    container.querySelectorAll('.signal-card-item').forEach(el => {
      el.addEventListener('click', () => {
        switchView('chart');
        selectCard(el.dataset.scryfall);
      });
    });
  };
  
  renderSignalList(bullishSignals, '#bullish-signals');
  renderSignalList(bearishSignals, '#bearish-signals');

  renderSellQueue(history);
  renderBuyQueue(history);
}

// ═══════════════════════════════════
// Sell Queue (within Signals view)
// ═══════════════════════════════════
const SELL_SIGNAL_TYPES = new Set(['bearish_cross', 'overbought', 'bb_upper_break']);

function renderSellQueue(history) {
  const container = $('#sell-queue');
  if (!container) return;

  const emptyState = (msg) =>
    `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 16px;">${msg}</div>`;

  if (!Array.isArray(cards) || cards.length === 0) {
    container.innerHTML = emptyState('No holdings — import a collection to build a sell queue.');
    return;
  }

  const rows = [];
  for (const card of cards) {
    if (!card.quantity || card.quantity <= 0) continue;
    const detail = history && history[card.scryfall_id];
    const signals = detail?.technicals?.signals;
    if (!Array.isArray(signals) || signals.length === 0) continue;

    // Latest signal only
    const latest = signals[signals.length - 1];
    if (!latest || !SELL_SIGNAL_TYPES.has(latest.type)) continue;

    const impact = (card.pnl || 0) * (card.quantity || 0);
    rows.push({
      name: card.name,
      scryfall_id: card.scryfall_id,
      current_price: card.current_price,
      quantity: card.quantity,
      signal: latest,
      impact,
    });
  }

  if (rows.length === 0) {
    container.innerHTML = emptyState('No owned cards with a bearish latest signal. Nothing to trim right now.');
    return;
  }

  rows.sort((a, b) => b.impact - a.impact);

  container.innerHTML = rows.slice(0, 30).map(r => `
    <div class="signal-card-item" data-scryfall="${r.scryfall_id}">
      <img class="signal-card-thumb" src="${scryfallImage(r.scryfall_id)}" alt="" loading="lazy" />
      <div class="signal-card-info">
        <div class="signal-card-name"><strong>${r.name}</strong> <span class="signal-badge bearish">${r.signal.label}</span></div>
        <div class="signal-card-signal">x${r.quantity} · <a href="https://scryfall.com/card/${r.scryfall_id}" target="_blank" rel="noopener">Scryfall</a></div>
      </div>
      <div class="signal-card-price ${pnlClass(r.impact)}">${fmt(r.impact)}</div>
    </div>
  `).join('');

  container.querySelectorAll('.signal-card-item').forEach(el => {
    el.addEventListener('click', (e) => {
      if (e.target.closest('a')) return;
      switchView('chart');
      selectCard(el.dataset.scryfall);
    });
  });
}

// ═══════════════════════════════════
// Buy Queue (within Signals view)
// ═══════════════════════════════════
const BUY_SIGNAL_TYPES = new Set(['bullish_cross', 'oversold', 'bb_lower_break']);

function renderBuyQueue(history) {
  const container = $('#buy-queue');
  if (!container) return;

  const emptyState = (msg) =>
    `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 16px;">${msg}</div>`;

  if (!Array.isArray(cards) || cards.length === 0) {
    container.innerHTML = emptyState('No holdings — import a collection to build a buy queue.');
    return;
  }

  const rows = [];
  for (const card of cards) {
    if (!card.quantity || card.quantity <= 0) continue;
    const detail = history && history[card.scryfall_id];
    const signals = detail?.technicals?.signals;
    if (!Array.isArray(signals) || signals.length === 0) continue;

    // Latest signal only
    const latest = signals[signals.length - 1];
    if (!latest || !BUY_SIGNAL_TYPES.has(latest.type)) continue;

    const conviction = (card.current_price || 0) * (card.quantity || 0);
    rows.push({
      name: card.name,
      scryfall_id: card.scryfall_id,
      current_price: card.current_price,
      quantity: card.quantity,
      signal: latest,
      conviction,
    });
  }

  if (rows.length === 0) {
    container.innerHTML = emptyState('No owned cards with a bullish latest signal. Nothing to add right now.');
    return;
  }

  rows.sort((a, b) => b.conviction - a.conviction);

  container.innerHTML = rows.slice(0, 30).map(r => `
    <div class="signal-card-item" data-scryfall="${r.scryfall_id}">
      <img class="signal-card-thumb" src="${scryfallImage(r.scryfall_id)}" alt="" loading="lazy" />
      <div class="signal-card-info">
        <div class="signal-card-name"><strong>${r.name}</strong> <span class="signal-badge bullish">${r.signal.label}</span></div>
        <div class="signal-card-signal">x${r.quantity} · <a href="https://scryfall.com/card/${r.scryfall_id}" target="_blank" rel="noopener">Scryfall</a></div>
      </div>
      <div class="signal-card-price positive">${fmt(r.conviction)}</div>
    </div>
  `).join('');

  container.querySelectorAll('.signal-card-item').forEach(el => {
    el.addEventListener('click', (e) => {
      if (e.target.closest('a')) return;
      switchView('chart');
      selectCard(el.dataset.scryfall);
    });
  });
}

// ═══════════════════════════════════
// Arbitrage View
// ═══════════════════════════════════
function renderArbitrage() {
  const tbody = $('#arbitrage-tbody');
  tbody.innerHTML = arbitrage.map(a => `
    <tr>
      <td><strong>${a.name}</strong></td>
      <td>${a.set_code}</td>
      <td style="font-family: var(--font-mono)">${fmt(a.tcg_retail)}</td>
      <td style="font-family: var(--font-mono)">${fmt(a.ck_retail)}</td>
      <td style="font-family: var(--font-mono)">${a.ck_buylist ? fmt(a.ck_buylist) : '—'}</td>
      <td style="font-family: var(--font-mono)">${a.cm_retail ? fmt(a.cm_retail) : '—'}</td>
      <td class="${a.spread_pct > 30 ? 'positive' : ''}" style="font-family: var(--font-mono); font-weight: 600">${a.spread_pct}%</td>
      <td>${a.cheaper_vendor}</td>
      <td style="font-size: 0.75rem; color: var(--text-muted)">${a.binder}</td>
    </tr>
  `).join('');
}

// ═══════════════════════════════════
// Collection View
// ═══════════════════════════════════
function renderCollection() {
  // Populate binder filter
  const binderFilter = $('#collection-binder-filter');
  if (binderFilter.options.length <= 1) {
    const binders = [...new Set(cards.map(c => c.binder))].sort();
    binders.forEach(b => {
      const opt = document.createElement('option');
      opt.value = b;
      opt.textContent = b;
      binderFilter.appendChild(opt);
    });
  }
  
  const applyFilters = () => {
    let filtered = [...cards];
    
    const search = $('#collection-search').value.toLowerCase().trim();
    const binder = binderFilter.value;
    const rarity = $('#collection-rarity-filter').value;
    const sort = $('#collection-sort').value;
    
    if (search) filtered = filtered.filter(c => c.name.toLowerCase().includes(search));
    if (binder !== 'all') filtered = filtered.filter(c => c.binder === binder);
    if (rarity !== 'all') filtered = filtered.filter(c => c.rarity === rarity);
    
    // Sort
    const sortFns = {
      pnl_desc: (a, b) => (b.pnl || 0) - (a.pnl || 0),
      pnl_asc: (a, b) => (a.pnl || 0) - (b.pnl || 0),
      current_desc: (a, b) => (b.current_price || 0) - (a.current_price || 0),
      current_asc: (a, b) => (a.current_price || 0) - (b.current_price || 0),
      change_7d_desc: (a, b) => (b.change_7d || 0) - (a.change_7d || 0),
      name_asc: (a, b) => a.name.localeCompare(b.name),
    };
    filtered.sort(sortFns[sort] || sortFns.pnl_desc);
    
    // Paginate
    const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
    if (collectionPage >= totalPages) collectionPage = 0;
    const page = filtered.slice(collectionPage * PAGE_SIZE, (collectionPage + 1) * PAGE_SIZE);
    
    const tbody = $('#collection-tbody');
    tbody.innerHTML = page.map(c => `
      <tr data-scryfall="${c.scryfall_id}" style="cursor: pointer">
        <td><strong>${c.name}</strong></td>
        <td>${c.set_code}</td>
        <td>${c.foil}</td>
        <td>${c.quantity}</td>
        <td style="font-family: var(--font-mono)">${fmt(c.purchase_price)}</td>
        <td style="font-family: var(--font-mono)">${fmt(c.current_price)}</td>
        <td class="${pnlClass(c.pnl)}" style="font-family: var(--font-mono); font-weight: 600">${fmt(c.pnl)}</td>
        <td class="${pnlClass(c.change_7d)}" style="font-family: var(--font-mono)">${fmtPct(c.change_7d)}</td>
        <td class="${pnlClass(c.change_30d)}" style="font-family: var(--font-mono)">${fmtPct(c.change_30d)}</td>
        <td style="font-size: 0.75rem; color: var(--text-muted)">${c.binder}</td>
      </tr>
    `).join('');
    
    tbody.querySelectorAll('tr').forEach(tr => {
      tr.addEventListener('click', () => {
        switchView('chart');
        selectCard(tr.dataset.scryfall);
      });
    });
    
    // Pagination buttons
    const pagDiv = $('#collection-pagination');
    if (totalPages > 1) {
      let buttons = '';
      if (collectionPage > 0) buttons += `<button data-page="${collectionPage - 1}">←</button>`;
      
      for (let i = 0; i < totalPages && i < 10; i++) {
        buttons += `<button data-page="${i}" class="${i === collectionPage ? 'active' : ''}">${i + 1}</button>`;
      }
      if (totalPages > 10) buttons += `<button disabled>...</button>`;
      
      if (collectionPage < totalPages - 1) buttons += `<button data-page="${collectionPage + 1}">→</button>`;
      
      pagDiv.innerHTML = `<span style="color: var(--text-muted); font-size: 0.8rem; margin-right: 8px">${filtered.length} cards</span>` + buttons;
      pagDiv.querySelectorAll('button[data-page]').forEach(btn => {
        btn.addEventListener('click', () => {
          collectionPage = parseInt(btn.dataset.page);
          applyFilters();
        });
      });
    } else {
      pagDiv.innerHTML = `<span style="color: var(--text-muted); font-size: 0.8rem">${filtered.length} cards</span>`;
    }
  };
  
  $('#collection-search').addEventListener('input', debounce(applyFilters, 200));
  binderFilter.addEventListener('change', applyFilters);
  $('#collection-rarity-filter').addEventListener('change', applyFilters);
  $('#collection-sort').addEventListener('change', applyFilters);
  
  applyFilters();
}

// ═══════════════════════════════════
// Events View
// ═══════════════════════════════════
function eventTypeBadge(type) {
  const label = (type || 'event').replace(/_/g, ' ');
  return `<span class="event-badge">${label}</span>`;
}

function renderEvents() {
  const emptyState = (msg) =>
    `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 16px;">${msg}</div>`;

  // Upcoming
  const upcomingEl = $('#events-upcoming');
  const upcoming = (events && Array.isArray(events.upcoming)) ? events.upcoming : [];
  if (upcoming.length === 0) {
    upcomingEl.innerHTML = emptyState('No upcoming events — run scrape_events.py after a data refresh.');
  } else {
    upcomingEl.innerHTML = upcoming.map(e => {
      const name = e.name || 'Untitled event';
      const dates = e.dates || '';
      const location = e.location || '';
      const url = e.url || '';
      const nameHtml = url
        ? `<a href="${url}" target="_blank" rel="noopener" class="event-name-link">${name}</a>`
        : `<span class="event-name-link">${name}</span>`;
      const meta = [dates, location].filter(Boolean).join(' · ');
      return `
        <div class="event-card">
          <div class="event-card-top">
            ${eventTypeBadge(e.type)}
            ${dates ? `<span class="event-date">${dates}</span>` : ''}
          </div>
          <div class="event-card-name">${nameHtml}</div>
          ${meta ? `<div class="event-card-meta">${meta}</div>` : ''}
        </div>
      `;
    }).join('');
  }

  // Recent tournament results
  const recentEl = $('#events-recent');
  const recent = (events && Array.isArray(events.recent_events)) ? events.recent_events : [];
  if (recent.length === 0) {
    recentEl.innerHTML = emptyState('No recent tournament results available.');
  } else {
    recentEl.innerHTML = recent.map(e => {
      const name = e.name || 'Event';
      const fmt = e.format || '';
      const url = e.url || '';
      const nameHtml = url
        ? `<a href="${url}" target="_blank" rel="noopener">${name}</a>`
        : name;
      return `
        <div class="events-recent-item">
          <div class="events-recent-name">${nameHtml}</div>
          ${fmt ? `<span class="events-recent-fmt">${fmt}</span>` : ''}
        </div>
      `;
    }).join('');
  }

  // Metagame snapshot
  const metaEl = $('#events-metagame');
  const meta = (events && events.metagame && typeof events.metagame === 'object') ? events.metagame : {};
  const formats = Object.keys(meta);
  if (formats.length === 0) {
    metaEl.innerHTML = emptyState('No metagame data available.');
  } else {
    metaEl.innerHTML = formats.map(fmtName => {
      const archs = Array.isArray(meta[fmtName]) ? meta[fmtName] : [];
      const chips = archs.map(a => {
        const aname = a.name || 'Archetype';
        const owned = a.in_collection === true;
        const url = a.url || '';
        const inner = url
          ? `<a href="${url}" target="_blank" rel="noopener">${aname}</a>`
          : aname;
        return `<span class="meta-chip${owned ? ' owned' : ''}">${inner}${owned ? ' <span class="meta-own-tag">owned</span>' : ''}</span>`;
      }).join('');
      return `
        <div class="meta-format">
          <div class="meta-format-name">${fmtName}</div>
          <div class="meta-chip-row">${chips || emptyState('No archetypes.')}</div>
        </div>
      `;
    }).join('');
  }
}

// ═══════════════════════════════════
// Alerts View
// ═══════════════════════════════════
function renderAlerts() {
  const container = $('#alerts-list');
  const fires = (alerts && Array.isArray(alerts.alerts)) ? alerts.alerts : [];
  const count = alerts && typeof alerts.count === 'number' ? alerts.count : fires.length;

  if (!alerts || count === 0 || fires.length === 0) {
    container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 16px;">No new alerts — run alerts.py after a data refresh.</div>';
    return;
  }

  container.innerHTML = fires.map(a => {
    const type = (a.type || '');
    const cls = type.includes('bullish') || type.includes('oversold') || type.includes('bb_lower') ? 'bullish' :
                type.includes('bearish') || type.includes('overbought') || type.includes('bb_upper') ? 'bearish' : 'neutral';
    const scryfall = a.scryfall_id || '';
    const name = a.name || 'Card';
    const label = a.label || type || 'Signal';
    const date = a.date || '';
    const setMeta = [a.set_code, a.foil ? 'foil' : null, a.binder].filter(Boolean).join(' · ');
    return `
      <div class="signal-card-item" data-scryfall="${scryfall}">
        ${scryfall ? `<img class="signal-card-thumb" src="${scryfallImage(scryfall)}" alt="" loading="lazy" />` : '<div class="signal-card-thumb"></div>'}
        <div class="signal-card-info">
          <div class="signal-card-name">${name}</div>
          <div class="signal-card-signal">
            <span class="signal-badge ${cls}">${label}</span>
            ${date ? `<span class="alert-date">${date}</span>` : ''}
            ${setMeta ? `<span class="alert-meta">${setMeta}</span>` : ''}
          </div>
        </div>
        <div class="signal-card-price">${fmt(a.current_price)}</div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.signal-card-item').forEach(el => {
    if (!el.dataset.scryfall) return;
    el.addEventListener('click', () => {
      switchView('chart');
      selectCard(el.dataset.scryfall);
    });
  });
}

// ═══════════════════════════════════
// Buylist Margin View
// ═══════════════════════════════════
let buylistSort = { key: 'margin_pct', dir: 'desc' };

function renderBuylist() {
  const tbody = $('#buylist-tbody');
  const rows = Array.isArray(buylist) ? buylist : [];

  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="color: var(--text-muted); text-align: center; padding: 24px;">No buylist margins — run preprocess.py after a data refresh.</td></tr>';
    return;
  }

  const { key, dir } = buylistSort;
  const sorted = [...rows].sort((a, b) => {
    let av = a[key];
    let bv = b[key];
    if (key === 'name') {
      av = (av || '').toLowerCase();
      bv = (bv || '').toLowerCase();
      const cmp = av.localeCompare(bv);
      return dir === 'asc' ? cmp : -cmp;
    }
    av = av ?? -Infinity;
    bv = bv ?? -Infinity;
    return dir === 'asc' ? av - bv : bv - av;
  });

  tbody.innerHTML = sorted.map(r => {
    const scryfall = r.scryfall_id || '';
    const name = r.name || 'Card';
    const nameHtml = scryfall
      ? `<a href="https://scryfall.com/card/${scryfall}" target="_blank" rel="noopener"><strong>${name}</strong></a>`
      : `<strong>${name}</strong>`;
    return `
      <tr>
        <td>${nameHtml}</td>
        <td>${r.set_code || '—'}${r.foil ? ' <span class="highlight">foil</span>' : ''}</td>
        <td style="font-family: var(--font-mono)">${fmt(r.best_retail)}</td>
        <td>${r.retail_vendor || '—'}</td>
        <td style="font-family: var(--font-mono)">${fmt(r.ck_buylist)}</td>
        <td class="positive" style="font-family: var(--font-mono); font-weight: 600">${fmt(r.margin_abs)}</td>
        <td class="positive" style="font-family: var(--font-mono); font-weight: 600">${fmtPct(r.margin_pct)}</td>
        <td style="font-size: 0.75rem; color: var(--text-muted)">${r.binder || '—'}</td>
      </tr>
    `;
  }).join('');

  // Sortable headers (bind once)
  const table = $('#buylist-table');
  if (table && !table.dataset.sortBound) {
    table.dataset.sortBound = '1';
    table.querySelectorAll('th[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const k = th.dataset.sort;
        if (buylistSort.key === k) {
          buylistSort.dir = buylistSort.dir === 'asc' ? 'desc' : 'asc';
        } else {
          buylistSort.key = k;
          buylistSort.dir = k === 'name' ? 'asc' : 'desc';
        }
        renderBuylist();
      });
    });
  }
}

// ═══════════════════════════════════
// Public Vault Gallery
// ═══════════════════════════════════
async function renderGallery() {
  const container = $('#gallery-grid');
  if (!container) return;

  const emptyState = (msg) =>
    `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 16px; grid-column: 1 / -1;">${msg}</div>`;

  container.innerHTML = emptyState('Loading vaults…');

  let vaults = [];
  try {
    const res = await fetch(`${API_BASE}/vaults`);
    if (!res.ok) throw new Error(`${res.status}`);
    const data = await res.json();
    vaults = Array.isArray(data?.vaults) ? data.vaults : [];
  } catch (e) {
    console.warn('Could not load vault gallery:', e);
    container.innerHTML = emptyState('Could not load vaults — the API may not be running.');
    return;
  }

  const ready = vaults.filter(v => v && v.status === 'ready');
  if (ready.length === 0) {
    container.innerHTML = emptyState('No public vaults yet. Import a collection to create the first one.');
    return;
  }

  container.innerHTML = ready.map(v => {
    const name = v.name || v.slug || 'Vault';
    const cardCount = (v.card_count ?? 0).toLocaleString();
    const valueHtml = (v.total_value !== null && v.total_value !== undefined)
      ? `<div class="gallery-card-value">${fmt(v.total_value, 0)}</div>`
      : '';
    return `
      <div class="gallery-card" data-slug="${v.slug}">
        <div class="gallery-card-name"><strong>${name}</strong></div>
        <div class="gallery-card-meta">${cardCount} cards</div>
        ${valueHtml}
      </div>
    `;
  }).join('');

  container.querySelectorAll('.gallery-card').forEach(el => {
    el.addEventListener('click', () => {
      const slug = el.dataset.slug;
      if (slug) window.location.href = `${window.location.origin}/?vault=${slug}`;
    });
  });
}

// ═══════════════════════════════════
// Vault Management
// ═══════════════════════════════════
function detectVault() {
  const params = new URLSearchParams(window.location.search);
  const slug = params.get('vault');
  if (slug) {
    currentVaultSlug = slug;
    localStorage.setItem('mana-vault-last', slug);
  } else {
    // Check localStorage for returning users
    const last = localStorage.getItem('mana-vault-last');
    if (last) {
      // Don't auto-load — just show a hint
      console.log(`Last vault: ${last}`);
    }
  }
}

async function showVaultBar() {
  if (!currentVaultSlug) {
    $('#vault-bar').style.display = 'none';
    $('#btn-export').style.display = 'none';
    return;
  }
  
  try {
    const res = await fetch(`${API_BASE}/vaults/${currentVaultSlug}/status`);
    if (res.ok) {
      currentVaultMeta = await res.json();
      $('#vault-bar-name').textContent = currentVaultMeta.name || currentVaultSlug;
      $('#vault-bar-meta').textContent = `${currentVaultMeta.card_count || '?'} cards · ${currentVaultMeta.created ? new Date(currentVaultMeta.created).toLocaleDateString() : ''}`;
      $('#vault-bar').style.display = 'block';
      $('#btn-export').style.display = 'flex';
    }
  } catch (e) {
    console.warn('Could not fetch vault meta:', e);
    // Still show vault bar with slug only
    $('#vault-bar-name').textContent = currentVaultSlug;
    $('#vault-bar-meta').textContent = '';
    $('#vault-bar').style.display = 'block';
    $('#btn-export').style.display = 'flex';
  }
}

function initVaultBar() {
  $('#btn-copy-vault-url').addEventListener('click', () => {
    const url = `${window.location.origin}/?vault=${currentVaultSlug}`;
    navigator.clipboard.writeText(url).then(() => {
      const btn = $('#btn-copy-vault-url');
      btn.textContent = '✓ Copied!';
      setTimeout(() => { btn.textContent = '📋 Copy Link'; }, 2000);
    });
  });
  
  $('#btn-close-vault').addEventListener('click', () => {
    currentVaultSlug = null;
    currentVaultMeta = null;
    localStorage.removeItem('mana-vault-last');
    window.history.replaceState({}, '', '/');
    $('#vault-bar').style.display = 'none';
    $('#btn-export').style.display = 'none';
    // Reload default data
    loadData().then(() => {
      renderPortfolio();
      switchView('portfolio');
    });
  });
}

// ═══════════════════════════════════
// Upload Flow
// ═══════════════════════════════════
let selectedFile = null;

function initUpload() {
  const modal = $('#upload-modal');
  const dropZone = $('#drop-zone');
  const fileInput = $('#file-input');
  const filenameEl = $('#drop-zone-filename');
  const submitBtn = $('#btn-upload-submit');
  
  // Open modal
  $('#btn-import').addEventListener('click', () => {
    modal.style.display = 'flex';
    selectedFile = null;
    filenameEl.style.display = 'none';
    submitBtn.disabled = true;
  });
  
  // Close modal
  $('#upload-modal-close').addEventListener('click', () => {
    modal.style.display = 'none';
  });
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
  });
  
  // Drag and drop
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
  });
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.csv')) {
      setSelectedFile(file);
    }
  });
  
  // File input
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) {
      setSelectedFile(fileInput.files[0]);
    }
  });
  
  function setSelectedFile(file) {
    selectedFile = file;
    filenameEl.textContent = `✅ ${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
    filenameEl.style.display = 'block';
    submitBtn.disabled = false;
  }
  
  // Submit
  submitBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    
    const name = $('#vault-name').value.trim() || 'My Vault';
    modal.style.display = 'none';
    
    // Show processing overlay
    const overlay = $('#processing-overlay');
    overlay.style.display = 'flex';
    $('#processing-status').textContent = 'Uploading...';
    
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('name', name);
      
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }
      
      const result = await res.json();
      const slug = result.slug;
      
      $('#processing-status').textContent = 'Processing price data...';
      
      // Poll for completion
      await pollVaultReady(slug);
      
      // Success — navigate to vault
      overlay.style.display = 'none';
      currentVaultSlug = slug;
      localStorage.setItem('mana-vault-last', slug);
      window.history.replaceState({}, '', `/?vault=${slug}`);
      
      // Reload with vault data
      await loadData();
      await showVaultBar();
      renderPortfolio();
      switchView('portfolio');
      
    } catch (err) {
      overlay.style.display = 'none';
      alert(`Upload failed: ${err.message}`);
    }
  });
}

async function pollVaultReady(slug, maxWait = 180) {
  const start = Date.now();
  const statusEl = $('#processing-status');
  
  while ((Date.now() - start) / 1000 < maxWait) {
    await new Promise(r => setTimeout(r, 3000));
    
    try {
      const res = await fetch(`${API_BASE}/vaults/${slug}/status`);
      if (res.ok) {
        const meta = await res.json();
        const elapsed = Math.round((Date.now() - start) / 1000);
        
        if (meta.status === 'ready') {
          statusEl.textContent = `Done! (${elapsed}s)`;
          return;
        } else if (meta.status === 'error') {
          throw new Error(meta.error || 'Processing failed');
        } else {
          statusEl.textContent = `Processing... (${elapsed}s)`;
        }
      }
    } catch (e) {
      if (e.message.includes('Processing failed')) throw e;
    }
  }
  throw new Error('Processing timed out');
}

// ═══════════════════════════════════
// Export
// ═══════════════════════════════════
function initExport() {
  $('#btn-export').addEventListener('click', () => {
    if (currentVaultSlug) {
      window.location.href = `${API_BASE}/export/${currentVaultSlug}`;
    }
  });
}

// ═══════════════════════════════════
// Init
// ═══════════════════════════════════
async function init() {
  console.log('🃏 Mana Vault initializing...');
  
  // Detect vault from URL or localStorage
  detectVault();
  
  initNav();
  initUpload();
  initExport();
  initVaultBar();
  
  try {
    await loadData();
    await showVaultBar();
    renderPortfolio();
    
    // Hide movers tab if viewing a vault (no movers data)
    if (currentVaultSlug) {
      const moversBtn = document.querySelector('[data-view="movers"]');
      if (moversBtn && movers.length === 0) moversBtn.style.display = 'none';
    }
    
    console.log('✅ Dashboard ready!');
  } catch (err) {
    console.error('Failed to load data:', err);
    document.getElementById('app').innerHTML = `
      <div style="padding: 60px; text-align: center; color: #ff5252;">
        <h2>Failed to load data</h2>
        <p>Make sure you've run <code>python3 preprocess.py</code> first, or <a href="/" style="color: var(--accent)">import a collection</a>.</p>
        <p style="color: #8b95b0; margin-top: 8px;">${err.message}</p>
      </div>
    `;
  }
}

init();
