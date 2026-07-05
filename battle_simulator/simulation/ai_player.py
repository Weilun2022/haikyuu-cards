"""Rule-based AI decision maker for game simulation."""
from ..engine.card import Card
from ..engine.game_state import PlayerState, GameState


class AIPlayer:
    """
    Greedy rule-based AI. Priority:
    1. Fill empty high-value zones (atk > blk > rcv > srv > tos)
    2. Replace weaker field card if hand card is significantly better
    3. Activate skills when guts allows and benefit > cost
    """

    ZONE_PRIORITY = ['atk', 'blk', 'rcv', 'srv', 'tos']

    def decide_plays(self, player: PlayerState, opponent: PlayerState) -> dict:
        """
        Returns {'place': {zone: Card|None}, 'activate_skills': [Card]}
        'place' maps zone → card to deploy from hand (None = don't change)
        """
        placements = {}
        hand_copy = list(player.hand)

        for zone in self.ZONE_PRIORITY:
            best = self._best_card_for_zone(hand_copy, zone, player, opponent)
            if best is not None:
                current = player.field.get(zone)
                current_val = getattr(current, zone, 0) if current else 0
                new_val = getattr(best, zone, 0)
                if new_val > current_val:
                    placements[zone] = best
                    hand_copy.remove(best)

        # Decide which skills to activate (greedy: activate if affordable and beneficial)
        skills_to_activate = []
        for card in placements.values():
            if card and card.guts_cost <= player.guts and card.has_tag('登場'):
                skills_to_activate.append(card)

        return {'place': placements, 'activate_skills': skills_to_activate}

    def _best_card_for_zone(self, hand: list[Card], zone: str,
                             player: PlayerState, opponent: PlayerState) -> Card | None:
        """Find best card from hand for given zone."""
        candidates = [c for c in hand if c.category == 'CHARACTER' and getattr(c, zone, 0) > 0]
        if not candidates:
            return None
        return max(candidates, key=lambda c: getattr(c, zone, 0))

    def decide_event_activation(self, player: PlayerState, trigger: str) -> list[Card]:
        """Return event cards to activate at given trigger."""
        activatable = []
        for card in player.field.get('evt', []):
            if card.has_tag(trigger) and card.guts_cost <= player.guts:
                activatable.append(card)
        return activatable
