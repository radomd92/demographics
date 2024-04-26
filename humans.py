import numpy as np
import math
import random
from state import SimulationState

mappings = {}


def get_syllable():
    consonants = 'm v p n t k ng r h x'.split() + ['']
    vowels = 'a ā e ē i ī o ō u ū'
    return random.choice(consonants) + random.choice(vowels.split()) + random.choice(consonants) + random.choice(
        vowels.split())


class Human(object):

    def __init__(self, father_id=1, mother_id=1):
        global SimulationState
        ().current_day
        self._id = (father_id, mother_id)
        self.age_cherry_popped = None
        self.beauty = random.randint(0, 100)
        self.beauty_standard = 50
        self.cherry_popper = None
        self.father = None
        self.generation = (0, 0)
        self.genes = np.zeros((23, 2), dtype=int)
        self.genes[:, 0] = father_id
        self.genes[:, 1] = mother_id
        self.given_name = get_syllable().title()
        self.kids = 0
        self.life_expectancy = random.randint(0, 120)
        self.life_partner = None
        self.marriage_age = random.randint(1800, 3200) / 100
        self.mother = None
        self.sex_XP = 0
        self.sexual_partners = {}
        self.year_of_birth = SimulationState().current_day / 365.25
        if father_id in mappings:
            self.surname = mappings[father_id].upper()
        else:
            self.surname = get_syllable().upper()
            mappings[father_id] = self.surname

        if mother_id in mappings:
            self.mother_name = mappings[mother_id].upper()
        else:
            self.mother_name = get_syllable().upper()
            mappings[mother_id] = self.mother_name

    @property
    def is_married(self):
        return self.life_partner is not None

    @property
    def name(self):
        patronym = ' ' + self.father.given_name if self.father else ''
        matronym = ' ' + self.mother.given_name if self.mother else ''
        return f"{self.surname.upper()} {self.given_name}{patronym}{matronym}"

    @property
    def want_to_marry(self):
        return self.age > self.marriage_age \
            and (self.life_partner is None or self.life_partner.is_dead)

    def __repr__(self):
        if self.father is not None:
            dad_string = self.father.name if self.father else 'unknown'
            dad_string += f' ({self.father.age})' if self.father else ' (??)'
            dad_string += f' (dead)' if self.father.is_dead else ''
        else:
            dad_string = 'unknown'

        if self.mother is not None:
            mom_string = self.mother.name if self.mother else 'unknown'
            mom_string += f' ({self.mother.age})' if self.mother else ' (??)'
            mom_string += f' (dead)' if self.mother.is_dead else ''
        else:
            mom_string = 'unknown'

        return f"{self.__class__.__name__}({self.name}, " \
               f"gen={self.generation[0]}/{self.generation[1]}, " \
               f"age={int(self.age)}, " \
               f"partner={self.life_partner.name + f' ({self.life_partner.age})' if self.life_partner else 'none'}, " \
               f"dad={dad_string}, " \
               f"mom={mom_string}, " \
               f"beauty={self.beauty}, standard={self.beauty_standard}, sex_exp={self.sex_XP}, " \
               f"life_exp={self.life_expectancy}, " \
               f"kids={self.kids}, " \
               f"partners={len(self.sexual_partners)}, " \
               f"vcard_lost_age={self.age_cherry_popped}, " \
               f"vcard_taker={self.cherry_popper.name if self.cherry_popper else None} ({self.cherry_popper.age if self.cherry_popper else ''}) "

    @property
    def age(self):
        global SimulationState
        ().current_day
        age = abs(SimulationState().current_day - self.year_of_birth * 365.25) / 365.25
        return float("%.2f" % age)

    def get_seed(self):
        # print(self.genes)
        seed = []
        for gene in self.genes:
            seed.append(random.choice(gene))

        return seed

    @property
    def is_dead(self):
        return self.age >= self.life_expectancy

    @property
    def is_adult(self):
        return self.age >= 18

    @property
    def should_give_birth(self):
        return NotImplementedError("This method should be implemented in the child class")


class Man(Human):
    def __init__(self, father_id=1, mother_id=1):
        super().__init__(father_id, mother_id)
        self.spermarche = random.randint(1125, 1550) / 100

    @property
    def can_ejaculate(self):
        return self.age >= self.spermarche

    @property
    def should_give_birth(self):
        return False

    def __repr__(self):
        k = super().__repr__()
        k += f' first_ejac={self.spermarche}'
        return k


