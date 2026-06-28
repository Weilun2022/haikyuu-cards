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

  const DEFAULT_OPTIONS = {
    autoplay: false,
    showControls: true,
  };
  const _opts = { ...DEFAULT_OPTIONS, ...options };

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
      }

      .rv-zone {
        width: 60px;
        height: 80px;
        border: 1px solid var(--border, #333);
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 9px;
        color: var(--text-dim, #888);
        background: var(--surface2, #1a1a2e);
        overflow: hidden;
        position: relative;
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

      .rv-zone-label {
        position: absolute;
        bottom: 2px;
        right: 2px;
        background: rgba(0, 0, 0, 0.7);
        padding: 1px 3px;
        border-radius: 2px;
        font-size: 8px;
      }

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

    btnPrev.addEventListener('click', () => seek(Math.max(0, _currentStep - 1)));
    btnPlay.addEventListener('click', () => (_isPlaying ? pause() : play()));
    btnNext.addEventListener('click', () => seek(Math.min(_steps.length - 1, _currentStep + 1)));
    seekBar.addEventListener('input', (e) => seek(parseInt(e.target.value)));
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
          const img = document.createElement('img');
          img.src = `images/${firstCard.img}`;
          img.alt = `${playerKey} block`;
          zoneEl.appendChild(img);
        }
      } else {
        // 單 slot zone：null 或 {img, guts}
        if (zoneData && zoneData.img) {
          const img = document.createElement('img');
          img.src = `images/${zoneData.img}`;
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

  // ============ 公開方法 ============

  function loadReplay(newEvents, newMeta) {
    if (!newEvents || newEvents.length === 0) {
      console.warn('createReplayViewer: newEvents is empty');
      return;
    }
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
    _renderStep(_currentStep);
  }

  function clearHighlight() {
    _highlightedCards = new Set();
    _renderStep(_currentStep);
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
