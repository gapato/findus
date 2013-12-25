## Findus
Reduce debt graphs

    $ findus reduce - << EOF
    [
      {
        "creditor": "A",
        "amount": 10,
        "debtors": [
          "A",
          "B"
        ],
        "comment": "payment 1"
      },
      {
        "creditor": "B",
        "amount": 2,
        "debtors": [
          "A",
          "B"
        ],
        "comment": "payment 2"
      }
    ]
    EOF

    $ findus reduce test.json
    Debts (reduced)
    B owes 4.00 to A

## License
MIT
