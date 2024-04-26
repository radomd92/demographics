class Singleton(type):
    def __init__(cls, name, bases, dict):
        super(Singleton, cls).__init__(name, bases, dict)
        cls.instance = None

    def __new__(type, name, bases, dict):
        if type.instance is None:
            type.instance = super(Singleton, type).__new__(type, name, bases, dict)
        return type.instance


class SimulationState(object):
    __metaclass__ = Singleton

    def __init__(self):
        self.current_day = 0

    def next_day(self, days=1):
        self.current_day += days