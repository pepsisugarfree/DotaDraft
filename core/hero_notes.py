"""Things about heroes that the statistics can't show, written by hand.

OpenDota knows on which lane a hero stands, but not if it is the core or
the support of that lane. So here is how often each hero is played as a
support in public games of the current meta. A hero that is not in the
table is a core (0).
"""

SUPPORT_SHARE = {
    # pure supports
    "Ancient Apparition": 1.0, "Bane": 1.0, "Chen": 1.0, "Crystal Maiden": 1.0, "Dazzle": 1.0,
    "Disruptor": 1.0, "Grimstroke": 1.0, "Io": 1.0, "Jakiro": 1.0, "Keeper of the Light": 0.9,
    "Lich": 1.0, "Lion": 1.0, "Oracle": 1.0, "Rubick": 1.0, "Shadow Demon": 1.0,
    "Shadow Shaman": 1.0, "Warlock": 1.0, "Witch Doctor": 1.0, "Winter Wyvern": 1.0,
    "Dark Willow": 1.0, "Ring Master": 1.0, "Largo": 0.9,
    # mostly supports
    "Skywrath Mage": 0.9, "Treant Protector": 0.9, "Undying": 0.9, "Ogre Magi": 0.9, "Tusk": 0.9,
    "Hoodwink": 0.9, "Snapfire": 0.9, "Techies": 0.9, "Earthshaker": 0.8, "Mirana": 0.8,
    "Silencer": 0.8, "Phoenix": 0.8, "Elder Titan": 0.8, "Venomancer": 0.8, "Pugna": 0.8,
    "Nyx Assassin": 0.8, "Vengeful Spirit": 0.7, "Enchantress": 0.7, "Bounty Hunter": 0.7,
    # played both ways
    "Clockwerk": 0.6, "Spirit Breaker": 0.6, "Omniknight": 0.6, "Earth Spirit": 0.6,
    "Enigma": 0.5, "Pudge": 0.5, "Marci": 0.5, "Abaddon": 0.5,
    # mostly cores, sometimes supports
    "Visage": 0.4, "Batrider": 0.4, "Zeus": 0.3, "Windranger": 0.3, "Sand King": 0.3,
    "Tiny": 0.3, "Weaver": 0.3, "Dawnbreaker": 0.3, "Lina": 0.2, "Dark Seer": 0.2,
    "Kunkka": 0.2, "Magnus": 0.2, "Primal Beast": 0.2, "Slardar": 0.2, "Nature's Prophet": 0.2,
    "Leshrac": 0.2, "Underlord": 0.2,
}

# heroes that start fights: a long stun, a blink-in, a big area spell
INITIATORS = {
    "Axe", "Batrider", "Beastmaster", "Centaur Warrunner", "Clockwerk", "Dark Seer", "Dawnbreaker",
    "Earth Spirit", "Earthshaker", "Elder Titan", "Enigma", "Faceless Void", "Kunkka",
    "Legion Commander", "Magnus", "Marci", "Mars", "Night Stalker", "Nyx Assassin", "Pangolier",
    "Phoenix", "Primal Beast", "Puck", "Pudge", "Sand King", "Slardar", "Spirit Breaker",
    "Tidehunter", "Treant Protector", "Tusk",
}

# heroes that can stand in front and take the damage
FRONTLINE = {
    "Abaddon", "Axe", "Beastmaster", "Brewmaster", "Bristleback", "Centaur Warrunner",
    "Chaos Knight", "Clockwerk", "Dawnbreaker", "Doom", "Dragon Knight", "Elder Titan", "Huskar",
    "Kunkka", "Legion Commander", "Lifestealer", "Lycan", "Mars", "Necrophos", "Night Stalker",
    "Ogre Magi", "Omniknight", "Primal Beast", "Pudge", "Slardar", "Spirit Breaker", "Tidehunter",
    "Timbersaw", "Tiny", "Treant Protector", "Underlord", "Undying", "Viper", "Wraith King",
}


def support_share(hero):
    """How often the hero is played as a support, 0..1."""
    return SUPPORT_SHARE.get(hero.name, 0.0)


def traits(hero):
    result = []
    if hero.name in INITIATORS:
        result.append("initiator")
    if hero.name in FRONTLINE:
        result.append("frontline")
    return result
