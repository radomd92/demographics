import numpy as np
import time
import pickle
import sys
import random
import tempfile

import networkx as nx
import matplotlib.pyplot as plt
from networkx.drawing.nx_pydot import graphviz_layout  # Ensure Graphviz is installed

from humans import Man, Woman
from state import SimulationState

sys.setrecursionlimit(1000000000)

state = SimulationState()


def main():
    if len(sys.argv) > 1:
        days_to_simulate = int(sys.argv[1]) * 365
    else:
        days_to_simulate = 100000
    birth_giving_ages = []
    men_population = 95
    women_population = 132
    men = [Man(c, c) for c in range(100, 100 + men_population)]
    women = [Woman(c, c) for c in range(200, 200 + women_population)]
    families = {}
    for k in men + women:
        families[k.surname] = 0

    # for k in men:
    #     families[k.surname + "♂"] = 0
    # for k in women:
    #     families[k.mother_name + "♀"] = 0

    population = len(women) + len(men)
    all_ever_lived = []
    while state.current_day < days_to_simulate and 0 <= population < 40000:
        women_at_next_iteration = set()
        men_at_next_iteration = set()

        for human in men:
            if human.is_dead:
                population -= 1
                print(f"[Day {state.current_day}] R.I.P: [{human}] has died")
                # dead person does not make past the loop
                continue

            men_at_next_iteration.add(human)

        for human in women:
            if human.is_dead:
                population -= 1
                print(f"[Day {state.current_day}] R.I.P: [{human}] has died")
                # dead person does not make past the loop
                continue

            # Marriage infidelity dynamics
            if human.is_married:
                if random.randint(0, 1000) < 20:
                    partner = men[random.randint(0, len(men) - 1)]
                else:
                    partner = human.life_partner
            else:
                partner = men[random.randint(0, len(men) - 1)]

            human.conceive(partner)
            if human.should_give_birth:
                if human.baby is not None:
                    print(
                        f"[Day {state.current_day}] Baby born! {human.baby.name} {human.baby._id} ({human.baby.__class__.__name__})")
                    death_roll = random.randint(0, 100000)
                    if death_roll < 3120:
                        human.life_expectancy = 0
                    all_ever_lived.append(human.baby)
                    if isinstance(human.baby, Woman):
                        women_at_next_iteration.add(human.baby)
                    else:
                        men_at_next_iteration.add(human.baby)
                human.baby = None
                human.conception = None
                human.kids += 1
                partner.kids += 1
                population += 1
                birth_giving_ages.append(human.age)

            women_at_next_iteration.add(human)

        state.next_day(100)
        women = list(women_at_next_iteration)
        men = list(men_at_next_iteration)
        print(f"Day {state.current_day} (year {state.current_day // 365}) Population: {population}")
        time.sleep(.01)

    kids_total_per_woman = sum([h.kids for h in women]) / max(1, len(women))
    everybody = men + women

    for h in everybody:
        surname = h.surname
        # if isinstance(h, Woman):
        #     surname += '♀'
        # else:
        #     surname += '♂'

        if surname in families:
            families[surname] += 1
        else:
            families[surname] = 1

    # Most used family names in the population
    families = sorted(list([(v, k) for k, v in families.items()]), reverse=True)
    with open("families.csv", "w") as f:
        f.write("count,family_name\n")
        f.write("\n".join([f"{k},{v}" for v, k in families]))

    with open('summary.txt', 'w') as f:
        f.write(f"\nTotal days simulated: {state.current_day}")
        f.write(f"\nAverage kids per woman: {kids_total_per_woman}")
        f.write(f"\nTotal population: {len(men) + len(women)}")
        f.write(f"\nMedian age men: {np.median([m.age for m in men])}")
        f.write(f"\nMedian age women: {np.median([w.age for w in women])}")
        f.write(f"\nMedian mother's ages: {np.median(birth_giving_ages)}")
        f.write(f"\nPeople aged 0-15: {len([h.age for h in everybody if h.age < 15])}")
        f.write(f"\nPeople aged 15-60: {len([h.age for h in everybody if 15 < h.age < 60])}")
        f.write(f"\nPeople aged 60+: {len([h.age for h in everybody if h.age > 60])}")
        f.write(f"\nNsexual partners/boy: {np.average([len(h.sexual_partners.keys()) for h in men if h.age_cherry_popped is not None])}")
        f.write(f"\nNsexual partners/girl: {np.average([len(h.sexual_partners.keys()) for h in women if h.age_cherry_popped is not None])}")
        f.write(
            f"\navg. age virginity loss/girl: {np.average([h.age_cherry_popped for h in women if h.age_cherry_popped is not None])}")
        f.write(
            f"\navg. age virginity loss/boy: {np.average([h.age_cherry_popped for h in men if h.age_cherry_popped is not None])}")
        f.write(
            f"\ntop 1% age virginity loss/girl: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 99)}")
        f.write(
            f"\ntop 10% age virginity loss/girl: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 90)}")
        f.write(
            f"\ntop 90% age virginity loss/girl: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 10)}")
        f.write(
            f"\ntop 99% age virginity loss/girl: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 1)}")
        f.write(
            f"\ntop 1% age virginity loss/boy: {np.percentile([h.age_cherry_popped for h in men if h.age_cherry_popped is not None], 99)}")
        f.write(
            f"\ntop 10% age virginity loss/boy: {np.percentile([h.age_cherry_popped for h in men if h.age_cherry_popped is not None], 90)}")
        f.write(
            f"\ntop 90% age virginity loss/boy: {np.percentile([h.age_cherry_popped for h in men if h.age_cherry_popped is not None], 10)}")
        f.write(
            f"\ntop 99% age virginity loss/boy: {np.percentile([h.age_cherry_popped for h in men if h.age_cherry_popped is not None], 1)}")

    open("population.txt", "w").write("\n".join([str(h) for h in everybody]))

    to_package = [
        h.as_dict() for h in all_ever_lived
    ]
    with open("population.pkl", "wb") as universe_file:
        pickle.dump(to_package, universe_file, pickle.HIGHEST_PROTOCOL)

    print("Simulation finished!")


