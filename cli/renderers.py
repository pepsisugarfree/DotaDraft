"""Renderers for the core objects. The core only knows the Renderer interface."""

from cli.graphics import Table, bar
from core import ATTRIBUTES, DIRE, POSITIONS, RADIANT, Renderer, assign_positions, position_shares, roles, traits
from core.hero_notes import support_share
from core.positions import lane_shares


def percent(value):
    return f"{value * 100:.1f}%"


def signed(value):
    return f"{value:+.1f}"


class HeroRenderer(Renderer):
    def __init__(self, style):
        self.style = style

    def render(self, hero):
        s = self.style
        attribute = s.attribute(hero.attribute, ATTRIBUTES.get(hero.attribute, hero.attribute))
        lines = [
            f"{s.bold(hero.name)}  ({attribute}, {hero.attack_type})",
            f"Roles: {', '.join(POSITIONS[position] for position in roles(hero))}",
            f"Traits: {', '.join(traits(hero)) or '-'}",
            f"Winrate this patch: {percent(hero.winrate)} in {hero.games:,} Divine+ games",
        ]
        shares = lane_shares(hero)
        if shares:
            safe, mid, off = shares
            lines.append(f"Lanes: safe {percent(safe)}, mid {percent(mid)}, off {percent(off)}; "
                         f"played as support ~{support_share(hero) * 100:.0f}%")
        else:
            lines.append("Lanes: not enough games yet, the hero can be anything")
        lines += ["", "Positions (guessed part of games):"]
        for position, share in position_shares(hero).items():
            lines.append(f"  {position} {POSITIONS[position]:<8} {s.dim(bar(share, 1, 20))} {share * 100:>3.0f}%")
        lines.append("")
        lines.append(f"Image: {hero.image_url or '-'}")
        return "\n".join(lines)


class DraftRenderer(Renderer):
    def __init__(self, style, pool):
        self.style = style
        self.pool = pool

    def render(self, draft):
        s = self.style
        lineups = {}
        for team in (RADIANT, DIRE):
            heroes = [self.pool.get(hero_id) for hero_id in draft.picks(team)]
            roles = assign_positions(heroes, draft.fixed_positions(team))
            lineups[team] = {position: self.pool.get(hero_id).name for hero_id, position in roles.items()}

        table = Table(["Pos", s.team(RADIANT, "Radiant"), s.team(DIRE, "Dire")])
        for position, title in POSITIONS.items():
            table.add_row(f"{position} {title}", lineups[RADIANT].get(position, s.dim("-")),
                          lineups[DIRE].get(position, s.dim("-")))

        lines = [s.bold(f"{draft.format.title}, step {len(draft.steps)}/{len(draft.format.order)}"),
                 table.render(s)]
        if draft.format.order[0][1] == "ban" or draft.bans():
            for team in (RADIANT, DIRE):
                bans = ", ".join(self.pool.get(hero_id).name for hero_id in draft.bans(team))
                lines.append(f"{s.team(team, team.title() + ' bans')}: {bans or '-'}")
        return "\n".join(lines)


class EvaluationRenderer(Renderer):
    def __init__(self, style, pool):
        self.style = style
        self.pool = pool

    def render(self, evaluation):
        s = self.style
        radiant, dire = evaluation.radiant, evaluation.dire
        table = Table(["", s.team(RADIANT, "Radiant"), s.team(DIRE, "Dire")], right_aligned=[1, 2])
        table.add_row("Counter picks", signed(radiant.counters), signed(dire.counters))
        table.add_row("Synergy", signed(radiant.synergy), signed(dire.synergy))
        table.add_row("Hero strength", signed(radiant.strength), signed(dire.strength))
        table.add_row("Positions", signed(radiant.positions), signed(dire.positions))
        table.add_row("Composition", signed(radiant.composition), signed(dire.composition))
        table.add_row(s.bold("Total"), s.bold(signed(radiant.total)), s.bold(signed(dire.total)))

        chance = evaluation.radiant_chance
        width = 30
        left = round(chance * width)
        meter = s.green("#" * left) + s.red("." * (width - left))
        lines = [table.render(s), ""]
        for team, score in ((RADIANT, radiant), (DIRE, dire)):
            if score.problems:
                lines.append(f"{s.team(team, team.title())} lacks: {', '.join(score.problems)}")
        lines.append(f"Win chance: Radiant {percent(chance)} [{meter}] {percent(1 - chance)} Dire")

        if evaluation.key_matchups:
            lines.append("Key matchups:")
            for hero_id, enemy_id, advantage in evaluation.key_matchups:
                hero, enemy = self.pool.get(hero_id).name, self.pool.get(enemy_id).name
                if advantage < 0:
                    hero, enemy, advantage = enemy, hero, -advantage
                lines.append(f"  {hero} is good against {enemy} ({advantage * 100:+.1f}%)")

        if evaluation.key_synergies:
            lines.append("Key synergies:")
            for team, hero_id, ally_id, synergy in evaluation.key_synergies:
                pair = f"{self.pool.get(hero_id).name} and {self.pool.get(ally_id).name}"
                how = "work well together" if synergy >= 0 else "work badly together"
                lines.append(f"  {s.team(team, team.title())}: {pair} {how} ({synergy * 100:+.1f}%)")
        return "\n".join(lines)
