function buildSteps(events) {
  // Initialize empty player state
  const emptyPlayer = () => ({
    zones: { serve: null, receive: null, toss: null, attack: null, block: [null, null, null] },
    hand_count: 0,
    pile_count: 40,
    grave_count: 0,
    set_cards: 0
  });

  let state = {
    p1: emptyPlayer(),
    p2: emptyPlayer()
  };

  const steps = [];

  // Helper: Deep copy state
  const copyState = () => JSON.parse(JSON.stringify(state));

  // Helper: Build card object with guts
  const buildCardData = (card_no, guts_nos = []) => {
    if (!card_no) return null;
    return {
      card_no: card_no,
      img: card_no + '.jpg',
      guts: guts_nos.map(n => ({ card_no: n, img: n + '.jpg' }))
    };
  };

  // Process each event
  for (let i = 0; i < events.length; i++) {
    const event = events[i];
    const player = event.player; // 1 or 2 (if applicable)

    switch (event.kind) {
      case 'game_start':
        // No state update, just record the event
        break;

      case 'phase':
        // No state update, just record the event
        break;

      case 'draw':
        // Increment hand_count, decrement pile_count
        if (player === 1) {
          state.p1.hand_count += 1;
          state.p1.pile_count = Math.max(0, state.p1.pile_count - 1);
        } else if (player === 2) {
          state.p2.hand_count += 1;
          state.p2.pile_count = Math.max(0, state.p2.pile_count - 1);
        }
        break;

      case 'deploy':
        // Update zones based on zone type
        if (player === 1 || player === 2) {
          const playerState = player === 1 ? state.p1 : state.p2;
          const { card_no, zone } = event.data;

          if (zone === 'block') {
            // Find first empty slot or use block[0]
            let blockIdx = playerState.zones.block.findIndex(slot => slot === null);
            if (blockIdx === -1) blockIdx = 0;

            playerState.zones.block[blockIdx] = {
              card_no: card_no,
              img: card_no + '.jpg',
              guts: []
            };
          } else if (['serve', 'receive', 'toss', 'attack'].includes(zone)) {
            // Get old card data
            const oldCard = playerState.zones[zone];
            let newGuts = [];

            if (oldCard !== null) {
              // Preserve old card as guts
              newGuts = [...(oldCard.guts || []), oldCard.img];
            }

            playerState.zones[zone] = {
              card_no: card_no,
              img: card_no + '.jpg',
              guts: newGuts
            };
          }

          // Decrement hand_count
          playerState.hand_count = Math.max(0, playerState.hand_count - 1);
        }
        break;

      case 'board_snapshot':
        // Complete state update from snapshot
        if (player === 1 || player === 2) {
          const playerState = player === 1 ? state.p1 : state.p2;
          const { serve_no, receive_no, toss_no, attack_no, block_nos } = event.data;
          const { serve_guts_nos, receive_guts_nos, toss_guts_nos, attack_guts_nos, block_guts_nos } = event.data;
          const { hand_count, pile_count, grave_count, set_cards } = event.data;

          // Update zones
          playerState.zones.serve = buildCardData(serve_no, serve_guts_nos || []);
          playerState.zones.receive = buildCardData(receive_no, receive_guts_nos || []);
          playerState.zones.toss = buildCardData(toss_no, toss_guts_nos || []);
          playerState.zones.attack = buildCardData(attack_no, attack_guts_nos || []);

          // Update block zone (3 slots)
          playerState.zones.block = [];
          for (let idx = 0; idx < 3; idx++) {
            const blockNo = (block_nos && block_nos[idx]) || null;
            const blockGuts = (block_guts_nos && block_guts_nos[idx]) || [];
            playerState.zones.block[idx] = buildCardData(blockNo, blockGuts);
          }

          // Update counters
          playerState.hand_count = hand_count || 0;
          playerState.pile_count = pile_count || 0;
          playerState.grave_count = grave_count || 0;
          playerState.set_cards = set_cards || 0;
        }
        break;

      case 'judge':
        // No state update, just record the event
        break;

      case 'lost':
        // Update set_cards for the losing player
        if (player === 1 || player === 2) {
          const playerState = player === 1 ? state.p1 : state.p2;
          playerState.set_cards = event.data.set_cards || 0;
        }
        break;

      case 'action':
        // No state update, just record the event
        break;

      case 'interval':
        // No state update, just record the event
        break;

      case 'set_result':
        // No state update, just record the event
        break;

      case 'game_end':
        // No state update, just record the event
        break;

      default:
        // Unknown event type, just record it
        break;
    }

    // Create step object with deep copied state
    const step = {
      eventIdx: i,
      event: event,
      state: copyState()
    };

    steps.push(step);
  }

  return steps;
}