def explore_population():
    all_ever_lived = pickle.load(open("population.pkl", "rb"))
    current_day = max([h.year_of_birth * 365.25 for h in all_ever_lived])
    print("Population explorer")
    print("====================================")
    print(f"Enter a name to search for a person > ", end="")
    name = input()

    def print_person_children(person, level=0):
        print('   ' * level,
              f"{person.name}, {person.__class__.__name__} {'(dead)' if person.age > person.life_expectancy else f', aged {person.age}'}, born {person.year_of_birth})")
        for child in all_ever_lived:
            if child.father == person or child.mother == person:
                print_person_children(child, level=level + 1)

    def print_person_ascendance(person, level=0):
        print('   ' * level,
              f"{person.name}, {person.__class__.__name__} {'(dead)' if person.age > person.life_expectancy else f', aged {person.age}'}, born {person.year_of_birth})")
        if person.mother and isinstance(person, Woman):
            print_person_ascendance(person.mother, level=level + 1)
        if person.father and isinstance(person, Man):
            print_person_ascendance(person.father, level=level + 1)

    while name:
        for h in all_ever_lived:
            if name.lower() in h.name.lower():
                draw_family_tree(h)
                # draw_cherry_poppers(h)
                # print("===== PERSON =====")
                # print(h)
                # print("===== DESCENDANCE =====")
                # print_person_children(h)
                # print("===== ASCENDANCE =====")
                # print_person_ascendance(h)

        print("====================================")
        print(f"Enter a name to search for a person > ", end="")
        name = input()


