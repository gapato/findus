from simplejson import load, loads, dumps
import logging
logger = logging.getLogger('cli.libfindus')

class Payment:

    def __init__(self, info):
        self.comment = info['comment']
        self.creditor = info['creditor']
        self.debtors = info['debtors']
        if len(self.debtors) == 0:
            error('Payment cannot be made to no one')
            raise ValueError
        self.amount = info['amount']
        self.share = self.amount/len(self.debtors)

        # debtors that exclude creditor
        self.effective_debtors = list(self.debtors)
        creditor_share_count = self.debtors.count(self.creditor)
        self.creditors_share = creditor_share_count * self.share
        for i in range(creditor_share_count):
            self.effective_debtors.remove(self.creditor)
        self.effective_amount = self.amount * (len(self.effective_debtors)/
                                               len(self.debtors))

    def make_debts(self):
        if len(self.effective_debtors) == 0: return {}
        discrete_amount = self.effective_amount/len(self.effective_debtors)
        debts = {}
        for debtor in self.effective_debtors:
            debt = debts.get(debtor) or Debt(debtor, self.creditor, 0, self.comment)
            debt.add(discrete_amount)
            debts[debtor] = debt
        return debts

class Debt:

    def __init__(self, debtor, creditor, amount=0, comment=None):
        self.debtor = debtor
        self.creditor = creditor
        self.amount = amount
        self.comment = comment

    def add(self, amount):
        self.amount += amount

    def can_merge(self, debt):
        return self.creditor == debt.creditor and self.debtor == debt.debtor

    def to_dict(self):
        return { 'debtor':self.debtor, 'creditor':self.creditor, 'amount':self.amount, 'comment':self.comment }

    def __repr__(self):
        return '{0} ({1})> {2}'.format(self.debtor, self.amount, self.creditor)

class Person:

    def __init__(self, name):
        self.name = name
        self.debts = {}
        self.cumul_paid = 0
        self.cumul_owed = 0
        self.to_pay     = 0
        self.to_receive = 0
        self.own_share  = 0

    def recalc(self):
        self.to_pay = 0
        for (c, d) in self.debts.items():
            self.to_pay += d.amount
        return { creditor:debt.amount for (creditor,debt) in self.debts.items() }

    def add_debt(self, debt, credit):
        effective_amount = debt.amount
        if credit:
            effective_amount -= credit.amount
            credit.amount -= debt.amount
            if effective_amount > 0:
                past_debt = self._add_insert_debt(debt.creditor, effective_amount)
            return credit
        else:
            logger.debug('inserting new debt to {0} ({1})'.format(debt.creditor, effective_amount))
            self._add_insert_debt(debt.creditor, effective_amount)
            return None

    def to_dict(self):
        return { 'name':self.name, 'cumul_paid':self.cumul_paid, 'cumul_owed':self.cumul_owed,
                 'to_pay':self.to_pay, 'to_receive':self.to_receive, 'own_share':self.own_share,
                 'debts': { d.creditor: d.to_dict() for d in self.debts.values() } }

    def _add_insert_debt(self, creditor_name, amount):
        d = self.debts.get(creditor_name)
        if d:
            d.add(amount)
        else:
            d = Debt(self.name, creditor_name, amount)
            self.debts[creditor_name] = d

