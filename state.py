class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        # If an instance of this class does not exist, create it
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class SimulationState(metaclass=SingletonMeta):

    def __init__(self):
        self.current_day = 0

    def next_day(self, days=1):
        self.current_day += days