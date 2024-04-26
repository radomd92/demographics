import numpy as np
import time
import pickle
import sys
import random
from humans import Man, Woman
from state import SimulationState

sys.setrecursionlimit(50000)

state = SimulationState()


def main():

    if len(sys.argv) > 1:
        days_to_simulate = int(sys.argv[1]) * 365
    else:
        days_to_simulate = 25000
    birth_giving_ages = []
    men_population = 61
    women_population = 67
    men = [Man(c, c) for c in range(100, 100 + men_population)]
    women = [Woman(c, c) for c in range(200, 200 + women_population)]
    families = {}
    for k in men:
        families[k.surname + "♂"] = 0
    for k in women:
        families[k.mother_name + "♀"] = 0

    population = len(women) + len(men)
    all_ever_lived = men + women
    while state.current_day < days_to_simulate and 40000 >= population > 10:
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
                    if isinstance(human.baby, Woman):
                        all_ever_lived.append(human.baby)
                        women_at_next_iteration.add(human.baby)
                    else:
                        all_ever_lived.append(human.baby)
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
        print(f"Day {current_day} (year {current_day // 365}) Population: {population}")
        time.sleep(.01)

    kids_total_per_woman = sum([h.kids for h in women]) / len(women)
    everybody = men + women

    for h in everybody:
        surname = h.surname
        if isinstance(h, Woman):
            surname += '♀'
        else:
            surname += '♂'

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
        f.write(f"\nTotal days simulated: {current_day}")
        f.write(f"\nAverage kids per woman: {kids_total_per_woman}")
        f.write(f"\nTotal population: {len(men) + len(women)}")
        f.write(f"\nMedian age men: {np.median([m.age for m in men])}")
        f.write(f"\nMedian age women: {np.median([w.age for w in women])}")
        f.write(f"\nMedian mother's ages: {np.median(birth_giving_ages)}")
        f.write(f"\nPeople aged 0-15: {len([h.age for h in everybody if h.age < 15])}")
        f.write(f"\nPeople aged 15-60: {len([h.age for h in everybody if 15 < h.age < 60])}")
        f.write(f"\nPeople aged 60+: {len([h.age for h in everybody if h.age > 60])}")
        f.write(f"\nNsexual partners/boy: {np.average([len(h.sexual_partners.keys()) for h in men])}")
        f.write(f"\nNsexual partners/girl: {np.average([len(h.sexual_partners.keys()) for h in women])}")
        f.write(
            f"\navg. age virginity loss/girl: {np.average([h.age_cherry_popped for h in women if h.age_cherry_popped is not None])}")
        f.write(
            f"\navg. age virginity loss/boy: {np.average([h.age_cherry_popped for h in women if h.age_cherry_popped is not None])}")
        f.write(
            f"\ntop 1% age virginity loss/girl: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 99)}")
        f.write(
            f"\ntop 10% age virginity loss/girl: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 90)}")
        f.write(
            f"\ntop 90% age virginity loss/girl: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 10)}")
        f.write(
            f"\ntop 99% age virginity loss/girl: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 1)}")
        f.write(
            f"\ntop 1% age virginity loss/boy: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 99)}")
        f.write(
            f"\ntop 10% age virginity loss/boy: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 90)}")
        f.write(
            f"\ntop 90% age virginity loss/boy: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 10)}")
        f.write(
            f"\ntop 99% age virginity loss/boy: {np.percentile([h.age_cherry_popped for h in women if h.age_cherry_popped is not None], 1)}")

    open("population.txt", "w").write("\n".join([str(h) for h in everybody]))
    pickle.dump(all_ever_lived, open("population.pkl", "wb"))

    print("Simulation finished!")


def explore_population():
    current_day = 0
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
                print("===== PERSON =====")
                print(h)
                print("===== DESCENDANCE =====")
                print_person_children(h)
                print("===== ASCENDANCE =====")
                print_person_ascendance(h)

        print("====================================")
        print(f"Enter a name to search for a person > ", end="")
        name = input()


if __name__ == '__main__':
    # main()
    explore_population()
