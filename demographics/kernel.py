"""The typed simulation hot path. This exact source also builds with mypyc.

No global clock, random state, I/O, recursive serialization, or artificial sleeps.
Lifespans are sampled once; each step is linear in the living population.
"""

import random
from collections.abc import Callable

from demographics.models import SimulationConfig

DAYS_PER_YEAR = 365.25


class Person:
    """An individual with stable IDs instead of cyclic object references."""

    def __init__(
        self,
        identifier: int,
        female: bool,
        birth_day: float,
        death_day: float,
        family: int,
        mother_id: int = 0,
        father_id: int = 0,
    ) -> None:
        self.identifier = identifier
        self.female = female
        self.birth_day = birth_day
        self.death_day = death_day
        self.family = family
        self.mother_id = mother_id
        self.father_id = father_id
        self.children = 0
        self.due_day = -1.0
        self.pregnancy_father = 0
        self.pregnancy_family = 0


class Snapshot:
    """Aggregate counts at one observation boundary."""

    def __init__(
        self, day: float, men: int, women: int, births: int, deaths: int, mean_age: float
    ) -> None:
        self.day = day
        self.men = men
        self.women = women
        self.births = births
        self.deaths = deaths
        self.mean_age = mean_age


def simulate(
    config: SimulationConfig,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[list[Snapshot], list[Person], str]:
    """Simulate a closed population; return observations and final living people.

    Conception uses an annual probability converted to each actual step duration.
    Only unrelated adults can conceive. Births are processed at step boundaries;
    life expectancy is a sampled lifespan, not a calibrated mortality table.
    """
    rng = random.Random(config.seed)
    # The config is an interpreted dataclass. Cache hot scalar attributes so
    # mypyc can use unboxed locals instead of repeated Python attribute access.
    fertility_min = config.fertility_min_age
    fertility_max = config.fertility_max_age
    max_population = config.max_population
    living: list[Person] = []
    next_id = 1
    for female, count in ((False, config.initial_men), (True, config.initial_women)):
        for _ in range(count):
            age = rng.uniform(0.0, config.initial_max_age)
            # Founders are alive at day zero, even if sampled older than mean lifespan.
            lifespan = max(
                age + 1.0 / DAYS_PER_YEAR, rng.gauss(config.life_expectancy, config.lifespan_stddev)
            )
            living.append(
                Person(
                    next_id, female, -age * DAYS_PER_YEAR, (lifespan - age) * DAYS_PER_YEAR, next_id
                )
            )
            next_id += 1

    end_day = config.years * DAYS_PER_YEAR
    day = 0.0
    births = 0
    deaths = 0
    history: list[Snapshot] = []
    reason = "completed"
    while True:
        men = 0
        women = 0
        age_sum = 0.0
        for person in living:
            if person.female:
                women += 1
            else:
                men += 1
            age_sum += (day - person.birth_day) / DAYS_PER_YEAR
        history.append(
            Snapshot(day, men, women, births, deaths, age_sum / len(living) if living else 0.0)
        )
        if progress is not None:
            progress(int(day), int(end_day))
        if not living:
            reason = "extinct"
            break
        if day >= end_day:
            break
        if len(living) >= max_population:
            reason = "population_limit"
            break

        next_day = min(day + config.step_days, end_day)
        elapsed = next_day - day
        survivors: list[Person] = []
        adult_men: list[Person] = []
        by_id: dict[int, Person] = {}
        for person in living:
            if person.death_day <= next_day:
                deaths += 1
                continue
            survivors.append(person)
            by_id[person.identifier] = person
            age = (day - person.birth_day) / DAYS_PER_YEAR
            if not person.female and age >= 18.0:
                adult_men.append(person)

        newborns: list[Person] = []
        maternal_deaths: set[int] = set()
        conception_chance = 1.0 - (1.0 - config.annual_conception_probability) ** (
            elapsed / DAYS_PER_YEAR
        )
        for mother in survivors:
            if not mother.female:
                continue
            if mother.due_day >= 0.0:
                if mother.due_day <= next_day:
                    # Do not overshoot the hard population limit during a birth wave.
                    if len(survivors) - len(maternal_deaths) + len(newborns) >= (max_population):
                        continue
                    father = by_id.get(mother.pregnancy_father)
                    baby = Person(
                        next_id,
                        rng.random() < 0.5,
                        next_day,
                        next_day
                        + max(
                            1.0 / DAYS_PER_YEAR,
                            rng.gauss(config.life_expectancy, config.lifespan_stddev),
                        )
                        * DAYS_PER_YEAR,
                        mother.pregnancy_family,
                        mother.identifier,
                        mother.pregnancy_father,
                    )
                    next_id += 1
                    births += 1
                    mother.children += 1
                    if father is not None:
                        father.children += 1
                    if rng.random() < config.infant_mortality:
                        deaths += 1
                    else:
                        newborns.append(baby)
                    mother.due_day = -1.0
                    if rng.random() < config.maternal_mortality:
                        maternal_deaths.add(mother.identifier)
                        deaths += 1
                # No new conception in the same step as delivery.
                continue
            age = (day - mother.birth_day) / DAYS_PER_YEAR
            if not fertility_min <= age < fertility_max:
                continue
            if not adult_men or rng.random() >= conception_chance:
                continue
            # Bounded sampling avoids an O(women * men) partner search.
            for _ in range(8):
                candidate = adult_men[rng.randrange(len(adult_men))]
                if (
                    candidate.family == mother.family
                    or candidate.identifier == mother.father_id
                    or candidate.mother_id == mother.identifier
                    or (mother.mother_id != 0 and candidate.mother_id == mother.mother_id)
                    or (mother.father_id != 0 and candidate.father_id == mother.father_id)
                ):
                    continue
                mother.due_day = next_day + config.gestation_days
                mother.pregnancy_father = candidate.identifier
                mother.pregnancy_family = candidate.family
                break

        living = [person for person in survivors if person.identifier not in maternal_deaths]
        living.extend(newborns)
        day = next_day
    return history, living, reason
