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

      .rv-board-compat {
        /* placeholder - old .rv-board and .rv-player rules removed */
      }

      /* ── game.html board CSS ── */
      .rv-board-wrap {
        display: flex;
        flex-direction: column;
        gap: 8px;
        flex: 1;
        min-height: 0;
      }

      .rv-player-area {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-height: 0;
        gap: 4px;
      }

      .rv-net {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-shrink: 0;
        padding: 2px 0;
      }
      .rv-net-line {
        flex: 1;
        height: 2px;
        background: linear-gradient(90deg, transparent, rgba(0,200,255,.5), rgba(0,200,255,.5), transparent);
      }
      .rv-net-text {
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 3px;
        color: rgba(0,200,255,.7);
        text-shadow: 0 0 8px rgba(0,200,255,.8);
      }

      .rv-player-label {
        font-size: 11px;
        font-weight: 700;
        color: var(--accent, #6c63ff);
        padding: 2px 0;
      }
      .rv-player-label.p2 { color: var(--accent2, #ff6584); }

      .rv-counters-row {
        font-size: 11px;
        color: var(--text-dim, #888);
        display: flex;
        gap: 8px;
        padding: 2px 0;
      }
      .rv-counters-row span { color: var(--accent, #6c63ff); }

      .board-court {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-height: 0;
        background-color: #040810;
        background-image:
          linear-gradient(rgba(0,120,255,.06) 1px, transparent 1px),
          linear-gradient(90deg, rgba(0,120,255,.06) 1px, transparent 1px);
        background-size: 20px 20px;
        border-radius: 10px;
        padding: 5px;
        box-shadow:
          inset 0 0 0 1px rgba(0,100,255,.18),
          inset 0 0 30px rgba(0,60,180,.12),
          0 0 8px rgba(0,80,200,.15);
      }

      .court-row {
        display: flex;
        gap: 4px;
        flex: 1;
        min-height: 0;
      }

      .zone-w {
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 1;
        min-width: 0;
        gap: 0;
        min-height: 0;
      }

      .z-slot {
        width: 100%;
        flex: 1;
        background: rgba(20,24,36,.85);
        border: 1.5px dashed var(--border, #2a2a3e);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        overflow: hidden;
        min-height: 60px;
        min-width: 0;
        transition: border-color .15s, box-shadow .15s;
      }

      .z-slot.z-blk {
        border-color: #505870;
        background: rgba(20,24,36,.85);
        box-shadow: inset 0 0 0 1px rgba(80,88,112,.35), 0 0 8px rgba(80,88,112,.3);
      }
      .z-slot.z-rcv {
        border-color: #0e7fff;
        background: rgba(8,32,120,.45);
        box-shadow: inset 0 0 0 1px rgba(14,127,255,.25), 0 0 10px rgba(14,127,255,.5);
      }
      .z-slot.z-tos {
        border-color: #00d850;
        background: rgba(0,80,30,.45);
        box-shadow: inset 0 0 0 1px rgba(0,216,80,.25), 0 0 10px rgba(0,216,80,.45);
      }
      .z-slot.z-atk {
        border-color: #ff2820;
        background: rgba(100,10,8,.5);
        box-shadow: inset 0 0 0 1px rgba(255,40,32,.25), 0 0 10px rgba(255,40,32,.55);
      }
      .z-slot.z-srv {
        border-color: #ffc800;
        background: rgba(90,60,0,.5);
        box-shadow: inset 0 0 0 1px rgba(255,200,0,.25), 0 0 10px rgba(255,200,0,.5);
      }
      .z-slot.z-evt {
        border-color: #00d8e8;
        background: rgba(0,70,90,.45);
        box-shadow: inset 0 0 0 1px rgba(0,216,232,.25), 0 0 10px rgba(0,216,232,.5);
      }

      .z-slot::after {
        position: absolute;
        bottom: 4px;
        left: 0; right: 0;
        text-align: center;
        font-size: 9px;
        font-weight: 800;
        letter-spacing: 1.5px;
        pointer-events: none;
        opacity: .85;
        line-height: 1;
        z-index: 2;
      }
      .z-slot.z-blk::after { content: 'BLOCK';   color: #8898c8; text-shadow: 0 0 6px rgba(80,88,112,.8); }
      .z-slot.z-rcv::after { content: 'RECEIVE'; color: #4ab4ff; text-shadow: 0 0 8px rgba(14,127,255,1); }
      .z-slot.z-tos::after { content: 'TOSS';    color: #00e85a; text-shadow: 0 0 8px rgba(0,216,80,1); }
      .z-slot.z-atk::after { content: 'ATTACK';  color: #ff6058; text-shadow: 0 0 8px rgba(255,40,32,1); }
      .z-slot.z-srv::after { content: 'SERVE';   color: #ffd840; text-shadow: 0 0 8px rgba(255,200,0,1); }
      .z-slot.z-evt::after { content: 'EVENT';   color: #40eeff; text-shadow: 0 0 8px rgba(0,216,232,1); }

      .z-empty {
        color: var(--text-dim, #888);
        font-size: 12px;
        z-index: 3;
      }

      /* z-hstack：卡牌橫排堆疊（position:absolute 確保填滿 slot） */
      .z-hstack {
        position: absolute;
        inset: 0;
        padding: 4px;
        display: flex;
        flex-direction: row;
        align-items: flex-start;
        justify-content: flex-start;
        overflow: hidden;
      }

      .z-hstack-card {
        position: relative;
        flex: 0 0 auto;
        /* height/width set by _layoutHstack() in JS */
        overflow: hidden;
        border-radius: 5px;
        box-shadow: 3px 4px 14px rgba(0,0,0,.85);
      }

      .z-hstack-card img {
        width: 100%; height: 100%;
        object-fit: cover;
        display: block;
      }

      .z-hstack-name {
        position: absolute;
        top: 3px; left: 0; right: 0;
        writing-mode: vertical-rl;
        font-size: 8px;
        color: #fff;
        text-shadow: 0 1px 3px #000;
        white-space: nowrap;
        overflow: hidden;
        text-align: center;
        pointer-events: none;
        z-index: 2;
        height: calc(100% - 6px);
      }

      .z-hstack-tag {
        position: absolute;
        bottom: 2px; right: 2px;
        font-size: 7px;
        font-weight: 700;
        background: rgba(0,0,0,.8);
        color: #fb923c;
        border-radius: 3px;
        padding: 1px 3px;
        z-index: 3;
        pointer-events: none;
      }

      .z-slot.rv-highlight {
        border-color: var(--arena-data-hot, #ff2d78);
        box-shadow: 0 0 6px var(--arena-data-hot, #ff2d78);
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

        <div class="rv-board-wrap">

          <!-- P2 在上（對手），板面鏡像：SERVE 在頂，中排 ATK|TOS|RCV，BLOCK 靠近 NET -->
          <div class="rv-player-area" id="rv-p2">
            <div class="rv-counters-row">手: <span class="rv-hand">0</span> 庫: <span class="rv-pile">40</span> — <span class="rv-player-label p2" style="display:inline;padding:0;">P2 <span class="rv-p2-name-inline"></span></span></div>
            <div class="board-court" id="rv-p2-court">
              <div class="court-row">
                <div class="zone-w" style="visibility:hidden;"></div>
                <div class="zone-w"><div class="z-slot z-evt" data-zone="event"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-srv" data-zone="serve"><div class="z-empty">—</div></div></div>
              </div>
              <div class="court-row">
                <div class="zone-w"><div class="z-slot z-atk" data-zone="attack"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-tos" data-zone="toss"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-rcv" data-zone="receive"><div class="z-empty">—</div></div></div>
              </div>
              <div class="court-row">
                <div class="zone-w"><div class="z-slot z-blk" data-zone="block-0"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-blk" data-zone="block-1"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-blk" data-zone="block-2"><div class="z-empty">—</div></div></div>
              </div>
            </div>
          </div>

          <!-- NET 分隔線 -->
          <div class="rv-net">
            <div class="rv-net-line"></div>
            <div class="rv-net-text">NET</div>
            <div class="rv-net-line"></div>
          </div>

          <!-- P1 在下（我方），正向排列：BLOCK 靠近 NET，SERVE 在底 -->
          <div class="rv-player-area" id="rv-p1">
            <div class="board-court" id="rv-p1-court">
              <div class="court-row">
                <div class="zone-w"><div class="z-slot z-blk" data-zone="block-0"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-blk" data-zone="block-1"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-blk" data-zone="block-2"><div class="z-empty">—</div></div></div>
              </div>
              <div class="court-row">
                <div class="zone-w"><div class="z-slot z-rcv" data-zone="receive"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-tos" data-zone="toss"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-atk" data-zone="attack"><div class="z-empty">—</div></div></div>
              </div>
              <div class="court-row">
                <div class="zone-w"><div class="z-slot z-srv" data-zone="serve"><div class="z-empty">—</div></div></div>
                <div class="zone-w"><div class="z-slot z-evt" data-zone="event"><div class="z-empty">—</div></div></div>
                <div class="zone-w" style="visibility:hidden;"></div>
              </div>
            </div>
            <div class="rv-counters-row"><span class="rv-player-label" style="display:inline;padding:0;">P1 <span class="rv-p1-name-inline"></span></span> — 手: <span class="rv-hand">0</span> 庫: <span class="rv-pile">40</span></div>
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
    mount.querySelectorAll('.z-slot[data-card-no]').forEach(el => {
      const cno = el.dataset.cardNo;
      if (!cno) return;
      if (!_cardIndex.has(cno)) _cardIndex.set(cno, new Set());
      _cardIndex.get(cno).add(el);
    });
  }

  // 移植自 game.html layoutHstack — JS 動態計算卡牌高度與重疊量
  function _layoutHstack(hstack) {
    requestAnimationFrame(() => {
      const cards = [...hstack.querySelectorAll('.z-hstack-card')];
      if (!cards.length) return;
      const slotH = hstack.offsetHeight;
      if (!slotH) return;
      const cardH = slotH - 8;
      cards.forEach(c => {
        c.style.height = cardH + 'px';
        c.style.width = (cardH * 5 / 7) + 'px';
      });
      if (cards.length < 2) return;
      const cardW = cards[0].offsetWidth || (cardH * 5 / 7);
      const zoneW = hstack.offsetWidth - 8;
      const idealOverlap = Math.floor(cardW * 0.40);
      const totalAtIdeal = cardW + (cards.length - 1) * (cardW - idealOverlap);
      let overlap;
      if (totalAtIdeal <= zoneW) {
        overlap = idealOverlap;
      } else {
        const minShow = Math.max(Math.floor(cardW * 0.22), 10);
        overlap = cardW - Math.max(Math.floor((zoneW - cardW) / (cards.length - 1)), minShow);
      }
      cards.forEach((c, i) => {
        c.style.marginLeft = i > 0 ? `-${Math.max(0, overlap)}px` : '0';
      });
    });
  }

  function _renderPlayer(playerKey, state) {
    const playerEl = mount.querySelector(`#rv-${playerKey}`);
    if (!playerEl) return;

    const counterHand = playerEl.querySelector('.rv-hand');
    const counterPile = playerEl.querySelector('.rv-pile');
    const courtEl     = playerEl.querySelector('.board-court');

    if (!courtEl) return;

    const pState = state[playerKey];
    const zones  = pState?.zones || {};

    // 填充輔助函式：把 cardData 渲染進 z-slot
    const fillSlot = (slotEl, cardData) => {
      if (!slotEl) return;
      slotEl.innerHTML = '';
      slotEl.dataset.cardNo = '';
      if (!cardData || !cardData.img) {
        slotEl.innerHTML = '<div class="z-empty">—</div>';
        return;
      }
      slotEl.dataset.cardNo = cardData.card_no || '';

      const guts = cardData.guts || [];
      const allImgs = [...guts.map(g => (typeof g === 'string' ? g : g?.img)).filter(Boolean), cardData.img];

      const hstack = document.createElement('div');
      hstack.className = 'z-hstack';

      allImgs.forEach((imgFile, i) => {
        const isTop = i === allImgs.length - 1;
        const cardEl = document.createElement('div');
        cardEl.className = 'z-hstack-card';

        const imgEl = document.createElement('img');
        imgEl.src = `/images/${imgFile}`;
        imgEl.loading = 'lazy';
        imgEl.onerror = () => { imgEl.onerror = null; imgEl.removeAttribute('src'); };
        cardEl.appendChild(imgEl);

        if (!isTop) {
          const tag = document.createElement('span');
          tag.className = 'z-hstack-tag';
          tag.textContent = 'G';
          cardEl.appendChild(tag);
        }
        hstack.appendChild(cardEl);
      });
      slotEl.appendChild(hstack);
      _layoutHstack(hstack);
    };

    // Block slots（3 個）
    const blockSlots = Array.isArray(zones.block) ? zones.block : [];
    for (let i = 0; i < 3; i++) {
      const slotEl = courtEl.querySelector(`.z-slot[data-zone="block-${i}"]`);
      fillSlot(slotEl, blockSlots[i] || null);
    }

    // 單 slot zones
    ['receive', 'toss', 'attack', 'serve'].forEach(zoneName => {
      const slotEl = courtEl.querySelector(`.z-slot[data-zone="${zoneName}"]`);
      fillSlot(slotEl, zones[zoneName] || null);
    });

    // Event zone（技能區 — 0~N 張，統一用 _layoutHstack）
    const evSlot = courtEl.querySelector('.z-slot[data-zone="event"]');
    if (evSlot) {
      const evCards = Array.isArray(zones.event) ? zones.event : [];
      evSlot.innerHTML = '';
      if (evCards.length > 0) {
        const hstack = document.createElement('div');
        hstack.className = 'z-hstack';
        evCards.forEach(cardData => {
          const cardEl = document.createElement('div');
          cardEl.className = 'z-hstack-card';
          const imgEl = document.createElement('img');
          imgEl.src = `/images/${cardData.img}`;
          imgEl.loading = 'lazy';
          imgEl.onerror = () => { imgEl.onerror = null; imgEl.removeAttribute('src'); };
          cardEl.appendChild(imgEl);
          hstack.appendChild(cardEl);
        });
        evSlot.appendChild(hstack);
        _layoutHstack(hstack);
      } else {
        evSlot.innerHTML = '<div class="z-empty">—</div>';
      }
    }

    // 更新計數器
    if (counterHand) counterHand.textContent = pState?.hand_count ?? 0;
    if (counterPile) counterPile.textContent = pState?.pile_count ?? 0;
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
    mount.querySelectorAll('.z-slot.rv-highlight').forEach(el => el.classList.remove('rv-highlight'));
    _highlightedCards = new Set();
    _steps = buildSteps(newEvents);
    _meta = newMeta || _meta;
    _currentStep = -1;
    _isPlaying = false;
    if (_timer) clearInterval(_timer);
    _timer = null;

    // 更新玩家名稱
    const p1label = mount.querySelector('.rv-p1-name');
    if (p1label) p1label.textContent = _meta.p1_name || 'P1';
    const p2label = mount.querySelector('.rv-p2-name');
    if (p2label) p2label.textContent = _meta.p2_name || 'P2';
    const p1inline = mount.querySelector('.rv-p1-name-inline');
    if (p1inline) p1inline.textContent = _meta.p1_name || '';
    const p2inline = mount.querySelector('.rv-p2-name-inline');
    if (p2inline) p2inline.textContent = _meta.p2_name || '';

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
        if (typeof _opts.onPlaybackEnd === 'function') {
          try { _opts.onPlaybackEnd(); } catch (e) {}
        }
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
    mount.querySelectorAll('.z-slot.rv-highlight').forEach(el => el.classList.remove('rv-highlight'));
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
    mount.querySelectorAll('.z-slot.rv-highlight').forEach(el => el.classList.remove('rv-highlight'));
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
