"""The Orbital Research Lab - the game's hub.

Tabs: Galaxy (travel), Team, ExoDex journal, Research, Fabricator (crafting),
Missions and Data Log (battle history pulled straight from SQLite).
"""
from __future__ import annotations

import math

import pygame

from .. import ui
from ..app import Scene
from ..creature import xp_for_level
from ..data import RARITY_ORDER
from ..session import ACCEL_EVOLVE_COST, SYNTH_COST

TABS = ["Galaxy", "Team", "ExoDex", "Research", "Fabricator", "Missions", "Data Log"]
BIOME_COLOR = {"forest": (80, 190, 110), "ocean": (60, 130, 230), "desert": (220, 180, 110),
               "ice": (170, 225, 245), "lava": (240, 100, 50), "artificial": (170, 130, 240)}
KINGDOMS = [None, "Fauna", "Flora", "Fungoid", "Microbe", "Mechanoid", "Crystalline"]


class LabScene(Scene):
    def __init__(self, app, tab: str = "Galaxy"):
        super().__init__(app)
        self.s = app.session
        self.data = self.s.data
        self.tab = tab
        self.sel_planet = 1
        self.sel_creature = None
        self.sel_species = 1
        self.dex_page = 0
        self.dex_kingdom = None
        self.scroll = 0
        self.rebuild()

    # ------------------------------------------------------------- helpers
    def msg(self, result):
        ok, text = result
        self.app.toast(text, ui.GOOD if ok else ui.WARN)
        self.rebuild()

    def set_tab(self, tab):
        self.tab = tab
        self.scroll = 0
        self.rebuild()

    def rebuild(self):
        B = ui.Button
        self.buttons = []
        for i, t in enumerate(TABS):
            self.buttons.append(B((20, 90 + i * 52, 170, 44), t, lambda t=t: self.set_tab(t), size=18))
        self.buttons.append(B((20, ui.H - 110, 170, 40), "Save Game", self._save, size=17))
        self.buttons.append(B((20, ui.H - 60, 170, 40), "Title Screen", self._title, size=17))
        getattr(self, "_build_" + self.tab.lower().replace(" ", "_"))()

    def _save(self):
        self.s.save()
        self.app.toast("Progress saved to SQLite.", ui.GOOD)

    def _title(self):
        self.s.save()
        self.s.db.close()
        self.app.session = None
        from .title import TitleScene
        self.app.switch(TitleScene(self.app))

    # ------------------------------------------------------------- builders
    def _build_galaxy(self):
        p = self.data.planets[self.sel_planet]
        unlocked = self.s.unlocked(p)
        self.buttons.append(ui.Button((ui.W - 330, ui.H - 90, 290, 50),
                                      (f"Launch to {p.name}" + (" (free shuttle)" if p.id == 1 else " (1 Fuel)")) if unlocked else "Locked",
                                      self._launch, enabled=unlocked))

    def _launch(self):
        ok, text = self.s.travel(self.sel_planet)
        self.app.toast(text, ui.GOOD if ok else ui.WARN)
        if ok:
            from .planet import PlanetScene
            self.app.switch(PlanetScene(self.app))

    def _creatures(self):
        return self.s.db.all_creatures()

    def _build_team(self):
        cs = self._creatures()
        if self.sel_creature is None and cs:
            self.sel_creature = cs[0].id
        c = next((c for c in cs if c.id == self.sel_creature), None)
        if not c:
            return
        x, y = 760, 560
        B = ui.Button
        in_team = c.team_slot is not None
        self.buttons += [
            B((x, y, 160, 38), "Make Lead", lambda: (self.s.set_lead(c.id), self.rebuild()), enabled=in_team, size=16),
            B((x + 170, y, 160, 38), "To Storage" if in_team else "To Team",
              lambda: self.msg(self.s.swap_team(c.id)), size=16),
            B((x + 340, y, 160, 38), f"Sequence ({self.s.sequence_cost()} DNA)",
              lambda: self.msg(self.s.sequence_genome(c.id)), size=15),
            B((x, y + 46, 160, 38), "Use MedGel", lambda: self.msg(self.s.use_item_on("medgel", c.id)),
              enabled=self.s.db.qty("medgel") > 0, size=16),
            B((x + 170, y + 46, 160, 38), "Revive Serum", lambda: self.msg(self.s.use_item_on("revive", c.id)),
              enabled=self.s.db.qty("revive") > 0 and c.fainted, size=16),
            B((x + 340, y + 46, 160, 38), f"Evolve ({ACCEL_EVOLVE_COST} DNA)",
              lambda: self.msg(self.s.accelerate_evolution(c.id)), enabled=bool(c.species.evolves_to), size=15),
        ]
        self.buttons.append(B((x + 340, 90, 160, 34), "Heal All (free)", self._heal, size=15))

    def _heal(self):
        self.s.heal_team()
        self.s.save()
        self.app.toast("Med Bay restored every specimen.", ui.GOOD)

    def _build_exodex(self):
        B = ui.Button
        for i, k in enumerate(KINGDOMS):
            self.buttons.append(B((220 + i * 92, 84, 86, 30), k or "All", lambda k=k: self._dex_filter(k), size=14))
        self.buttons.append(B((220, ui.H - 50, 90, 34), "< Prev", lambda: self._dex_page(-1), size=15))
        self.buttons.append(B((320, ui.H - 50, 90, 34), "Next >", lambda: self._dex_page(1), size=15))
        sp = self.data.species[self.sel_species]
        self.buttons.append(B((ui.W - 330, ui.H - 60, 290, 40), f"Synthesize clone ({SYNTH_COST} DNA)",
                              lambda: self.msg(self.s.synthesize(sp.id)), size=15))

    def _dex_rows(self):
        return self.s.db.journal(self.dex_kingdom)

    def _dex_filter(self, k):
        self.dex_kingdom = k
        self.dex_page = 0
        self.rebuild()

    def _dex_page(self, d):
        pages = max(1, math.ceil(len(self._dex_rows()) / 40))
        self.dex_page = (self.dex_page + d) % pages

    def _build_research(self):
        for i, r in enumerate(self.s.db.research_rows()):
            x, y = 220 + (i % 2) * 520, 100 + (i // 2) * 190
            maxed = r["level"] >= r["max_level"]
            self.buttons.append(ui.Button((x + 320, y + 120, 170, 40),
                                          "MAXED" if maxed else f"Upgrade: {self.s.research_cost(r['id'])} RP",
                                          lambda rid=r["id"]: self.msg(self.s.upgrade_research(rid)),
                                          enabled=not maxed, size=15))

    def _build_fabricator(self):
        for i, r in enumerate(self.data.recipes):
            y = 100 + i * 58
            self.buttons.append(ui.Button((700, y + 8, 120, 38), "Craft", lambda rid=r["id"]: self.msg(self.s.craft(rid)),
                                          enabled=self.s.can_craft(r), size=16))
        self.buttons.append(ui.Button((ui.W - 250, ui.H - 60, 220, 40), "Use Bio Lure on next landing",
                                      self._lure, enabled=self.s.db.qty("lure") > 0, size=14))

    def _lure(self):
        if self.s.use_lure():
            self.app.toast("Bio Lure primed: encounters doubled for 60 steps.", ui.GOOD)
        self.rebuild()

    def _build_missions(self):
        for i, m in enumerate(self.s.db.missions()[self.scroll:self.scroll + 9]):
            y = 100 + i * 66
            done = m["progress"] >= m["goal"]
            self.buttons.append(ui.Button((ui.W - 180, y + 12, 140, 38), "Claimed" if m["claimed"] else "Claim",
                                          lambda mid=m["id"]: self.msg(self.s.claim_mission(mid)),
                                          enabled=done and not m["claimed"], size=16))
        self.buttons.append(ui.Button((220, ui.H - 50, 90, 34), "Up", lambda: self._scroll(-9), size=15))
        self.buttons.append(ui.Button((320, ui.H - 50, 90, 34), "Down", lambda: self._scroll(9), size=15))

    def _scroll(self, d):
        self.scroll = max(0, min(len(self.data.missions) - 9, self.scroll + d))
        self.rebuild()

    def _build_data_log(self):
        pass

    # ------------------------------------------------------------- events
    def handle(self, event):
        if super().handle(event):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self.tab == "Galaxy":
                for p in self.data.planets.values():
                    if math.dist(self._planet_pos(p), (mx, my)) < 40:
                        self.sel_planet = p.id
                        self.rebuild()
            elif self.tab == "Team":
                for i, c in enumerate(self._creatures()[self.scroll:self.scroll + 10]):
                    if pygame.Rect(220, 130 + i * 56, 500, 50).collidepoint(mx, my):
                        self.sel_creature = c.id
                        self.rebuild()
            elif self.tab == "ExoDex":
                rows = self._dex_rows()[self.dex_page * 40:(self.dex_page + 1) * 40]
                for i, r in enumerate(rows):
                    if self._dex_cell(i).collidepoint(mx, my):
                        self.sel_species = r["id"]
                        self.rebuild()
        if event.type == pygame.MOUSEWHEEL and self.tab == "Team":
            self.scroll = max(0, min(max(0, len(self._creatures()) - 10), self.scroll - event.y))
        return False

    def _planet_pos(self, p):
        a = p.id / 6 * math.tau + self.app.time * 0.03
        r = 120 + p.id * 30
        return 560 + math.cos(a) * r * 1.35, 380 + math.sin(a) * r * 0.75

    def _dex_cell(self, i):
        return pygame.Rect(220 + (i % 8) * 80, 124 + (i // 8) * 104, 74, 98)

    # ------------------------------------------------------------- drawing
    def draw(self, surf):
        self.app.draw_starfield(surf)
        p = self.s.player
        ui.panel(surf, pygame.Rect(0, 0, ui.W, 64), (12, 18, 34), ui.LINE, 0)
        ui.text(surf, "ORBITAL RESEARCH LAB", (20, 18), 24, ui.ACCENT, bold=True)
        counts = self.s.db.dex_counts()
        info = (f"{p['name']}   |   Rank {counts['scanned']}   |   RP {p['rp']}   |   Fuel {self.s.db.qty('fuel')}"
                f"   |   ExoDex {counts['scanned']}/{len(self.data.species)}   |   Caught {counts['captured']}")
        ui.text(surf, info, (ui.W - 20, 22), 17, ui.TEXT, right=True)
        for b in self.buttons:
            if b.label == self.tab:
                pygame.draw.rect(surf, ui.ACCENT, b.rect.inflate(4, 4), 2, border_radius=10)
            b.draw(surf)
        getattr(self, "_draw_" + self.tab.lower().replace(" ", "_"))(surf)

    def _draw_galaxy(self, surf):
        cx, cy = 560, 380
        for r in range(60, 0, -6):
            pygame.draw.circle(surf, (255, 200 - r, 80 - r // 2), (cx, cy), r)
        for p in self.data.planets.values():
            r = 120 + p.id * 30
            pygame.draw.ellipse(surf, (34, 44, 70), (cx - r * 1.35, cy - r * 0.75, r * 2.7, r * 1.5), 1)
        for p in self.data.planets.values():
            x, y = self._planet_pos(p)
            col = BIOME_COLOR[p.biome] if self.s.unlocked(p) else (60, 66, 84)
            pygame.draw.circle(surf, col, (int(x), int(y)), 22 + p.id * 2)
            if p.id == self.sel_planet:
                pygame.draw.circle(surf, ui.ACCENT, (int(x), int(y)), 32 + p.id * 2, 2)
            ui.text(surf, p.name, (x, y + 38), 15, ui.TEXT, center=True)
        p = self.data.planets[self.sel_planet]
        r = pygame.Rect(ui.W - 340, 90, 310, 540)
        ui.panel(surf, r)
        ui.text(surf, p.name, (r.x + 18, r.y + 14), 28, BIOME_COLOR[p.biome], bold=True)
        ui.text(surf, f"{p.biome.title()} world  |  Lv {p.min_level}-{p.max_level}", (r.x + 18, r.y + 52), 16, ui.MUTED)
        y = ui.text_block(surf, p.description, r.x + 18, r.y + 84, r.w - 36, 16)
        y += 10
        ui.text(surf, "Dominant lifeform types:", (r.x + 18, y), 15, ui.MUTED)
        bx = r.x + 18
        for t in p.types:
            bx = ui.type_badge(surf, t, (bx, y + 24))
        y += 62
        found = self.s.db.count_scanned_where("d.planet_id = ?", (p.id,))
        ui.text(surf, f"Species scanned here: {found}", (r.x + 18, y), 16)
        ui.text(surf, f"Resource: {self.data.items[p.material]['name']}", (r.x + 18, y + 26), 16)
        beaten = str(p.id) in self.s.player["alphas_beaten"].split(",")
        ui.text(surf, f"Alpha: {self.data.species[p.alpha_species].name if beaten else '???'} (Lv {p.alpha_level})",
                (r.x + 18, y + 52), 16, ui.GOOD if beaten else ui.WARN)
        if not self.s.unlocked(p):
            ui.text(surf, f"Unlocks at Explorer Rank {p.unlock_rank}", (r.x + 18, y + 90), 17, ui.BAD, bold=True)

    def _draw_team(self, surf):
        cs = self._creatures()
        ui.text(surf, f"Team & Storage ({len(cs)} specimens)  -  scroll for more", (220, 92), 18, ui.MUTED)
        for i, c in enumerate(cs[self.scroll:self.scroll + 10]):
            r = pygame.Rect(220, 130 + i * 56, 500, 50)
            ui.panel(surf, r, ui.PANEL_HI if c.id == self.sel_creature else ui.PANEL)
            surf.blit(ui.creature_sprite(c.species, 46, c.aberrant), (r.x + 4, r.y + 2))
            tag = f"TEAM {c.team_slot + 1}" if c.team_slot is not None else "LAB"
            ui.text(surf, f"{c.name}  Lv{c.level}", (r.x + 58, r.y + 6), 17, bold=True)
            ui.text(surf, tag, (r.x + 58, r.y + 28), 12, ui.ACCENT if c.team_slot is not None else ui.MUTED)
            ui.bar(surf, (r.x + 300, r.y + 20, 180, 10), c.hp / c.max_hp, ui.hp_color(c.hp / c.max_hp))
            ui.text(surf, f"{c.hp}/{c.max_hp}", (r.x + 300, r.y + 32), 12, ui.MUTED)
        c = next((c for c in cs if c.id == self.sel_creature), None)
        if not c:
            return
        r = pygame.Rect(740, 130, 520, 420)
        ui.panel(surf, r)
        surf.blit(ui.creature_sprite(c.species, 180, c.aberrant), (r.x + 10, r.y + 10))
        x = r.x + 200
        ui.text(surf, c.name + ("  *ABERRANT*" if c.aberrant else ""), (x, r.y + 16), 26, bold=True)
        bx = x
        for t in c.species.types:
            bx = ui.type_badge(surf, t, (bx, r.y + 54))
        ui.text(surf, f"{c.species.kingdom}  |  {c.species.rarity.title()}", (x, r.y + 84), 15,
                ui.RARITY_COLOR[c.species.rarity])
        ui.text(surf, f"Level {c.level}   Trait: {c.trait}", (x, r.y + 108), 16)
        ui.text(surf, self.data.traits[c.trait], (x, r.y + 130), 14, ui.MUTED)
        nxt, cur = xp_for_level(c.level + 1), xp_for_level(c.level)
        ui.bar(surf, (x, r.y + 156, 280, 8), (c.xp - cur) / max(1, nxt - cur), ui.ACCENT)
        y = r.y + 200
        for label, val, iv in (("HP", c.max_hp, c.ivs["hp"]), ("ATK", c.atk, c.ivs["atk"]),
                               ("DEF", c.defense, c.ivs["def"]), ("SPD", c.spd, c.ivs["spd"])):
            ui.text(surf, f"{label:<4}{val:>4}", (r.x + 20, y), 16)
            ui.bar(surf, (r.x + 110, y + 5, 150, 8), iv / 15, (150, 120, 255))
            ui.text(surf, f"gene {iv}/15", (r.x + 268, y), 13, ui.MUTED)
            y += 26
        ui.text(surf, "Moves", (r.x + 360, r.y + 200), 15, ui.MUTED)
        for i, mid in enumerate(c.moves):
            m = self.data.moves[mid]
            ui.text(surf, m.name, (r.x + 360, r.y + 224 + i * 24), 15, ui.TYPE_COLOR.get(m.type, ui.TEXT))
        d = self.s.db.discovery(c.species.id)
        ui.text(surf, f"{c.species.name} DNA in storage: {d['dna'] if d else 0}", (r.x + 20, r.y + 320), 15)
        if c.species.evolves_to:
            ui.text(surf, f"Evolves at Lv {c.species.evolve_level}", (r.x + 20, r.y + 346), 15, ui.WARN)

    def _draw_exodex(self, surf):
        rows = self._dex_rows()
        page = rows[self.dex_page * 40:(self.dex_page + 1) * 40]
        for i, row in enumerate(page):
            cell = self._dex_cell(i)
            sp = self.data.species[row["id"]]
            ui.panel(surf, cell, ui.PANEL_HI if row["id"] == self.sel_species else ui.PANEL, radius=6)
            if row["seen"]:
                surf.blit(ui.creature_sprite(sp, 64, silhouette=not row["scanned"]), (cell.x + 5, cell.y + 4))
            ui.text(surf, f"#{sp.id:03d}", (cell.x + 4, cell.bottom - 30), 11, ui.MUTED)
            ui.text(surf, sp.name if row["scanned"] else "???", (cell.x + 4, cell.bottom - 17), 11,
                    ui.GOOD if row["captured"] else ui.TEXT)
        pages = max(1, math.ceil(len(rows) / 40))
        ui.text(surf, f"Page {self.dex_page + 1}/{pages}", (430, ui.H - 44), 16, ui.MUTED)
        sp = self.data.species[self.sel_species]
        row = next(r for r in self.s.db.journal() if r["id"] == sp.id)
        r = pygame.Rect(ui.W - 340, 84, 320, 560)
        ui.panel(surf, r)
        if not row["seen"]:
            ui.text(surf, f"#{sp.id:03d}  Unknown lifeform", (r.x + 16, r.y + 16), 20, ui.MUTED)
            ui.text_block(surf, "Encounter this species in the field to log it.", r.x + 16, r.y + 50, r.w - 32, 15)
            return
        surf.blit(ui.creature_sprite(sp, 200, silhouette=not row["scanned"]), (r.centerx - 100, r.y + 6))
        ui.text(surf, f"#{sp.id:03d} {sp.name if row['scanned'] else '???'}", (r.x + 16, r.y + 210), 22, bold=True)
        if not row["scanned"]:
            ui.text_block(surf, "Seen but not scanned. Use SCAN in battle to record data.", r.x + 16, r.y + 244,
                          r.w - 32, 15, ui.MUTED)
            return
        bx = r.x + 16
        for t in sp.types:
            bx = ui.type_badge(surf, t, (bx, r.y + 244))
        ui.text(surf, f"{sp.kingdom}  |  {sp.rarity.title()}", (r.x + 16, r.y + 274), 15, ui.RARITY_COLOR[sp.rarity])
        ui.text(surf, f"Height {sp.height_m} m   Mass {sp.mass_kg} kg", (r.x + 16, r.y + 298), 15, ui.MUTED)
        ui.text(surf, "Habitat: " + ", ".join(b.title() for b in sp.biomes), (r.x + 16, r.y + 320), 15, ui.MUTED)
        y = ui.text_block(surf, sp.description, r.x + 16, r.y + 350, r.w - 32, 15)
        ui.text(surf, f"Base stats  HP {sp.hp}  ATK {sp.atk}  DEF {sp.defense}  SPD {sp.spd}", (r.x + 16, y + 8), 14)
        if sp.evolves_to:
            nxt = self.data.species[sp.evolves_to]
            ui.text(surf, f"Evolves into #{nxt.id:03d} at Lv {sp.evolve_level}", (r.x + 16, y + 32), 14, ui.WARN)
        ui.text(surf, f"DNA samples: {row['dna']}   {'CAPTURED' if row['captured'] else ''}", (r.x + 16, y + 56), 15,
                ui.GOOD if row["captured"] else ui.TEXT)

    def _draw_research(self, surf):
        ui.text(surf, f"Research Points available: {self.s.player['rp']}", (220, 80), 18, ui.ACCENT)
        for i, r in enumerate(self.s.db.research_rows()):
            x, y = 220 + (i % 2) * 520, 100 + (i // 2) * 190
            box = pygame.Rect(x, y + 10, 500, 170)
            ui.panel(surf, box)
            ui.text(surf, r["name"], (x + 18, y + 24), 22, bold=True)
            ui.text_block(surf, r["description"], x + 18, y + 60, 460, 15, ui.MUTED)
            for k in range(r["max_level"]):
                pygame.draw.rect(surf, ui.ACCENT if k < r["level"] else ui.LINE, (x + 18 + k * 34, y + 132, 28, 14),
                                 border_radius=4)

    def _draw_fabricator(self, surf):
        ui.text(surf, "FABRICATOR  -  combine materials gathered on planets", (220, 76), 18, ui.ACCENT)
        for i, r in enumerate(self.data.recipes):
            y = 100 + i * 58
            ui.panel(surf, pygame.Rect(220, y, 610, 54))
            ui.text(surf, f"{r['qty']}x {self.data.items[r['output']]['name']}", (236, y + 8), 18, bold=True)
            parts = [f"{v} {self.data.items[k]['name']} ({self.s.db.qty(k)})" for k, v in r["inputs"].items()]
            ui.text(surf, "  +  ".join(parts), (236, y + 31), 13, ui.MUTED)
        box = pygame.Rect(860, 100, 400, 540)
        ui.panel(surf, box)
        ui.text(surf, "CARGO HOLD", (876, 112), 18, ui.ACCENT, bold=True)
        for i, (item, qty) in enumerate(self.s.db.inventory()):
            ui.text(surf, f"{item['name']}", (876, 146 + i * 26), 16)
            ui.text(surf, f"x{qty}", (box.right - 16, 146 + i * 26), 16, ui.ACCENT, right=True)

    def _draw_missions(self, surf):
        for i, m in enumerate(self.s.db.missions()[self.scroll:self.scroll + 9]):
            y = 100 + i * 66
            r = pygame.Rect(220, y, ui.W - 240, 60)
            ui.panel(surf, r, (20, 40, 36) if m["claimed"] else ui.PANEL)
            ui.text(surf, m["title"], (236, y + 6), 18, bold=True)
            ui.text(surf, m["description"], (236, y + 32), 14, ui.MUTED)
            ui.bar(surf, (640, y + 14, 260, 12), m["progress"] / m["goal"], ui.ACCENT)
            ui.text(surf, f"{m['progress']}/{m['goal']}", (640, y + 32), 13, ui.MUTED)
            ui.text(surf, f"+{m['reward_rp']} RP, {m['reward_qty']}x {self.data.items[m['reward_item']]['name']}",
                    (920, y + 20), 14, ui.WARN)

    def _draw_data_log(self, surf):
        ui.text(surf, "DATA LOG  -  live queries against your save database", (220, 80), 18, ui.ACCENT)
        db = self.s.db
        q = db.execute("SELECT COUNT(*) n, SUM(result='win') w, SUM(result='captured') c, SUM(result='loss') l,"
                       " SUM(result='fled') f FROM battle_history").fetchone()
        ui.text(surf, f"Battles: {q['n']}   Wins: {q['w'] or 0}   Captures: {q['c'] or 0}   Losses: {q['l'] or 0}"
                      f"   Fled: {q['f'] or 0}   Steps walked: {self.s.player['steps']}", (220, 112), 16)
        ui.text(surf, "Recent field reports", (220, 150), 16, ui.MUTED)
        for i, b in enumerate(db.recent_battles(10)):
            planet = self.data.planets[b["planet_id"]].name if b["planet_id"] else "-"
            col = {"win": ui.GOOD, "captured": ui.ACCENT, "loss": ui.BAD}.get(b["result"], ui.MUTED)
            ui.text(surf, f"{b['at'][:16].replace('T', ' ')}   {planet:<14} {b['species_name']} Lv{b['enemy_level']}",
                    (220, 178 + i * 26), 15)
            ui.text(surf, f"{b['result'].upper()} in {b['turns']} turns", (760, 178 + i * 26), 15, col)
        ui.text(surf, "Discoveries by rarity", (220, 460), 16, ui.MUTED)
        rows = db.execute("SELECT s.rarity, COUNT(*) total, SUM(COALESCE(d.scanned,0)) found FROM species s"
                          " LEFT JOIN discoveries d ON d.species_id = s.id GROUP BY s.rarity").fetchall()
        rows = sorted(rows, key=lambda r: RARITY_ORDER.index(r["rarity"]))
        for i, r in enumerate(rows):
            y = 490 + i * 30
            ui.text(surf, r["rarity"].title(), (220, y), 15, ui.RARITY_COLOR[r["rarity"]])
            ui.bar(surf, (340, y + 5, 400, 12), (r["found"] or 0) / r["total"], ui.RARITY_COLOR[r["rarity"]])
            ui.text(surf, f"{r['found'] or 0}/{r['total']}", (752, y), 15, ui.MUTED)