class Ledger:

    def __init__(self, obj):
        if obj.__class__ == str:
            self.data = loads(obj)
        else:
            self.data = load(obj)
        self.reduced = False
        self.people = {}
        for p in self.data:
            if p['amount'] > 0:
                payment = Payment(p)
                creditor_name = payment.creditor
                creditor = self._get_insert_person(creditor_name)
                creditor.own_share += payment.creditors_share
                logger.debug('creditor: '+str(creditor.to_dict()))
                creditor.cumul_paid += payment.amount
            else:
                continue
            for d in payment.make_debts().values():
                logger.debug('processing '+str(d))
                debtor_name = d.debtor
                debtor = self._get_insert_person(debtor_name)
                logger.debug('debtor: '+str(debtor.to_dict()))
                debtor.cumul_owed += payment.share
                credit = creditor.debts.get(debtor_name)
                if credit:
                    logger.debug('found credit')
                new_credit = debtor.add_debt(d, credit)
                if new_credit and new_credit.amount <= 0:
                    creditor.debts.pop(debtor_name)
        self._recalc()

    def summary(self):
        string = 'Debts '
        if self.reduced:
            string += '(reduced)\n'
        else:
            string += '(unreduced)\n'
        for person in self.people.values():
            for d in person.debts.values():
                string += '{0} owes {1:.2f} to {2}\n'.format(d.debtor, d.amount, d.creditor)
        return string

    def json(self):
        return dumps(self.to_dict(), indent=True)

    def reduce(self):
        cycles = self._find_cycles()
        while cycles:
            # probably a bit dumb to recompute everything
            min_cycles_debts = self._min_cycles_debts(cycles)
            min_index = 0
            min_c_count = len(min_cycles_debts[min_index][1])
            for (i, (debt, member_cycles)) in enumerate(min_cycles_debts):
                l = len(member_cycles)
                if l == 1:
                    min_index = i
                    break
                if l < min_c_count:
                    min_index = i
                    min_c_count = l
            logger.debug('removing cycle '+str(cycles[min_index]))
            cycles = self._remove_cycle(cycles, min_index, min_cycles_debts)
            logger.debug('new cycles: '+str(cycles))
        self._recalc()
        self.reduced = True

    def to_dict(self):
        dict_repr = { person.name:person.to_dict() for person in self.people.values() }
        return dict_repr

    def _recalc(self):
        logger.debug('recalculating sum of debts')
        for person in self.people.values():
            person.to_receive = person.to_pay = 0
        for person in self.people.values():
            owed = person.recalc()
            for (creditor, amount) in owed.items():
                self.people[creditor].to_receive += amount

    def _get_insert_person(self, person_name):
        p = self.people.get(person_name)
        if not p:
            p = Person(person_name)
            self.people[person_name] = p
        return p

    def _find_cycles(self, history=[]):
        if history == []:
            cycles = []
            for person in self.people.values():
                new_cycles = self._find_cycles(history=[person])
                if len(new_cycles) > 0:
                    cycles = self._merge_cycles(cycles, new_cycles)
            return cycles
        else:
            index = history.index(history[-1])
            if index < len(history)-1:
                logger.debug('cycle found')
                return [history[index:-1]]
            cycles = []
            for (creditor, debt) in history[-1].debts.items():
                new_history = list(history)
                assert(debt.amount > 0) # true or bug
                new_history.append(self.people[creditor])
                new_cycles = self._find_cycles(history=new_history)
                if len(new_cycles) > 0:
                    cycles = self._merge_cycles(cycles, new_cycles)
            return cycles

    def _merge_cycles(self, cycles_1, cycles_2):
        logger.debug('merging '+str(cycles_1)+' and '+str(cycles_2))
        new_cycles = list(cycles_1)
        for c2 in cycles_2:
            if not any(map(lambda x:self._cycles_equal(x, c2), cycles_1)):
                new_cycles.append(c2)
        logger.debug('result: '+str(new_cycles))
        return new_cycles

    def _cycles_equal(self, c1, c2):
        logger.debug('comparing '+str(c1)+' and '+str(c2))
        if len(c1) != len(c2): return False
        try:
            i0 = c2.index(c1[0])
        except:
            logger.debug('cycles are different')
            return False
        i = 1
        offset = i0
        while i < len(c1):
            if i+offset == len(c2):
                offset = -i
            if c1[i] != c2[i+offset]:
                logger.debug('cycles are different')
                return False
            i += 1
        logger.debug('cycles are equal')
        return True

    def _min_cycles_debts(self, cycles):
        min_debts = []
        for cycle in cycles:
            logger.debug('min debt for '+str(cycle))
            min_debt = None
            for i in range(len(cycle)):
                debtor = cycle[i]
                if i == len(cycle) - 1:
                    creditor_name = cycle[0].name
                else:
                    creditor_name = cycle[i+1].name
                debt = debtor.debts[creditor_name]
                if i == 0:
                    min_debt = debt
                else:
                    if debt.amount < min_debt.amount:
                        min_debt = debt
            containing_cycles = []
            for c in cycles:
                if self._debt_in_cycle(min_debt, c):
                    containing_cycles.append(c)
            min_debts.append((min_debt, containing_cycles))
        logger.debug('got '+str(min_debts))
        return min_debts

    def _debt_in_cycle(self, debt, cycle):
        (debtor_name, creditor_name) = (debt.debtor, debt.creditor)
        for person in cycle:
            if debt in person.debts.values():
                return True
        return False

    def _remove_cycle(self, cycles, i, min_cycles_debts):
        cycle = cycles[i]
        min_debt = min_cycles_debts[i][0]
        min_debt_amount = min_debt.amount
        for i in range(len(cycle)):
            debtor = cycle[i]
            if i == len(cycle) - 1:
                creditor_name = cycle[0].name
            else:
                creditor_name = cycle[i+1].name
            debt = debtor.debts[creditor_name]
            assert(debt.amount >= min_debt.amount)
            logger.debug('reducing debt '+str(debt))
            debt.add(-min_debt_amount)
            if debt.amount == 0:
                debtor.debts.pop(creditor_name)
                for (d, cs) in min_cycles_debts:
                    if debt == d:
                        for c in cs:
                            try:
                                cycles.remove(c)
                            except:
                                pass
        return cycles
