"""Turn-based battle engine (pure logic - no rendering).

The UI calls `Battle.act(action)` with one of:
    ("move", index) ("scan",) ("capture", item_id) ("item", item_id, team_index)
    ("swap", team_index) ("flee",)
and displays the returned list of messages.  Battle.result becomes one of
"win", "loss", "fled", "captured" once the battle is over.
"""
from __future__ import annotations

import random

from .creature import Creature
from .data import RARITY_CAPTURE, GameData, Move

CAPTURE_MULT = {"pod": 1.0, "pod_plus": 1.8, "pod_max": 3.0}
STATUS_NAMES = {"burn": "burned", "freeze": "frozen", "poison": "poisoned", "stun": "stunned", "sleep": "asleep"}


def stage_mult(stage: int) -> float:
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


class Battle:
    def __init__(self, data: GameData, team: list[Creature], enemy: Creature, *, alpha: bool = False,
                 rng: random.Random | None = None, inventory=None, scanner_level: int = 0,
                 containment_level: int = 0):
        self.data = data
        self.team = team
        self.enemy = enemy
        self.alpha = alpha
        self.rng = rng or random.Random()
        self.inventory = inventory          # object with qty(id) / remove_item(id, n)
        self.scanner_level = scanner_level
        self.containment_level = containment_level
        self.active = next(i for i, c in enumerate(team) if not c.fainted)
        self.turns = 0
        self.result: str | None = None
        self.scanned = False
        self.participants = {self.active}
        for c in team:
            c.reset_battle_state()
        enemy.reset_battle_state()

    @property
    def me(self) -> Creature:
        return self.team[self.active]

    # ----------------------------------------------------------------- core
    def act(self, action: tuple) -> list[str]:
        if self.result:
            return []
        self.turns += 1
        msgs: list[str] = []
        kind = action[0]
        enemy_move = self._enemy_choice()

        if kind == "move":
            move = self.data.moves[self.me.moves[action[1]]]
            first_is_player = self._speed(self.me) >= self._speed(self.enemy)
            if first_is_player:
                msgs += self._use_move(self.me, self.enemy, move)
                if not self.enemy.fainted and not self.me.fainted:
                    msgs += self._use_move(self.enemy, self.me, enemy_move)
            else:
                msgs += self._use_move(self.enemy, self.me, enemy_move)
                if not self.me.fainted and not self.enemy.fainted:
                    msgs += self._use_move(self.me, self.enemy, move)
        else:
            if kind == "flee":
                if self.alpha:
                    msgs.append("The Alpha blocks your escape!")
                else:
                    chance = 0.5 + 0.5 * self._speed(self.me) / max(1, self._speed(self.enemy))
                    if self.rng.random() < min(0.95, chance):
                        self.result = "fled"
                        return msgs + ["You retreated safely to the landing zone."]
                    msgs.append("Couldn't get away!")
            elif kind == "scan":
                msgs += self._scan()
            elif kind == "capture":
                msgs += self._capture(action[1])
                if self.result:
                    return msgs
            elif kind == "item":
                msgs += self._use_item(action[1], action[2])
            elif kind == "swap":
                self.active = action[1]
                self.participants.add(self.active)
                msgs.append(f"Go, {self.me.name}!")
            if not self.enemy.fainted:
                msgs += self._use_move(self.enemy, self.me, enemy_move)

        msgs += self._end_of_turn()
        msgs += self._check_faints()
        return msgs

    # ---------------------------------------------------------------- moves
    def _speed(self, c: Creature) -> float:
        s = c.spd * stage_mult(c.stages["spd"])
        return s * (0.5 if c.status == "stun" else 1)

    def _enemy_choice(self) -> Move:
        moves = [self.data.moves[m] for m in self.enemy.moves]
        if self.enemy.hp < self.enemy.max_hp * 0.3:
            heals = [m for m in moves if m.effect == "heal"]
            if heals and self.rng.random() < 0.7:
                return heals[0]
        if self.rng.random() < 0.7:
            def score(m: Move):
                if m.power == 0:
                    return 25
                eff = self.data.effectiveness(m.type, self.me.species.types)
                stab = 1.25 if m.type in self.enemy.species.types else 1
                return m.power * eff * stab * m.accuracy / 100
            return max(moves, key=score)
        return self.rng.choice(moves)

    def _blocked_by_status(self, user: Creature) -> str | None:
        if user.status == "freeze":
            if self.rng.random() < 0.3:
                user.status = None
                return f"{user.name} thawed out!"  # thawing uses up the turn
            return f"{user.name} is frozen solid!"
        if user.status == "sleep":
            user.status_turns -= 1
            if user.status_turns <= 0:
                user.status = None
                return f"{user.name} woke up!"
            return f"{user.name} is fast asleep."
        if user.status == "stun" and self.rng.random() < 0.25:
            return f"{user.name} is stunned and can't move!"
        return None

    def damage(self, user: Creature, target: Creature, move: Move, crit: bool = False,
               roll: float = 1.0) -> tuple[int, float]:
        atk = user.atk * stage_mult(user.stages["atk"]) * (0.75 if user.status == "burn" else 1)
        dfn = target.defense * stage_mult(target.stages["def"])
        base = ((2 * user.level / 5 + 2) * move.power * atk / dfn) / 50 + 2
        eff = self.data.effectiveness(move.type, target.species.types)
        if eff > 1 and target.trait == "Adaptive":
            eff *= 0.75
        stab = 1.25 if move.type in user.species.types else 1.0
        dmg = base * eff * stab * roll * (1.5 if crit else 1) * (1.2 if user.trait == "Volatile" else 1)
        return max(1, int(dmg)), eff

    def _use_move(self, user: Creature, target: Creature, move: Move) -> list[str]:
        blocked = self._blocked_by_status(user)
        if blocked:
            return [blocked]
        msgs = [f"{user.name} used {move.name}!"]
        acc = move.accuracy * stage_mult(user.stages["acc"])
        if move.power > 0 or move.effect in ("sleep",):
            if self.rng.random() * 100 > acc:
                return msgs + ["...but it missed!"]
        if move.power > 0:
            crit_chance = 1 / 16 * (2 if user.trait == "Bioluminescent" else 1)
            crit = self.rng.random() < crit_chance
            dmg, eff = self.damage(user, target, move, crit, self.rng.uniform(0.85, 1.0))
            target.hp = max(0, target.hp - dmg)
            if crit:
                msgs.append("A critical hit!")
            if eff >= 2:
                msgs.append("It's super effective!")
            elif eff < 1:
                msgs.append("It's not very effective...")
            if move.effect == "drain":
                heal = dmg // 2
                user.hp = min(user.max_hp, user.hp + heal)
                msgs.append(f"{user.name} drained {heal} HP.")
            elif move.effect in STATUS_NAMES and not target.fainted and self.rng.random() < 0.3:
                msgs += self._apply_status(target, move.effect)
            elif move.effect and move.effect.startswith("debuff") and self.rng.random() < 0.4:
                stat = move.effect.split("_")[1]
                target.stages[stat] = max(-3, target.stages[stat] - 1)
                msgs.append(f"{target.name}'s {stat.upper()} fell!")
        else:
            eff = move.effect
            if eff == "heal":
                amount = int(user.max_hp * 0.4)
                user.hp = min(user.max_hp, user.hp + amount)
                msgs.append(f"{user.name} restored HP!")
            elif eff and eff.startswith("buff"):
                stat = eff.split("_")[1]
                user.stages[stat] = min(3, user.stages[stat] + 1)
                msgs.append(f"{user.name}'s {stat.upper()} rose!")
            elif eff == "sleep":
                msgs += self._apply_status(target, "sleep")
        return msgs

    def _apply_status(self, target: Creature, status: str) -> list[str]:
        if target.status:
            return []
        if target.trait == "Resilient":
            return [f"{target.name}'s Resilient trait blocks the effect!"]
        target.status = status
        target.status_turns = self.rng.randint(1, 3) if status == "sleep" else 0
        return [f"{target.name} is {STATUS_NAMES[status]}!"]

    def _end_of_turn(self) -> list[str]:
        msgs = []
        for c in (self.me, self.enemy):
            if c.fainted:
                continue
            if c.status in ("burn", "poison"):
                d = max(1, int(c.max_hp * (0.06 if c.status == "burn" else 0.08)))
                c.hp = max(0, c.hp - d)
                msgs.append(f"{c.name} is hurt by its {'burn' if c.status == 'burn' else 'poison'}.")
            if c.trait == "Regenerative" and not c.fainted and c.hp < c.max_hp:
                c.hp = min(c.max_hp, c.hp + max(1, int(c.max_hp * 0.06)))
                msgs.append(f"{c.name} regenerates.")
        return msgs

    def _check_faints(self) -> list[str]:
        msgs = []
        if self.enemy.fainted:
            msgs.append(f"The wild {self.enemy.name} fainted!")
            self.result = "win"
            msgs += self._award_xp()
            return msgs
        if self.me.fainted:
            msgs.append(f"{self.me.name} fainted!")
            nxt = next((i for i, c in enumerate(self.team) if not c.fainted), None)
            if nxt is None:
                self.result = "loss"
                msgs.append("Your team was defeated... emergency beacon activated.")
            else:
                self.active = nxt
                self.participants.add(nxt)
                msgs.append(f"Go, {self.me.name}!")
        return msgs

    def _award_xp(self) -> list[str]:
        msgs = []
        xp = self.enemy.xp_reward(self.alpha)
        for i, c in enumerate(self.team):
            if c.fainted:
                continue
            share = xp if i in self.participants else xp // 2
            msgs += c.gain_xp(share, self.data)
        return msgs

    # -------------------------------------------------------- non-move actions
    def _scan(self) -> list[str]:
        e = self.enemy
        self.scanned = True
        dna = 1 + self.scanner_level
        types = "/".join(e.species.types)
        return [f"Scanning {e.name}... [{types}] {e.species.kingdom}, {e.species.rarity.upper()}.",
                f"Trait: {e.trait}. Collected {dna} DNA sample{'s' if dna > 1 else ''}."]

    def capture_chance(self, pod: str) -> float:
        e = self.enemy
        hp_factor = 1 - (2 / 3) * (e.hp / e.max_hp)
        status_bonus = 1.6 if e.status in ("sleep", "freeze") else 1.25 if e.status else 1.0
        chance = (hp_factor * RARITY_CAPTURE[e.species.rarity] * CAPTURE_MULT[pod] * status_bonus
                  * (1 + 0.15 * self.containment_level) * (0.5 if self.alpha else 1.0))
        return max(0.02, min(0.95, chance))

    def _capture(self, pod: str) -> list[str]:
        if self.inventory is not None and not self.inventory.remove_item(pod, 1):
            return ["You don't have any of those pods!"]
        name = self.data.items[pod]["name"]
        msgs = [f"You launched a {name}!"]
        chance = self.capture_chance(pod)
        shakes = 0
        for _ in range(3):
            if self.rng.random() < chance ** (1 / 3):
                shakes += 1
        if shakes == 3:
            self.result = "captured"
            msgs.append(f"Containment successful! {self.enemy.name} was captured.")
            return msgs
        msgs.append(["It broke free immediately!", "Almost had it...", "So close! It broke free!"][shakes])
        return msgs

    def _use_item(self, item_id: str, idx: int) -> list[str]:
        target = self.team[idx]
        item = self.data.items[item_id]
        if item["kind"] == "heal" and target.fainted:
            return ["You can't heal a fainted creature - use a Revive Serum."]
        if item["kind"] == "revive" and not target.fainted:
            return [f"{target.name} hasn't fainted."]
        if self.inventory is not None and not self.inventory.remove_item(item_id, 1):
            return ["You don't have that item."]
        if item["kind"] == "heal":
            before = target.hp
            target.hp = min(target.max_hp, target.hp + item["value"])
            return [f"{target.name} recovered {target.hp - before} HP."]
        target.hp = target.max_hp // 2
        return [f"{target.name} was revived!"]
