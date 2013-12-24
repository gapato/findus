## Findus
Reduce debt graphs

    $ cat > test.json << EOF
    [
      {
        "buyer": "A",
        "amount": 10,
        "recipients": [
          "A",
          "B"
        ],
        "comment": "payment 1"
      },
      {
        "buyer": "B",
        "amount": 2,
        "recipients": [
          "A",
          "B"
        ],
        "comment": "payment 2"
      }
    ]
    EOF

    $ findus reduce test.json
    Debts (rounded to the nearest cent)
    B owes 4.00 to A

## License
MIT
