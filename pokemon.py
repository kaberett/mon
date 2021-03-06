import abc
from collections import namedtuple
from math import sqrt

import appraisal
import iv
import species


class Snapshot(metaclass=abc.ABCMeta):

    __slots__ = ()

    @abc.abstractmethod
    def encode_for_json(self):
        pass

    @staticmethod
    def looks_like_json_obj(dct):
        if (not isinstance(dct, dict) or
                'CP' not in dct or 'HP' not in dct or 'Dust' not in dct):
            return False
        if (len(dct) == 5 and
                'Species' in dct and dct['Species'] in species.species and
                'Half levels' in dct and isinstance(dct['Half levels'], bool)):
            # StartSnapshot
            return True
        if len(dct) == 4 and 'Steps' in dct and isinstance(dct['Steps'], int):
            # PowerUpSnapshot
            return True
        if (len(dct) == 5 and
                'Species' in dct and dct['Species'] in species.species and
                'Steps' in dct and isinstance(dct['Steps'], int)):
            # EvolutionSnapshot
            return True
        return False

    @staticmethod
    def decode_from_json(dct):
        if 'Half levels' in dct:
            cls = StartSnapshot
        elif 'Species' in dct:
            cls = EvolutionSnapshot
        else:
            cls = PowerUpSnapshot
        return cls.decode_from_json(dct)


class StartSnapshot(Snapshot,
                    namedtuple(
                        'StartSnapshot',
                        ('species', 'cp', 'hp', 'dust', 'half_levels'))):

    __slots__ = ()

    def encode_for_json(self):
        return {'Species': self.species.name,
                'CP': self.cp,
                'HP': self.hp,
                'Dust': self.dust,
                'Half levels': self.half_levels}

    @classmethod
    def decode_from_json(cls, dct):
        return cls(species.species[dct['Species']],
                   dct['CP'], dct['HP'], dct['Dust'], dct['Half levels'])


class PowerUpSnapshot(Snapshot,
                      namedtuple('PowerUpSnapshot',
                                 ('cp', 'hp', 'dust', 'power_ups'))):

    __slots__ = ()

    def encode_for_json(self):
        return {'CP': self.cp,
                'HP': self.hp,
                'Dust': self.dust,
                'Steps': self.power_ups}

    @classmethod
    def decode_from_json(cls, dct):
        return cls(dct['CP'], dct['HP'], dct['Dust'], dct['Steps'])


class EvolutionSnapshot(Snapshot,
                        namedtuple(
                            'EvolutionSnapshot',
                            ('species', 'cp', 'hp', 'dust', 'power_ups'))):

    __slots__ = ()

    def encode_for_json(self):
        return {'Species': self.species.name,
                'CP': self.cp,
                'HP': self.hp,
                'Dust': self.dust,
                'Steps': self.power_ups}

    @classmethod
    def decode_from_json(cls, dct):
        return cls(species.species[dct['Species']],
                   dct['CP'], dct['HP'], dct['Dust'], dct['Steps'])


