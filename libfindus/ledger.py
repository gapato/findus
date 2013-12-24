from simplejson import load
import logging
logger = logging.getLogger('cli.libfindus')

class Payment:

    def __init__(self, info):
        self.comment = info['comment']
        self.creditor = info['buyer']
        self.debtors = info['recipients']
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
        return '{0} ({1})> {2} ({3})'.format(self.debtor, self.amount, self.creditor, self.comment)

class Ledger:

    def __init__(self, buf):
        self.data = load(buf)
        self.effective_debts = {}
        for p in self.data:
            if p['amount'] > 0:
                payment = Payment(p)
                creditor = payment.creditor
                creditor_debts = self.effective_debts.get(creditor) or {}
            else:
                continue
            for d in payment.make_debts().values():
                debtor = d.debtor
                debt = ((self.effective_debts.get(debtor)
                            and self.effective_debts[debtor].get(creditor))
                            or Debt(debtor, creditor))
                credit = creditor_debts.get(debtor)
                if credit:
                    if credit.amount > d.amount:
                        credit.add(-d.amount)
                    else:
                        if credit.amount < d.amount:
                            debt.add(d.amount)
                        creditor_debts.pop(debtor)
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
        print('Debts (rounded to the nearest cent)')
        for c in self.effective_debts.values():
            for d in c.values():
                print('{0} owes {1:.2f} to {2}'.format(d.debtor, d.amount, d.creditor))

    def reduce(self):
        cycle = self._find_cycle()
        while cycle:
            debts = []
            min_debt = None
            for i in range(len(cycle)):
                if i == len(cycle) - 1: break
                debt = self.effective_debts[cycle[i]][cycle[i+1]]
                debts.append(debt)
                if i == 0:
                    min_debt = debt
                else:
                    if debt.amount < min_debt.amount:
                        min_debt = debt
            logger.debug('Min. debt: '+str(min_debt))
            min_debt_amount = min_debt.amount
            for debt in debts:
                logger.debug('Old debt:'+str(debt))
                debt.add(-min_debt_amount)
                logger.debug('New debt:'+str(debt))
            self.effective_debts[min_debt.debtor].pop(min_debt.creditor)

            cycle = self._find_cycle()

    def _find_cycle(self, history=[]):
        logger.debug(history)
        if history == []:
            for debtor in self.effective_debts:
                ret = self._find_cycle(history=[debtor])
                if ret:
                    return ret
            return None
        else:
            index = history.index(history[-1])
            if index < len(history)-1:
                logger.debug('cycle found')
                return history[index:]
            creditors = self.effective_debts.get(history[-1])
            for debt in creditors or []:
                new_history = list(history)
                new_history.append(debt)
                return self._find_cycle(history=new_history)
