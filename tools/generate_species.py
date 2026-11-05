"""Generate the ExoDex static dataset (species, moves, planets, items, recipes,
missions, research) into data/gamedata.json.

The generator is deterministic (fixed seed), so the committed JSON can always be
reproduced:  python tools/generate_species.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 20261105
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "gamedata.json"

TYPES = ["THERMAL", "CRYO", "HYDRO", "LITHIC", "FLORA", "SYNTH", "VOLT", "PSIONIC"]

# attacker -> (strong against, weak against)
TYPE_CHART = {
    "THERMAL": (["CRYO", "FLORA", "SYNTH"], ["HYDRO", "LITHIC", "THERMAL"]),
    "CRYO": (["FLORA", "HYDRO", "VOLT"], ["THERMAL", "SYNTH", "CRYO"]),
    "HYDRO": (["THERMAL", "LITHIC", "SYNTH"], ["FLORA", "VOLT", "HYDRO"]),
    "LITHIC": (["THERMAL", "VOLT", "CRYO"], ["HYDRO", "FLORA"]),
    "FLORA": (["HYDRO", "LITHIC"], ["THERMAL", "CRYO", "SYNTH"]),
    "SYNTH": (["CRYO", "FLORA", "PSIONIC"], ["VOLT", "THERMAL"]),
    "VOLT": (["HYDRO", "SYNTH"], ["LITHIC", "FLORA", "VOLT"]),
    "PSIONIC": (["HYDRO", "FLORA", "LITHIC"], ["SYNTH", "PSIONIC"]),
}

TYPE_HUE = {"THERMAL": 12, "CRYO": 195, "HYDRO": 215, "LITHIC": 32,
            "FLORA": 120, "SYNTH": 280, "VOLT": 52, "PSIONIC": 315}

PLANETS = [
    dict(id=1, name="Verdance", biome="forest", types=["FLORA", "PSIONIC", "HYDRO"],
         min_level=2, max_level=6, unlock_rank=0, seed=1101,
         description="A humid super-Earth wrapped in bioluminescent canopy. Ideal first survey site."),
    dict(id=2, name="Thalassa", biome="ocean", types=["HYDRO", "VOLT", "FLORA"],
         min_level=5, max_level=10, unlock_rank=0, seed=2202,
         description="A global ocean dotted with coral archipelagos and storm-charged reefs."),
    dict(id=3, name="Dune Kappa", biome="desert", types=["LITHIC", "THERMAL", "PSIONIC"],
         min_level=9, max_level=15, unlock_rank=8, seed=3303,
         description="Silica dunes over a buried crystal lattice. Life hides beneath the sand."),
    dict(id=4, name="Glacia Prime", biome="ice", types=["CRYO", "HYDRO", "PSIONIC"],
         min_level=13, max_level=20, unlock_rank=16, seed=4404,
         description="Frozen crust over a subsurface sea, like Europa. Cryovolcanoes vent nutrients."),
    dict(id=5, name="Pyros IX", biome="lava", types=["THERMAL", "LITHIC", "VOLT"],
         min_level=18, max_level=26, unlock_rank=28, seed=5505,
         description="A tidally-locked lava world. Extremophiles thrive in sulfur vents."),
    dict(id=6, name="Machina Nexus", biome="artificial", types=["SYNTH", "VOLT", "PSIONIC"],
         min_level=23, max_level=32, unlock_rank=45, seed=6606,
         description="A derelict Dyson-ring habitat. Its self-replicating machines evolved into ecosystems."),
]

KINGDOMS = ["Fauna", "Flora", "Fungoid", "Microbe", "Mechanoid", "Crystalline"]
KINGDOM_BY_TYPE = {
    "THERMAL": ["Fauna", "Microbe", "Crystalline"],
    "CRYO": ["Fauna", "Crystalline", "Microbe"],
    "HYDRO": ["Fauna", "Flora", "Microbe"],
    "LITHIC": ["Crystalline", "Fauna", "Fungoid"],
    "FLORA": ["Flora", "Fungoid", "Fauna"],
    "SYNTH": ["Mechanoid", "Mechanoid", "Crystalline"],
    "VOLT": ["Fauna", "Mechanoid", "Microbe"],
    "PSIONIC": ["Fungoid", "Fauna", "Microbe"],
}

PREFIX = {
    "THERMAL": ["Pyr", "Ign", "Cind", "Mag", "Sulf", "Ash", "Ember", "Scor", "Calor", "Volc", "Blaz", "Fum"],
    "CRYO": ["Glac", "Frig", "Cryo", "Boreal", "Rim", "Niv", "Hail", "Pol", "Gel", "Sleet", "Tundr", "Aur"],
    "HYDRO": ["Aqu", "Thal", "Pel", "Mar", "Brin", "Tid", "Kelp", "Neri", "Hydr", "Coral", "Abys", "Lag"],
    "LITHIC": ["Lith", "Petr", "Silic", "Basal", "Quar", "Ferr", "Dun", "Grav", "Obsid", "Crag", "Ore", "Slat"],
    "FLORA": ["Verd", "Phyll", "Sylv", "Myc", "Spor", "Thorn", "Rhiz", "Bloss", "Fern", "Mos", "Lich", "Pet"],
    "SYNTH": ["Mech", "Cyb", "Nan", "Servo", "Alloy", "Proto", "Robo", "Gear", "Chrom", "Nex", "Bit", "Ferro"],
    "VOLT": ["Volt", "Zap", "Ion", "Arc", "Flux", "Ohm", "Spark", "Tesl", "Plasm", "Stat", "Ampe", "Jolt"],
    "PSIONIC": ["Psi", "Neur", "Astr", "Myst", "Ment", "Vey", "Lumi", "Ethr", "Omn", "Dream", "Cogn", "Nyx"],
}
MID = ["a", "o", "i", "e", "u", "ae", "y", "io", "ar", "or", "il", "en"]
SUFFIX = [
    ["ling", "pod", "mite", "kit", "let", "sprout", "bit", "nub", "spore", "seed", "pup", "fry"],
    ["ix", "orn", "ax", "ra", "iss", "ith", "ox", "ant", "ul", "ek", "yx", "us"],
    ["athon", "odon", "aurus", "oloth", "everon", "arch", "oleth", "imaw", "agon", "ortex", "erion", "onyx"],
]

ADJ = {
    "Fauna": ["six-limbed grazer", "burrowing predator", "gliding forager", "armored scavenger", "pack hunter",
              "filter-feeding drifter", "ambush stalker", "migratory runner"],
    "Flora": ["photosynthetic colony", "carnivorous bloom", "drifting seed-pod", "rooted giant",
              "vine network", "chemosynthetic reed"],
    "Fungoid": ["mycelial mat", "spore-casting cap", "symbiotic lichen", "hive-minded mold"],
    "Microbe": ["extremophile swarm", "colonial cell-cluster", "bioluminescent plankton", "viral-like replicator"],
    "Mechanoid": ["self-repairing drone", "nanite aggregate", "salvage-built crawler", "autonomous sentinel"],
    "Crystalline": ["silicon-based lattice", "piezoelectric shard-beast", "growing geode", "resonant crystal form"],
}
TRAIT_FACT = {
    "THERMAL": "metabolizes sulfur compounds near magma vents",
    "CRYO": "produces antifreeze proteins to survive at -180 C",
    "HYDRO": "breathes through filament gills that extract dissolved oxygen",
    "LITHIC": "grows by depositing minerals in concentric layers",
    "FLORA": "converts starlight into sugars with a violet pigment",
    "SYNTH": "copies its own blueprint using scavenged metals",
    "VOLT": "stores bioelectric charge in stacked electrocyte cells",
    "PSIONIC": "communicates through low-frequency neural fields",
}

MOVES_BY_TYPE = {
    "THERMAL": [("Ember Spit", 35, 100, None), ("Heat Wave", 55, 95, "burn"), ("Magma Fang", 70, 90, None),
                ("Solar Flare", 95, 80, "burn"), ("Thermal Shield", 0, 100, "buff_def"), ("Inferno Core", 120, 70, None)],
    "CRYO": [("Frost Nip", 35, 100, None), ("Ice Shard", 55, 95, None), ("Hail Barrage", 70, 90, "freeze"),
             ("Absolute Zero", 100, 75, "freeze"), ("Frost Armor", 0, 100, "buff_def"), ("Glacial Lance", 115, 70, None)],
    "HYDRO": [("Bubble Jet", 35, 100, None), ("Tidal Slap", 55, 95, None), ("Riptide", 70, 90, "debuff_spd"),
              ("Abyssal Surge", 95, 85, None), ("Regenerate", 0, 100, "heal"), ("Tsunami", 120, 70, None)],
    "LITHIC": [("Pebble Toss", 35, 100, None), ("Sand Blast", 50, 95, "debuff_acc"), ("Boulder Crash", 75, 85, None),
               ("Tectonic Slam", 100, 80, None), ("Crystal Harden", 0, 100, "buff_def"), ("Meteor Fall", 120, 70, None)],
    "FLORA": [("Vine Lash", 35, 100, None), ("Spore Cloud", 45, 95, "poison"), ("Thorn Volley", 70, 90, None),
              ("Photon Bloom", 95, 85, None), ("Photosynthesis", 0, 100, "heal"), ("World Root", 115, 75, None)],
    "SYNTH": [("Laser Ping", 35, 100, None), ("Nanite Swarm", 55, 95, "poison"), ("Railgun", 80, 85, None),
              ("Overclock", 0, 100, "buff_atk"), ("Self Repair", 0, 100, "heal"), ("Singularity Cannon", 120, 70, None)],
    "VOLT": [("Static Zap", 35, 100, "stun"), ("Arc Bolt", 55, 95, None), ("Ion Storm", 75, 90, "stun"),
             ("Plasma Rail", 95, 85, None), ("Charge Up", 0, 100, "buff_atk"), ("Gigavolt", 120, 70, "stun")],
    "PSIONIC": [("Mind Prick", 35, 100, None), ("Neural Pulse", 55, 95, "debuff_atk"), ("Dream Eater", 70, 90, "drain"),
                ("Astral Lance", 95, 85, None), ("Hypnotize", 0, 75, "sleep"), ("Cosmic Mind", 120, 70, None)],
}
NEUTRAL_MOVES = [("Tackle", "NEUTRAL", 30, 100, None), ("Claw Swipe", "NEUTRAL", 45, 100, None),
                 ("Headbutt", "NEUTRAL", 60, 95, None), ("Focus", "NEUTRAL", 0, 100, "buff_atk"),
                 ("Hyper Strike", "NEUTRAL", 90, 85, None)]

EFFECT_TEXT = {
    None: "", "burn": "May burn the target.", "freeze": "May freeze the target.", "poison": "May poison the target.",
    "stun": "May stun the target.", "sleep": "Puts the target to sleep.", "heal": "Restores 40% of max HP.",
    "drain": "Heals the user by half the damage dealt.", "buff_def": "Raises the user's Defense.",
    "buff_atk": "Raises the user's Attack.", "debuff_spd": "Lowers the target's Speed.",
    "debuff_atk": "Lowers the target's Attack.", "debuff_acc": "Lowers the target's accuracy.",
}

LEGENDARIES = [
    ("Solarchon", "THERMAL", "VOLT", "lava", "A star-fed titan said to have ignited Pyros IX's core."),
    ("Kryovane", "CRYO", "PSIONIC", "ice", "Sleeps beneath Glacia's ice shelf, dreaming the auroras."),
    ("Leviathal", "HYDRO", "PSIONIC", "ocean", "An abyssal leviathan whose song reshapes ocean currents."),
    ("Monolithus", "LITHIC", "PSIONIC", "desert", "A walking monolith older than Dune Kappa's dunes."),
    ("Yggdravine", "FLORA", "PSIONIC", "forest", "The world-tree organism linking Verdance's entire canopy."),
    ("Omnimech", "SYNTH", "VOLT", "artificial", "The Nexus's original architect AI, now a living machine."),
    ("Nebulith", "PSIONIC", "LITHIC", "desert", "A comet-born crystal mind. Appears only during sandstorms."),
    ("Voltaris", "VOLT", "HYDRO", "ocean", "A storm-serpent that rides lightning between Thalassa's reefs."),
    ("Magmawyrm", "THERMAL", "LITHIC", "lava", "A tunneling wyrm that swims through molten rock."),
    ("Aetheris", "PSIONIC", "SYNTH", "artificial", "A ghost signal that learned to build itself a body."),
]

ITEMS = [
    # id, name, kind, description, value
    ("iron", "Iron Ingot", "material", "Common structural metal salvaged from landers.", 0),
    ("bio_resin", "Bio Resin", "material", "Sticky polymer harvested from Verdance trees.", 0),
    ("kelp_fiber", "Kelp Fiber", "material", "Tough fiber from Thalassa's kelp forests.", 0),
    ("silica", "Silica Sand", "material", "Ultra-pure sand from Dune Kappa.", 0),
    ("cryo_crystal", "Cryo Crystal", "material", "A crystal that stays frozen at room temperature.", 0),
    ("basalt", "Basalt Ore", "material", "Volcanic ore rich in rare metals.", 0),
    ("scrap_alloy", "Scrap Alloy", "material", "Exotic alloy pulled from the Nexus ruins.", 0),
    ("pod", "Containment Pod", "capture", "Standard capture pod. 1.0x capture rate.", 10),
    ("pod_plus", "Stasis Pod", "capture", "Cryo-stasis pod. 1.8x capture rate.", 18),
    ("pod_max", "Quantum Pod", "capture", "Entangles the target. 3.0x capture rate.", 30),
    ("medgel", "MedGel", "heal", "Restores 50 HP to one creature.", 50),
    ("medgel_plus", "MedGel+", "heal", "Restores 150 HP to one creature.", 150),
    ("revive", "Revive Serum", "revive", "Revives a fainted creature at 50% HP.", 50),
    ("fuel", "Fuel Cell", "fuel", "Powers one interplanetary jump.", 1),
    ("lure", "Bio Lure", "lure", "Doubles encounter rate and rare chance for 60 steps.", 60),
]

RECIPES = [
    # output, qty, inputs
    ("pod", 2, {"iron": 2, "silica": 1}),
    ("pod", 1, {"iron": 1, "bio_resin": 1}),
    ("pod_plus", 1, {"iron": 2, "cryo_crystal": 1, "kelp_fiber": 1}),
    ("pod_max", 1, {"scrap_alloy": 2, "cryo_crystal": 1, "basalt": 1}),
    ("medgel", 2, {"kelp_fiber": 1, "bio_resin": 1}),
    ("medgel_plus", 1, {"medgel": 2, "cryo_crystal": 1}),
    ("revive", 1, {"medgel": 1, "silica": 2}),
    ("fuel", 1, {"basalt": 1, "iron": 1}),
    ("fuel", 1, {"kelp_fiber": 2, "iron": 1}),
    ("lure", 1, {"bio_resin": 2, "kelp_fiber": 1}),
]

BIOME_MATERIAL = {"forest": "bio_resin", "ocean": "kelp_fiber", "desert": "silica",
                  "ice": "cryo_crystal", "lava": "basalt", "artificial": "scrap_alloy"}

RESEARCH = [
    ("scanner", "Deep Scanner", "Scanning yields +1 DNA and reveals rarity of wild specimens.", 30, 3),
    ("containment", "Containment Field", "+15% capture chance per level.", 40, 3),
    ("genetics", "Gene Splicer", "Genome sequencing costs 25% less DNA per level.", 35, 3),
    ("logistics", "Cargo Logistics", "Gather +1 material from every resource node per level.", 25, 3),
    ("medbay", "Med Bay", "Your team recovers 15% max HP after every battle, per level.", 30, 2),
    ("propulsion", "Ion Propulsion", "Each jump has a 30% chance per level to not consume fuel.", 45, 2),
]

MISSIONS = [
    # id, title, description, kind, target, goal, reward_rp, reward_item, reward_qty
    ("m01", "First Contact", "Scan 3 different species.", "scan", "any", 3, 15, "pod", 3),
    ("m02", "Containment Protocol", "Capture 2 specimens.", "capture", "any", 2, 15, "medgel", 2),
    ("m03", "Field Engineer", "Craft 3 items at the Fabricator.", "craft", "any", 3, 10, "fuel", 2),
    ("m04", "Canopy Survey", "Scan 5 species on Verdance.", "scan_planet", "1", 5, 20, "lure", 1),
    ("m05", "Reef Census", "Scan 5 species on Thalassa.", "scan_planet", "2", 5, 20, "pod_plus", 2),
    ("m06", "Combat Data", "Win 5 battles.", "win", "any", 5, 20, "medgel_plus", 1),
    ("m07", "Gene Pioneer", "Sequence a genome in the Research Lab.", "sequence", "any", 1, 15, "revive", 1),
    ("m08", "Metamorphosis", "Evolve a creature.", "evolve", "any", 1, 25, "pod_plus", 2),
    ("m09", "Thermal Survey", "Scan 4 THERMAL-type species.", "scan_type", "THERMAL", 4, 20, "fuel", 2),
    ("m10", "Cryo Survey", "Scan 4 CRYO-type species.", "scan_type", "CRYO", 4, 20, "fuel", 2),
    ("m11", "Prospector", "Gather from 20 resource nodes.", "gather", "any", 20, 20, "pod", 5),
    ("m12", "Apex Encounter", "Defeat or capture a planet's Alpha.", "alpha", "any", 1, 40, "pod_max", 1),
    ("m13", "Rare Find", "Capture a rare (or rarer) specimen.", "capture_rarity", "rare", 1, 30, "pod_max", 1),
    ("m14", "Half Catalogue", "Register 50 species in the ExoDex (scanned).", "scan", "any", 50, 60, "pod_max", 3),
    ("m15", "Veteran", "Win 25 battles.", "win", "any", 25, 40, "medgel_plus", 3),
    ("m16", "Alpha Hunter", "Defeat or capture 4 Alphas.", "alpha", "any", 4, 80, "pod_max", 3),
    ("m17", "Xenobiologist", "Register 120 species in the ExoDex.", "scan", "any", 120, 120, "pod_max", 5),
    ("m18", "Living Archive", "Capture 40 specimens.", "capture", "any", 40, 80, "revive", 3),
]

TRAITS = [
    ("Hardy", "+12% max HP"), ("Ferocious", "+12% Attack"), ("Armored", "+12% Defense"),
    ("Swift", "+12% Speed"), ("Bioluminescent", "Critical hits twice as likely"),
    ("Regenerative", "Heals 6% max HP each turn"), ("Ancient", "+25% XP gained"),
    ("Resilient", "Immune to status effects"), ("Adaptive", "Super-effective damage taken -25%"),
    ("Volatile", "+20% damage dealt, -8% Defense"),
]

RARITY_WEIGHT = {"common": 60, "uncommon": 26, "rare": 10, "epic": 3.5, "legendary": 0.5}


def make_name(rng: random.Random, t: str, stage: int, used: set, root: str | None = None) -> str:
    for _ in range(200):
        r = root or (rng.choice(PREFIX[t]) + rng.choice(MID))
        name = (r + rng.choice(SUFFIX[stage])).capitalize()
        name = name.replace("aa", "a").replace("ii", "i").replace("uu", "u")
        if name not in used and 5 <= len(name) <= 12:
            used.add(name)
            return name
        root = None if _ > 20 else root
    raise RuntimeError("name space exhausted")


def build():
    rng = random.Random(SEED)
    used: set[str] = set()
    data: dict = {"version": 1, "types": TYPES, "type_chart": TYPE_CHART, "type_hue": TYPE_HUE}

    # ---- moves ----
    moves = []
    mid = 1
    move_ids_by_type: dict[str, list[int]] = {}
    for t, lst in MOVES_BY_TYPE.items():
        move_ids_by_type[t] = []
        for name, power, acc, eff in lst:
            moves.append(dict(id=mid, name=name, type=t, power=power, accuracy=acc, effect=eff,
                              description=(f"Power {power}. " if power else "") + EFFECT_TEXT[eff]))
            move_ids_by_type[t].append(mid)
            mid += 1
    neutral_ids = []
    for name, t, power, acc, eff in NEUTRAL_MOVES:
        moves.append(dict(id=mid, name=name, type=t, power=power, accuracy=acc, effect=eff,
                          description=(f"Power {power}. " if power else "") + EFFECT_TEXT[eff]))
        neutral_ids.append(mid)
        mid += 1
    data["moves"] = moves

    # ---- species ----
    species = []
    sid = 1
    plan = [3] * 32 + [2] * 42 + [1] * 30  # 96 + 84 + 30 = 210 + 10 legendaries = 220
    rng.shuffle(plan)
    biome_types = {p["biome"]: p["types"] for p in PLANETS}
    biomes = list(biome_types)

    def learnset(t1, t2, stage_count, rarity):
        tm = move_ids_by_type[t1]
        ls = [(1, neutral_ids[0]), (1, tm[0]), (5, tm[4] if rng.random() < .5 else neutral_ids[3]),
              (9, tm[1]), (14, neutral_ids[2]), (18, tm[2]), (26, tm[3]), (36, tm[5]), (42, neutral_ids[4])]
        if t2:
            sm = move_ids_by_type[t2]
            ls += [(12, sm[0]), (22, sm[1]), (32, sm[3])]
        if rarity in ("epic", "legendary"):
            ls = [(lv if lv == 1 else max(1, lv - 6), m) for lv, m in ls]
        ls.sort()
        return [list(x) for x in ls]

    for fam_index, stages in enumerate(plan):
        biome = biomes[fam_index % len(biomes)]
        t1 = rng.choice(biome_types[biome])
        t2 = None
        if rng.random() < 0.35:
            t2 = rng.choice([x for x in TYPES if x != t1])
        kingdom = rng.choice(KINGDOM_BY_TYPE[t1])
        extra_biome = rng.choice([b for b in biomes if t1 in biome_types[b] and b != biome] or [biome])
        habitat = sorted({biome, extra_biome}) if rng.random() < 0.3 else [biome]
        if stages == 1:
            base_rarity = rng.choices(["uncommon", "rare", "epic"], [35, 40, 25])[0]
        else:
            base_rarity = rng.choices(["common", "uncommon", "rare"], [70, 25, 5])[0]
        root = rng.choice(PREFIX[t1]) + rng.choice(MID)
        base = {k: rng.randint(35, 60) for k in ("hp", "atk", "def", "spd")}
        hue = (TYPE_HUE[t1] + rng.randint(-18, 18)) % 360
        family_ids = list(range(sid, sid + stages))
        evo_levels = [rng.randint(14, 18), rng.randint(30, 36)]
        adj = rng.choice(ADJ[kingdom])
        sprite_seed = rng.randint(1, 10 ** 6)
        for st in range(stages):
            mult = [1.0, 1.45, 1.95][st] * (1.25 if stages == 1 else 1.0)
            rarity = base_rarity
            if st >= 1 and rarity == "common":
                rarity = "uncommon"
            if st == 2 and rarity == "uncommon":
                rarity = "rare"
            stage_idx = st if stages > 1 else 1
            name = make_name(rng, t1, stage_idx, used, root)
            height = round((0.2 + rng.random() * 0.8) * (1 + st * 1.4), 2)
            mass = round(height ** 3 * rng.uniform(8, 60), 1)
            species.append(dict(
                id=sid, name=name, type1=t1, type2=t2 if (st > 0 or stages == 1 or rng.random() < .4) else None,
                kingdom=kingdom, rarity=rarity,
                hp=int(base["hp"] * mult) + 10, atk=int(base["atk"] * mult), defense=int(base["def"] * mult),
                spd=int(base["spd"] * mult),
                evolves_to=family_ids[st + 1] if st + 1 < stages else None,
                evolve_level=evo_levels[st] if st + 1 < stages else None,
                family=fam_index + 1, stage=st + 1, biomes=habitat, hue=hue, sprite_seed=sprite_seed,
                height_m=height, mass_kg=mass,
                description=f"A {adj} that {TRAIT_FACT[t1]}." + (
                    " Its final form dominates the local food web." if st == 2 else
                    " Juvenile specimens are often found in groups." if st == 0 and stages > 1 else ""),
            ))
            sid += 1

    # second type consistency: evolved stages inherit type2 from family
    fam_t2: dict[int, str | None] = {}
    for s in species:
        if s["type2"]:
            fam_t2.setdefault(s["family"], s["type2"])
    for s in species:
        if s["stage"] > 1 and not s["type2"]:
            s["type2"] = fam_t2.get(s["family"])

    for name, t1, t2, biome, desc in LEGENDARIES:
        used.add(name)
        species.append(dict(
            id=sid, name=name, type1=t1, type2=t2, kingdom=rng.choice(KINGDOM_BY_TYPE[t1]), rarity="legendary",
            hp=rng.randint(105, 125), atk=rng.randint(100, 125), defense=rng.randint(95, 120),
            spd=rng.randint(90, 120), evolves_to=None, evolve_level=None, family=len(plan) + (sid - len(species)) + 1,
            stage=1, biomes=[biome], hue=TYPE_HUE[t1], sprite_seed=rng.randint(1, 10 ** 6),
            height_m=round(rng.uniform(4, 18), 1), mass_kg=round(rng.uniform(800, 9000), 0), description=desc))
        sid += 1

    # learnsets
    for s in species:
        s["learnset"] = learnset(s["type1"], s["type2"], s["stage"], s["rarity"])
    # renumber legendary families uniquely
    fam = len(plan)
    for s in species:
        if s["rarity"] == "legendary":
            fam += 1
            s["family"] = fam
    data["species"] = species

    # Alphas: the strongest final-stage non-legendary of each planet's biome, plus legendaries
    planets = []
    for p in PLANETS:
        legend = next(s for s in species if s["rarity"] == "legendary" and s["biomes"] == [p["biome"]])
        q = dict(p)
        q["alpha_species"] = legend["id"]
        q["alpha_level"] = p["max_level"] + 4
        q["material"] = BIOME_MATERIAL[p["biome"]]
        planets.append(q)
    data["planets"] = planets
    data["items"] = [dict(id=i, name=n, kind=k, description=d, value=v) for i, n, k, d, v in ITEMS]
    data["recipes"] = [dict(id=i + 1, output=o, qty=q, inputs=inp) for i, (o, q, inp) in enumerate(RECIPES)]
    data["research"] = [dict(id=i, name=n, description=d, cost=c, max_level=m) for i, n, d, c, m in RESEARCH]
    data["missions"] = [dict(id=a, title=b, description=c, kind=d, target=e, goal=f, reward_rp=g,
                             reward_item=h, reward_qty=i) for a, b, c, d, e, f, g, h, i in MISSIONS]
    data["traits"] = [dict(name=n, description=d) for n, d in TRAITS]
    data["rarity_weight"] = RARITY_WEIGHT
    return data


def main():
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1))
    sp = data["species"]
    print(f"wrote {OUT.relative_to(ROOT)}: {len(sp)} species, {len(data['moves'])} moves, "
          f"{len(data['planets'])} planets")
    from collections import Counter
    print("rarity:", Counter(s["rarity"] for s in sp))
    print("biomes:", Counter(b for s in sp for b in s["biomes"]))


if __name__ == "__main__":
    main()
