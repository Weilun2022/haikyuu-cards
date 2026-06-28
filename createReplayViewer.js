/**
 * createReplayViewer - Replay 檢視器工廠函式
 * 建立可嵌入的回放控制實例，不依賴 iframe
 * @requires buildSteps.js 已被載入
 */

function createReplayViewer({ mount, events, meta = {}, options = {} }) {
  // ============ 私有狀態（closure 隔離）============
  let _steps = [];
  let _currentStep = -1;
  let _isPlaying = false;
  let _timer = null;
  let _highlightedCards = new Set();
  let _meta = meta;
  let _cardIndex = new Map();  // card_no → Set<HTMLElement>

  const DEFAULT_OPTIONS = {
    autoplay: false,
    showControls: true,
  };
  const _opts = { ...DEFAULT_OPTIONS, ...options };

  // ============ 用户意图回调 ============
  const _onUserIntent = typeof _opts.onUserIntent === 'function' ? _opts.onUserIntent : null;

  // ============ 事件類型中文對應 ============
  const EVENT_ZH = {
    game_start: '遊戲開始',
    draw: '抽牌',
    deploy: '部署',
    skill: '技能',
    guts: 'Guts',
    action: '行動',
    set_result: 'Set 結果',
    game_end: '遊戲結束',
    phase: '階段',
    judge: '判定',
    lost: '失點',
    interval: '換邊',
    board_snapshot: '盤面更新',
    turn_start: '回合開始',
  };

  // ============ 注入 CSS（一次性）============
  if (!document.getElementById('__rv_styles')) {
    const style = document.createElement('style');
    style.id = '__rv_styles';
    style.textContent = `
      .rv-container {
        display: flex;
        flex-direction: column;
        gap: 6px;
        height: 100%;
        font-family: var(--font-mono, monospace);
        color: var(--text, #e0e0e0);
      }

      .rv-header {
        display: flex;
        gap: 12px;
        align-items: center;
        font-size: 12px;
        color: var(--text-dim, #888);
        padding: 4px 0;
        border-bottom: 1px solid var(--border, #333);
      }

      .rv-title {
        flex: 1;
      }

      .rv-score {
        font-weight: bold;
        color: var(--accent, #6c63ff);
      }

      .rv-board {
        display: flex;
        gap: 8px;
        flex: 1;
        min-height: 300px;
      }

      .rv-player {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
        padding: 6px;
        border: 1px solid var(--border, #333);
        border-radius: 4px;
        background: var(--surface2, #0f0f1e);
      }

      .rv-player.rv-p2 {
        flex-direction: column-reverse;
      }

      .rv-zones {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        flex: 1;
        background-color: #040810;
        background-image:
          linear-gradient(rgba(0,120,255,.06) 1px, transparent 1px),
          linear-gradient(90deg, rgba(0,120,255,.06) 1px, transparent 1px);
        background-size: 20px 20px;
        border-radius: 8px;
        padding: 4px;
        box-shadow: inset 0 0 0 1px rgba(0,100,255,.18), inset 0 0 30px rgba(0,60,180,.12);
      }

      .rv-zone {
        width: 72px;
        height: 96px;
        border: 1.5px dashed var(--border, #333);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 9px;
        color: var(--text-dim, #888);
        background: rgba(20,24,36,.85);
        overflow: hidden;
        position: relative;
        transition: border-color .15s, box-shadow .15s;
      }

      .rv-zone img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .rv-zone.rv-highlight {
        border-color: var(--arena-data-hot, #ff2d78);
        box-shadow: 0 0 6px var(--arena-data-hot, #ff2d78);
      }

      /* Neon zone colors */
      .rv-zone[data-zone="block"]   { border-color: #505870; background: rgba(20,24,36,.85); box-shadow: inset 0 0 0 1px rgba(80,88,112,.35), 0 0 8px rgba(80,88,112,.3); }
      .rv-zone[data-zone="serve"]   { border-color: #ffc800; background: rgba(90,60,0,.5);   box-shadow: inset 0 0 0 1px rgba(255,200,0,.25), 0 0 10px rgba(255,200,0,.5); }
      .rv-zone[data-zone="receive"] { border-color: #0e7fff; background: rgba(8,32,120,.45); box-shadow: inset 0 0 0 1px rgba(14,127,255,.25), 0 0 10px rgba(14,127,255,.5); }
      .rv-zone[data-zone="toss"]    { border-color: #00d850; background: rgba(0,80,30,.45);  box-shadow: inset 0 0 0 1px rgba(0,216,80,.25), 0 0 10px rgba(0,216,80,.45); }
      .rv-zone[data-zone="attack"]  { border-color: #ff2820; background: rgba(100,10,8,.5);  box-shadow: inset 0 0 0 1px rgba(255,40,32,.25), 0 0 10px rgba(255,40,32,.55); }

      .rv-zone::after {
        position: absolute;
        bottom: 4px;
        left: 0; right: 0;
        text-align: center;
        font-size: 9px;
        font-weight: 800;
        letter-spacing: 1.5px;
        pointer-events: none;
        opacity: .9;
        line-height: 1;
        z-index: 2;
      }
      .rv-zone[data-zone="block"]::after   { content: 'BLOCK';   color: #8898c8; text-shadow: 0 0 6px rgba(80,88,112,.8); }
      .rv-zone[data-zone="serve"]::after   { content: 'SERVE';   color: #ffd840; text-shadow: 0 0 8px rgba(255,200,0,1); }
      .rv-zone[data-zone="receive"]::after { content: 'RECEIVE'; color: #4ab4ff; text-shadow: 0 0 8px rgba(14,127,255,1); }
      .rv-zone[data-zone="toss"]::after    { content: 'TOSS';    color: #00e85a; text-shadow: 0 0 8px rgba(0,216,80,1); }
      .rv-zone[data-zone="attack"]::after  { content: 'ATTACK';  color: #ff6058; text-shadow: 0 0 8px rgba(255,40,32,1); }

      .rv-counters {
        font-size: 11px;
        color: var(--text-dim, #888);
        display: flex;
        gap: 12px;
      }

      .rv-counters span {
        color: var(--accent, #6c63ff);
      }

      .rv-event-msg {
        font-size: 11px;
        color: var(--accent, #6c63ff);
        min-height: 16px;
        padding: 4px 0;
        border-top: 1px solid var(--border, #333);
      }

      .rv-controls {
        display: flex;
        gap: 4px;
        align-items: center;
        padding: 4px 0;
      }

      .rv-btn {
        padding: 4px 10px;
        font-size: 12px;
        background: var(--surface2, #1a1a2e);
        border: 1px solid var(--border, #333);
        color: var(--text, #e0e0e0);
        cursor: pointer;
        border-radius: 3px;
        transition: background 0.2s;
      }

      .rv-btn:hover {
        background: var(--surface3, #2a2a3e);
      }

      .rv-btn:active {
        background: var(--accent, #6c63ff);
        color: var(--surface1, #000);
      }

      .rv-seek {
        flex: 1;
        height: 4px;
        cursor: pointer;
      }
    `;
    document.head.appendChild(style);
  }

  // ============ DOM 初始化 ============
  function _buildDOM() {
    mount.innerHTML = `
      <div class="rv-container">
        <div class="rv-header">
          <span class="rv-title">
            P1 <span class="rv-p1-name">${_meta.p1_name || 'Player 1'}</span>
            vs
            P2 <span class="rv-p2-name">${_meta.p2_name || 'Player 2'}</span>
          </span>
          <span class="rv-score">${_meta.p1_sets || 0} : ${_meta.p2_sets || 0}</span>
          <span class="rv-step-counter">步驟 0 / 0</span>
        </div>

        <div class="rv-board">
          <div class="rv-player" id="rv-p1">
            <div class="rv-zones"></div>
            <div class="rv-counters">
              手: <span class="rv-hand">6</span>
              庫: <span class="rv-pile">40</span>
            </div>
          </div>

          <div class="rv-player rv-p2" id="rv-p2">
            <div class="rv-counters">
              手: <span class="rv-hand">6</span>
              庫: <span class="rv-pile">40</span>
            </div>
            <div class="rv-zones"></div>
          </div>
        </div>

        <div class="rv-event-msg"></div>

        <div class="rv-controls">
          <button class="rv-btn rv-prev">◀◀</button>
          <button class="rv-btn rv-play">▶</button>
          <button class="rv-btn rv-next">▶▶</button>
          <input type="range" class="rv-seek" min="0" step="1" value="0">
          <span class="rv-step-info">0 / 0</span>
        </div>
      </div>
    `;

    // ============ 事件綁定 ============
    const btnPrev = mount.querySelector('.rv-prev');
    const btnPlay = mount.querySelector('.rv-play');
    const btnNext = mount.querySelector('.rv-next');
    const seekBar = mount.querySelector('.rv-seek');

    btnPrev.addEventListener('click', () => {
      if (_onUserIntent) _onUserIntent('seek-prev');
      seek(Math.max(0, _currentStep - 1));
    });
    btnPlay.addEventListener('click', () => {
      if (_onUserIntent) _onUserIntent('toggle-play');
      _isPlaying ? pause() : play();
    });
    btnNext.addEventListener('click', () => {
      if (_onUserIntent) _onUserIntent('seek-next');
      seek(Math.min(_steps.length - 1, _currentStep + 1));
    });
    seekBar.addEventListener('input', (e) => {
      if (_onUserIntent) _onUserIntent('seek-drag');
      seek(parseInt(e.target.value));
    });
  }

  // ============ 私有方法 ============

  function _updateHeader() {
    if (!mount.querySelector('.rv-step-counter')) return;
    mount.querySelector('.rv-step-counter').textContent = `步驟 ${_currentStep + 1} / ${_steps.length}`;
    mount.querySelector('.rv-step-info').textContent = `${_currentStep + 1} / ${_steps.length}`;
    const seek = mount.querySelector('.rv-seek');
    if (seek) {
      seek.max = Math.max(0, _steps.length - 1);
      seek.value = _currentStep;
    }
  }

  function _renderStep(idx) {
    if (idx < 0 || idx >= _steps.length) return;

    const step = _steps[idx];
    if (!step || !step.state) return;

    const state = step.state;
    const event = step.event || {};

    // 更新 P1 和 P2 盤面
    for (const playerKey of ['p1', 'p2']) {
      _renderPlayer(playerKey, state);
    }

    // 更新事件訊息（buildSteps.js 使用 event.kind 欄位）
    const eventType = event.kind || 'board_snapshot';
    const eventMsg = EVENT_ZH[eventType] || eventType;
    const eventEl = mount.querySelector('.rv-event-msg');
    if (eventEl) {
      eventEl.textContent = `[${idx + 1}] ${eventMsg}`;
    }

    // 更新控制列
    _updateHeader();

    // 重建 card index（card_no → DOM elements）
    _cardIndex = new Map();
    mount.querySelectorAll('.rv-zone[data-card-no]').forEach(el => {
      const cno = el.dataset.cardNo;
      if (!cno) return;
      if (!_cardIndex.has(cno)) _cardIndex.set(cno, new Set());
      _cardIndex.get(cno).add(el);
    });
  }

  function _renderPlayer(playerKey, state) {
    const playerEl = mount.querySelector(`#rv-${playerKey}`);
    if (!playerEl) return;

    const zonesContainer = playerEl.querySelector('.rv-zones');
    const counterHand = playerEl.querySelector('.rv-hand');
    const counterPile = playerEl.querySelector('.rv-pile');

    // 清空 zones
    zonesContainer.innerHTML = '';

    // 定義 zone 名稱
    const zoneNames = ['serve', 'receive', 'toss', 'attack', 'block'];
    const zoneLabels = ['發球', '接球', '舉球', '攻撃', '攔網'];

    // 為每個 zone 建立容器
    // buildSteps state 結構：{ zones: { serve: {img,guts}|null, block: [{img,guts}|null, ...] }, hand_count, pile_count }
    zoneNames.forEach((zoneName, zIdx) => {
      const zoneEl = document.createElement('div');
      zoneEl.className = 'rv-zone';
      zoneEl.dataset.zone = zoneName;

      const zoneData = state[playerKey]?.zones?.[zoneName];

      if (zoneName === 'block') {
        // block 是 3-slot 陣列，只顯示第一個有卡的
        const slots = Array.isArray(zoneData) ? zoneData : [];
        const firstCard = slots.find(s => s && s.img);
        if (firstCard) {
          zoneEl.dataset.cardNo = firstCard.card_no || '';
          const img = document.createElement('img');
          img.src = `/images/${firstCard.img}`;
          img.alt = `${playerKey} block`;
          zoneEl.appendChild(img);
        }
      } else {
        // 單 slot zone：null 或 {img, guts}
        if (zoneData && zoneData.img) {
          zoneEl.dataset.cardNo = zoneData.card_no || '';
          const img = document.createElement('img');
          img.src = `/images/${zoneData.img}`;
          img.alt = `${playerKey} ${zoneName}`;
          zoneEl.appendChild(img);
        }
      }

      // 加上 zone 標籤（角落）
      const label = document.createElement('div');
      label.className = 'rv-zone-label';
      label.textContent = zoneLabels[zIdx];
      zoneEl.appendChild(label);

      zonesContainer.appendChild(zoneEl);
    });

    // 更新計數器（buildSteps 用 hand_count / pile_count）
    if (counterHand) counterHand.textContent = state[playerKey]?.hand_count ?? 0;
    if (counterPile) counterPile.textContent = state[playerKey]?.pile_count ?? 0;
  }

  function _zoneHasCard(playerState, cno) {
    const zones = (playerState && playerState.zones) ? playerState.zones : {};
    for (const [name, data] of Object.entries(zones)) {
      if (name === 'block') {
        if (Array.isArray(data) && data.some(s => s && s.card_no === cno)) return true;
      } else {
        if (data && data.card_no === cno) return true;
      }
    }
    return false;
  }

  function _findStepWithBothCards(cardNos) {
    // 先往後（currentStep → end），再往前（currentStep-1 → 0）
    // 優先找「接下來」的命中，其次找「之前」的命中（最近原則）
    const checkStep = (i) => {
      const step = _steps[i];
      if (!step || !step.state) return false;
      const state = step.state;
      return cardNos.every(cno =>
        _zoneHasCard(state.p1, cno) || _zoneHasCard(state.p2, cno)
      );
    };

    // 往後掃（含 currentStep）
    for (let i = _currentStep; i < _steps.length; i++) {
      if (checkStep(i)) return i;
    }
    // 往前掃（currentStep-1 → 0）
    for (let i = _currentStep - 1; i >= 0; i--) {
      if (checkStep(i)) return i;
    }
    return -1;
  }

  // ============ 公開方法 ============

  function loadReplay(newEvents, newMeta) {
    if (!newEvents || newEvents.length === 0) {
      console.warn('createReplayViewer: newEvents is empty');
      return;
    }
    // 清理舊狀態（idempotent）
    pause();
    _cardIndex = new Map();
    mount.querySelectorAll('.rv-zone.rv-highlight').forEach(el => el.classList.remove('rv-highlight'));
    _highlightedCards = new Set();
    _steps = buildSteps(newEvents);
    _meta = newMeta || _meta;
    _currentStep = -1;
    _isPlaying = false;
    if (_timer) clearInterval(_timer);
    _timer = null;
    _updateHeader();
    seek(0);
  }

  function play() {
    if (_isPlaying || _currentStep >= _steps.length - 1) return;
    _isPlaying = true;
    const btnPlay = mount.querySelector('.rv-play');
    if (btnPlay) btnPlay.textContent = '⏸';
    _timer = setInterval(() => {
      if (_currentStep < _steps.length - 1) {
        seek(_currentStep + 1);
      } else {
        pause();
      }
    }, 600);
  }

  function pause() {
    _isPlaying = false;
    if (_timer) clearInterval(_timer);
    _timer = null;
    const btnPlay = mount.querySelector('.rv-play');
    if (btnPlay) btnPlay.textContent = '▶';
  }

  function seek(idx) {
    idx = Math.max(0, Math.min(idx, Math.max(0, _steps.length - 1)));
    _currentStep = idx;
    _renderStep(idx);
  }

  function highlightCards(cardNos) {
    _highlightedCards = new Set(cardNos);
    mount.querySelectorAll('.rv-zone.rv-highlight').forEach(el => el.classList.remove('rv-highlight'));
    const found = [], missing = [];
    for (const cno of cardNos) {
      const els = _cardIndex.get(cno);
      if (els && els.size > 0) {
        els.forEach(el => el.classList.add('rv-highlight'));
        found.push(cno);
      } else {
        missing.push(cno);
      }
    }
    if (missing.length > 0) {
      console.warn('[createReplayViewer] highlightCards: 部分 combo 卡片目前步驟不可見', missing);
    }
    return { found, missing };
  }

  function clearHighlight() {
    _highlightedCards = new Set();
    _renderStep(_currentStep);
  }

  function seekToCards(cardNos) {
    if (!cardNos || cardNos.length === 0) return false;
    const idx = _findStepWithBothCards(cardNos);
    if (idx < 0) return false;
    seek(idx);
    return true;
  }

  function destroy() {
    pause();
    mount.innerHTML = '';
  }

  // ============ 初始化 ============
  _buildDOM();
  if (events && events.length > 0) {
    loadReplay(events, meta);
  }

  // ============ 返回公開 API ============
  return {
    loadReplay,
    play,
    pause,
    seek,
    highlightCards,
    clearHighlight,
    seekToCards,
    destroy,
  };
}

// ============ Legacy Shim ============
// 如果頁面有 REPLAY_EVENTS 全域變數且容器存在，自動掛載
if (typeof REPLAY_EVENTS !== 'undefined' && document.getElementById('replay-root')) {
  document.addEventListener('DOMContentLoaded', () => {
    if (typeof buildSteps !== 'undefined') {
      createReplayViewer({
        mount: document.getElementById('replay-root'),
        events: REPLAY_EVENTS,
      });
    }
  });
}
