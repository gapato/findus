## Findus
Reduce debt graphs

    $ cat test.json
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
    
    $ findus test.json
    B owes 4.00:
        4.00 to A:
    A is owed 4.00

## License
MIT
