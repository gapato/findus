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

class Debt:

    def __init__(self, debtor, creditor, amount=0, comment=None):
        self.debtor = debtor
        self.creditor = creditor
        self.amount = amount
        self.comment = comment

    def to_dict(self):
        return { 'debtor':self.debtor, 'creditor':self.creditor, 'amount':self.amount, 'comment':self.comment }

    def __repr__(self):
        return '{0} ({1})> {2}'.format(self.debtor, self.amount, self.creditor)

class Person:

    def __init__(self, name):
        self.name = name
        self.balance = self._tmp_balance = 0
        self.own_share = 0
        self.transfers = []

    def to_dict(self):
        return { 'name':self.name, 'balance':self.balance, 'own_share':self.own_share,
                 'transfers': self.transfers }

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
                logger.debug('creditor: '+str(creditor.to_dict()))
                creditor.balance += payment.amount
            else:
                continue
            for d in payment.debtors:
                debtor = self._get_insert_person(d)
                logger.debug('debtor: '+str(debtor.to_dict()))
                debtor.balance -= payment.share

        self._transfers_done = False
        self._generate_transfers()


    def summary(self):
        string = 'Debts:\n'
        for person in self.people:
            if person.balance > 0:
                string += '{0} is owed {1:.2f}\n'.format(person.name, person.balance)
            elif person.balance <= 0:
                string += '{0} owes {1:.2f}:\n'.format(person.name, -person.balance)
                for t in person.transfers:
                    string += '    {0:.2f} to {1}:\n'.format(t['amount'], t['to'])
        return string

    def json(self):
        return dumps(self.to_list(), indent=True)

    def to_list(self):
        list_repr = [ person.to_dict() for person in self.people ]
        return list_repr

    def _get_insert_person(self, person_name):
        p = self.people.get(person_name)
        if not p:
            p = Person(person_name)
            self.people[person_name] = p
        return p

    def _generate_transfers(self):

        if self._transfers_done:
            logger.error('Transfers have already been computed.\n')
            return

        self.people = sorted(self.people.values(), key=lambda p:p.balance)
        l = list(self.people)

        for p in l:
            p._tmp_balance = p.balance

        done = len(l) <= 1

        while not done:

            start = l[0]
            end   = l[-1]

            if start == end:
                if abs(start._tmp_balance) > 1e-14:
                    logger.warn('Balancing error: {}'.format(start._tmp_balance))
                break

            if -start._tmp_balance == end._tmp_balance:
                start.transfers.append({'to':end.name, 'amount':end._tmp_balance})
                start._tmp_balance = end._tmp_balance = 0
                l = l[1:-1]
            elif -start._tmp_balance > end._tmp_balance:
                start.transfers.append({'to':end.name, 'amount':end._tmp_balance})
                start._tmp_balance += end._tmp_balance
                end._tmp_balance = 0
                l = l[:-1]
            else:
                start.transfers.append({'to':end.name, 'amount':-start._tmp_balance})
                end._tmp_balance += start._tmp_balance
                start._tmp_balance = 0
                l = l[1:]

            done = len(l) == 0

        self._transfers_done = True