def draw_cherry_poppers(person: [Man, Woman]):
    edges = []
    nodes = []
    node_colors = []
    options = {
        'node_size': 1000,
        'width': 1,
        'arrowstyle': '-|>',
        'arrowsize': 5,
    }

    def make_label(person: [Man, Woman]):
        if person is None:
            return "Unknown"
        if isinstance(person, Woman):
            label = f"{person.name}(♀)"
        else:
            label = f"{person.name}(♂)"

        label += f"\n({int(person.year_of_birth)} - {int(person.year_of_birth + person.life_expectancy)})" \
                 f"\nbeauty={person.beauty}"

        return label

    def print_person_vcard_taker(person: [Man, Woman], level=0):
        if person is None:
            return

        edge_self_label = make_label(person)

        if person.cherry_popper is not None:
            edge_popper = make_label(person.cherry_popper)
            if edge_popper not in nodes:
                nodes.append(edge_popper)
                edges.append((edge_popper, edge_self_label))
                print_person_vcard_taker(person.cherry_popper, level + 1)
        if person.life_partner is not None:
            edge_partner = make_label(person.life_partner)
            if edge_partner not in nodes:
                nodes.append(edge_partner)
                edges.append((edge_partner, edge_self_label))
                print_person_vcard_taker(person.life_partner, level + 1)

    # node_colors.append('green')
    print_person_vcard_taker(person)

    g = nx.DiGraph()

    g.add_nodes_from(nodes)
    for edge in edges:
        g.add_edge(*edge)

    graphviz_settings = """
        digraph G {
            ranksep=-1.0;  # Adjust vertical spacing
            nodesep=1.0;  # Adjust horizontal spacing
        }
        """

    with tempfile.NamedTemporaryFile(delete=False, suffix=".dot") as tmp_dot_file:
        tmp_dot_file.write(graphviz_settings.encode())
        tmp_dot_file.close()
        pos = graphviz_layout(g, prog='dot', root=tmp_dot_file.name)

    nx.draw(g, pos, with_labels=True, node_color=node_colors, **options)
    plt.draw()
    plt.show()


def draw_family_tree(person: [Man, Woman]):
    edges = []
    nodes = []
    node_colors = []
    options = {
        'node_size': 1000,
        'width': 1,
        'arrowstyle': '-|>',
        'arrowsize': 5,
    }

    def make_label(person: [Man, Woman]):
        if person is None:
            return "Unknown"
        if isinstance(person, Woman):
            label = f"{person.name}(♀)"
        else:
            label = f"{person.name}(♂)"

        label += f"\n({int(person.year_of_birth)} - {int(person.year_of_birth + person.life_expectancy)})" \
                 f"\nbeauty={person.beauty}"

        return label

    def print_person_parents(person: [Man, Woman], level=0):
        if person is None:
            return

        edge_self_label = make_label(person)

        if person.mother is not None:
            edge_mother_label = make_label(person.mother)
            edges.append((edge_mother_label, edge_self_label))
            nodes.append(edge_self_label)

        if person.father is not None:
            edge_father_label = make_label(person.father)
            edges.append((edge_father_label, edge_self_label))
            print_person_parents(person.father, level + 1)
            if level < 2:
                print_person_parents(person.mother, level + 1)

    # node_colors.append('green')
    print_person_parents(person)

    g = nx.DiGraph()

    g.add_nodes_from(nodes)
    for edge in edges:
        g.add_edge(*edge)

    graphviz_settings = """
    digraph G {
        ranksep=-1.0;  # Adjust vertical spacing
        nodesep=1.0;  # Adjust horizontal spacing
    }
    """

    with tempfile.NamedTemporaryFile(delete=False, suffix=".dot") as tmp_dot_file:
        tmp_dot_file.write(graphviz_settings.encode())
        tmp_dot_file.close()
        pos = graphviz_layout(g, prog='dot', root=tmp_dot_file.name)

    nx.draw(g, pos, with_labels=True, node_color=node_colors, **options)
    plt.draw()
    plt.show()


if __name__ == '__main__':
    main()
    # explore_population()
    # draw_family_tree(None)
