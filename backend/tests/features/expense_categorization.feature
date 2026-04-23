Feature: Categorize uploaded expenses
  As a budget-conscious individual
  I want to upload a raw list of bank transactions and have them automatically tagged
  So that I can understand where my money is going

  Background:
    Given the expense categorizer service is running
    And keyword rules are loaded

  Scenario: Categorize a single free-form cafe transaction as Food
    When I submit the transaction text "Paid $12.50 at Corner Cafe."
    Then the transaction should be categorized as "Food"
    And the matched rule id should be "food_corner_cafe"
    And the transaction status should be "categorized"

  Scenario: Categorize a CSV upload with mixed known merchants
    Given a CSV file containing the following transactions
      | date       | description                         | amount  | currency |
      | 2026-04-01 | Starbucks Coffee                    | 5.80    | USD      |
      | 2026-04-02 | Netflix Subscription                | 16.99   | USD      |
      | 2026-04-03 | Sunrise Property Management Rent    | 1090.00 | USD      |
      | 2026-04-04 | Shell Gas Station                   | 29.85   | USD      |
    When I upload the CSV file
    Then all 4 transactions should be categorized
    And the coverage percent should be 100.0

  Scenario: Leave unknown merchants uncategorized when no strong match exists
    Given a CSV file containing the following transactions
      | date       | description                  | amount | currency |
      | 2026-04-10 | Unknown Merchant POS TXN     | 14.25  | USD      |
    When I upload the CSV file
    Then the transaction should be categorized as "Uncategorized"
    And the transaction status should be "uncategorized"

  Scenario: Meet the 80 percent correctness gate on a labeled validation set
    Given a labeled validation dataset is available
    When I run the evaluation gate with a threshold of 80 percent
    Then the evaluation should pass
    And the correctness percent should be at least 80.0