class Pokemon(object):
    def __init__(self, snapshots=None, appraisal=None, nickname=None):
        if snapshots is None:
            snapshots = []

        self.snapshots = snapshots
        self.appraisal = appraisal
        self.nickname = nickname

    def __repr__(self):
        if self.nickname is None and self.appraisal is None:
            return '{}({!r})'.format(self.__class__.__name__, self.snapshots)
        elif self.appraisal is None:
            return '{}({!r}, nickname={!r})'.format(self.__class__.__name__,
                                                    self.snapshots,
                                                    self.nickname)
        elif self.nickname is None:
            return '{}({!r}, {!r})'.format(self.__class__.__name__,
                                           self.snapshots,
                                           self.appraisal)
        else:
            return '{}({!r}, {!r}, {!r})'.format(self.__class__.__name__,
                                                 self.snapshots,
                                                 self.appraisal,
                                                 self.nickname)

    @classmethod
    def new(cls, species, cp, hp, dust, name=None, half_levels=False):
        snapshot = StartSnapshot(species, cp, hp, dust, half_levels)
        return cls([snapshot], nickname=name)

    def power_up(self, cp, hp, dust, power_ups=1):
        snapshot = PowerUpSnapshot(cp, hp, dust, power_ups)
        self.snapshots.append(snapshot)

    def evolve(self, species, cp, hp, dust, power_ups=0):
        snapshot = EvolutionSnapshot(species, cp, hp, dust, power_ups)
        self.snapshots.append(snapshot)

    def appraise(self, overall, top_hp, top_att, top_dfn, top_iv):
        self.appraisal = appraisal.Appraisal(overall, top_hp, top_att, top_dfn,
                                             top_iv)

    @property
    def species(self):
        for snapshot in self.snapshots[::-1]:
            try:
                return snapshot.species
            except AttributeError:  # Didn't have a species attribute
                continue

    @property
    def cp(self):
        return self.snapshots[-1].cp

    @property
    def hp(self):
        return self.snapshots[-1].hp

    @property
    def name(self):
        if self.nickname is None:
            return self.species.name
        else:
            return self.nickname

    def rename(self, name):
        self.nickname = name

    @staticmethod
    def calc_cp(species, iv):
        # Based on
        # https://docs.google.com/spreadsheets/d/1wbtIc33K45iU1ScUnkB0PlslJ-eLaJlSZY47sPME2Uk
        # by /u/aggixx
        species.att
        iv.att
        cp = int((species.att + iv.att) *
                 sqrt(species.dfn + iv.dfn) *
                 sqrt(species.sta + iv.sta) *
                 iv.cp_scalar / 10)
        return max(cp, 10)

    @staticmethod
    def calc_hp(species, iv):
        # Based on
        # https://docs.google.com/spreadsheets/d/1wbtIc33K45iU1ScUnkB0PlslJ-eLaJlSZY47sPME2Uk
        # by /u/aggixx
        hp = int((species.sta + iv.sta) * sqrt(iv.cp_scalar))
        return max(hp, 10)

    def calc_ivs(self):
        for snapshot in self.snapshots:
            try:
                species = snapshot.species
            except AttributeError:
                # This snapshot doesn't define a new species, so just continue
                # using the previous value (and assume something will have set
                # the value previously).
                pass

            if isinstance(snapshot, StartSnapshot):
                possible_ivs = iv.IV.possible_ivs(
                    snapshot.dust, snapshot.half_levels)
            else:
                possible_ivs = {iv.increment_level(snapshot.power_ups)
                                for iv in possible_ivs}

            possible_ivs = {iv for iv in possible_ivs if
                            self.calc_cp(species, iv) == snapshot.cp and
                            self.calc_hp(species, iv) == snapshot.hp}

        if self.appraisal is not None:
            possible_ivs = {iv for iv in possible_ivs
                            if self.appraisal.valid_iv(iv)}

        return possible_ivs

    def percentage_range(self):
        ivs = self.calc_ivs()
        minimum = min(iv.percentage for iv in ivs)
        maximum = max(iv.percentage for iv in ivs)
        return (minimum, maximum)

    def encode_for_json(self):
        return {'Nickname': self.nickname,
                'Snapshots': [s.encode_for_json() for s in self.snapshots],
                'Appraisal': (None if self.appraisal is None
                              else self.appraisal.encode_for_json())}

    @staticmethod
    def looks_like_json_dct(dct):
        try:
            return (len(dct) == 3 and
                    (dct['Nickname'] is None or
                     isinstance(dct['Nickname'], str)) and
                    all(Snapshot.looks_like_json_obj(s)
                        for s in dct['Snapshots']) and
                    appraisal.Appraisal.looks_like_json_obj(dct['Appraisal']))
        except KeyError:
            return False

    @classmethod
    def decode_from_json(cls, dct):
        return cls([Snapshot.decode_from_json(s) for s in dct['Snapshots']],
                   appraisal.Appraisal.decode_from_json(dct['Appraisal']),
                   dct['Nickname'])