class Woman(Human):
    def __init__(self, father_id=1, mother_id=1):
        super().__init__(father_id, mother_id)
        self.conception = None
        self.gestation_period = 9 * 30
        self.menarche = random.randint(800, 1300) / 100
        self.menonpause = random.randint(3300, 4500) / 100
        self.baby = None
        if father_id in mappings:
            self.surname = mappings[mother_id].upper()
        else:
            self.surname = get_syllable().upper()
            mappings[mother_id] = self.surname

    def __repr__(self):
        k = super().__repr__()
        k += f' menarche={self.menarche}, menonpause={self.menonpause}'
        return k

    @property
    def should_give_birth(self):
        if not self.conception:
            return False

        due_date = self.conception + self.gestation_period
        if self.baby is not None:
            if due_date > SimulationState().current_day:
                return False
            else:
                # Stillbirth or miscarriage
                if random.randint(0, 100000) < self.baby.miscarriage_rate:
                    print(f"Miscarriage for {self.baby}!")
                    self.baby = None
                    return False
                # print(due_date, SimulationState().current_day)
                return True
        else:
            return False

    @property
    def conception_chances(self):
        if self.age > self.menonpause:
            return 0
        if self.age < self.menarche:
            return 0

        roll = random.randint(0, 100)
        sigmoid = math.exp((self.age - self.menarche) / 10) / (1 + math.exp((self.age - self.menarche) / 10))
        chance = roll * sigmoid
        return chance

    def assess_pregnancy(self, man, cummies_roll: int):
        # Are we pregnant?
        if not self.conception_chances:
            return
        if cummies_roll < self.conception_chances:
            self.conception = SimulationState().current_day
            if random.randint(0, 100) < 50:
                Baby = Woman
            else:
                Baby = Man

            self.baby = Baby(
                father_id=man._id[0],
                mother_id=self._id[1]
            )
            self.baby.mother = self
            self.baby.father = man
            self.baby.generation = (man.generation[0] + 1, self.generation[1] + 1)
            self.baby.miscarriage_rate = random.randint(0, 100)

            self.baby.beauty = int(random.randint(-10, 10) + man.beauty * .50 + self.beauty * .50)
            self.baby.beauty_standard = int(
                random.randint(-10, 10) + man.beauty_standard * .50 + self.beauty_standard * .50)

            self.baby.genes = np.zeros((23, 2), dtype=int)
            self.baby.genes[:, 0] = self.get_seed()
            self.baby.genes[:, 1] = man.get_seed()

            print(f"Conception of {self.baby._id} successful!")

    def assess_beauty_and_experience(self, man):
        # if we are married, let's go for it!
        if self.life_partner == man:
            if not self.life_partner.is_dead:
                return 100
            else:
                self.life_partner = None

        modifier = 0

        # incest is a strong taboo
        if man._id[0] in self._id:
            modifier -= 50
        if man._id[1] in self._id:
            modifier -= 50

        # if modifier == -100:
        #     print("Incest is a strong taboo!")

        if man.beauty < self.beauty_standard:
            # woman is picky. less chance, but can still happen
            modifier -= 30

        if self.beauty < man.beauty_standard:
            # man is less picky ;)
            modifier += 10

        if len(self.sexual_partners.keys()) < 1:  # girl is a virgin:
            # picky on first encounter
            if len(man.sexual_partners.keys()) > 1:  # boy is not a virgin:
                modifier += 20

        if len(man.sexual_partners.keys()) < 1:  # boy is a virgin:
            modifier -= 10

        if len(man.sexual_partners.keys()) > len(self.sexual_partners.keys()) * 2:
            # man has some experience
            modifier += 10

        # consent is less likely
        if self.age < 6:  # pedo man
            modifier -= 100
        if self.age < 16:  # sex with a teen OK
            modifier -= 40

        if man.age < 6:
            modifier -= 100  # pedo woman
        if 11 < man.age < 18:  # horny teenager
            if self.age * 1.2 < man.age:
                modifier -= 40  # pedo guy
            if self.age > man.age * 1.2:
                modifier += 30  # horny girl
            else:
                modifier += 20

        # gender asymmetric perception of large age difference
        if self.age < man.age // 2 + 6:
            if self.age < 15:
                modifier -= 90
            else:
                modifier -= 50

        if man.age < self.age // 2 + 6:
            modifier -= 85

        # past sexual experience with same man
        if self._id in man.sexual_partners:
            modifier += 30
        else:
            modifier -= 20

        # Marriage dynamics
        if man.want_to_marry:
            if self.want_to_marry:  # and I want committed relationship
                if random.randint(0, 1000) < 750:  # it's a match! let's marry!
                    modifier += 1000
                    self.life_partner = man
                    man.life_partner = self
                    print(
                        f"[Day {SimulationState().current_day}] We are getting married: {self.name} ({self.age}F) and {man.name} ({man.age}M)")
                else:
                    modifier += 30
            else:  # woman wants casual relationship
                modifier -= 15
        else:
            if self.want_to_marry:  # but woman wants serious relationship
                modifier -= 30

        return modifier

    def conceive(self, man: Man):
        sex_roll = random.randint(0, 100)
        modifier = self.assess_beauty_and_experience(man)
        sex_roll += modifier

        # let's rock!
        if sex_roll < 75:
            return
        # else:
        #     print(f'Lovemaking session! '
        #           f' (roll: {sex_roll}): {man._id}'
        #           f' (beauty:{man.beauty}) ({int(man.age)}M)'
        #           f' and {self._id} (beauty:{self.beauty}) ({int(self.age)}F)!')

        # I JUST HAD SEX!!
        man.sex_XP += sex_roll
        self.sex_XP += sex_roll

        if not self.sexual_partners.keys():
            self.age_cherry_popped = self.age
            self.cherry_popper = man
        if not man.sexual_partners.keys():
            man.age_cherry_popped = man.age
            man.cherry_popper = self

        if man._id in self.sexual_partners.keys():
            self.sexual_partners[man._id] += 1
        else:
            self.sexual_partners[man._id] = 1

        if self._id in man.sexual_partners.keys():
            man.sexual_partners[self._id] += 1
        else:
            man.sexual_partners[self._id] = 1

        if not man.can_ejaculate:
            return

        # did he came inside?
        cummies_roll = random.randint(0, 100)
        if self.baby is not None:
            # print(f"Already pregnant ({SimulationState().current_day - self.conception - self.gestation_period}d)!")
            return

        if cummies_roll < 24:
            return

        self.assess_pregnancy(man, cummies_roll)
