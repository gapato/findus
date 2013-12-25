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

        # debtors that exclude creditor
        self.effective_debtors = list(self.debtors)
        for i in range(self.debtors.count(self.creditor)):
            self.effective_debtors.remove(self.creditor)
        self.effective_amount = self.amount * (len(self.effective_debtors)/
                                               len(self.debtors))

    def make_debts(self):
        discrete_amount = self.effective_amount/len(self.effective_debtors)
        debts = {}
        for debtor in self.effective_debtors:
            debt = debts.get(debtor) or Debt(debtor, self.creditor, 0, self.comment)
            debt.add(discrete_amount)
            debts[debtor] = debt
            logger.debug(debt)
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

    def __repr__(self):
        return '{0} ({1})> {2}'.format(self.debtor, self.amount, self.creditor)

class Ledger:

    def __init__(self, obj):
        if obj.__class__ == str:
            self.data = loads(obj)
        else:
            self.data = load(obj)
        self.reduced = False
        self.effective_debts = {}
        for p in self.data:
            if p['amount'] > 0:
                payment = Payment(p)
                creditor = payment.creditor
                creditor_debts = self.effective_debts.get(creditor) or {}
            else:
                continue
            for d in payment.make_debts().values():
                logger.debug('processing '+str(d))
                debtor = d.debtor
                debt = ((self.effective_debts.get(debtor)
                            and self.effective_debts[debtor].get(creditor))
                            or Debt(debtor, creditor))
                credit = creditor_debts.get(debtor)
                if credit:
                    logger.debug('credit: '+str(credit))
                    if credit.amount > d.amount:
                        credit.add(-d.amount)
                    else:
                        if credit.amount < d.amount:
                            debt.add(d.amount-credit.amount)
                        creditor_debts.pop(debtor)
                    logger.debug('new debt: '+str(debt))
                else:
                    debt.add(d.amount)
                if debt.amount > 0:
                    if not self.effective_debts.get(debtor):
                        self.effective_debts[debtor] = {}
                    self.effective_debts[debtor][creditor] = debt
            if len(creditor_debts) == 0:
                try: self.effective_debts.pop(creditor)
                except: pass
            else:
                self.effective_debts[creditor] = creditor_debts

    def summary(self):
        string = 'Debts '
        if self.reduced:
            string += '(reduced)\n'
        else:
            string += '(unreduced)\n'
        for c in self.effective_debts.values():
            for d in c.values():
                string += '{0} owes {1:.2f} to {2}\n'.format(d.debtor, d.amount, d.creditor)
        return string

    def _debts_list(self):
        debts_list = []
        for v in self.effective_debts.values():
            debts_list.extend(list(map(lambda i:i.__dict__, v.values())))
        return debts_list

    def json_debts(self):
        return dumps(self._debts_list(), indent=True)

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
        self.reduced = True

    def _find_cycles(self, history=[]):
        logger.debug(history)
        if history == []:
            cycles = []
            for debtor in self.effective_debts:
                new_cycles = self._find_cycles(history=[debtor])
                if len(new_cycles) > 0:
                    cycles = self._merge_cycles(cycles, new_cycles)
            return cycles
        else:
            index = history.index(history[-1])
            if index < len(history)-1:
                logger.debug('cycle found')
                return [history[index:-1]]
            creditors = self.effective_debts.get(history[-1])
            cycles = []
            for debt in creditors or []:
                new_history = list(history)
                new_history.append(debt)
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
                if i == len(cycle) - 1:
                    debt = self.effective_debts[cycle[i]][cycle[0]]
                else:
                    debt = self.effective_debts[cycle[i]][cycle[i+1]]
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
        (debtor, creditor) = (debt.debtor, debt.creditor)
        if cycle[-1] == debtor and cycle[0] == creditor:
            return True
        for i in range(len(cycle)-1):
            if cycle[i] == debtor and cycle[i+1] == creditor:
                return True
        return False

    def _remove_cycle(self, cycles, i, min_cycles_debts):
        cycle = cycles[i]
        min_debt = min_cycles_debts[i][0]
        min_debt_amount = min_debt.amount
        for i in range(len(cycle)):
            if i == len(cycle) - 1:
                debt = self.effective_debts[cycle[i]][cycle[0]]
            else:
                debt = self.effective_debts[cycle[i]][cycle[i+1]]
            assert(debt.amount >= min_debt.amount)
            logger.debug('reducing debt '+str(debt))
            debt.add(-min_debt_amount)
            if debt.amount == 0:
                self.effective_debts[debt.debtor].pop(debt.creditor)
                for (d, cs) in min_cycles_debts:
                    if debt == d:
                        for c in cs:
                            try:
                                cycles.remove(c)
                            except:
                                pass
        return cycles
